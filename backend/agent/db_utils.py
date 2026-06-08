"""
Database utilities for PostgreSQL connection and operations.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from uuid import UUID
import logging

import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DatabasePool:
    """Manages PostgreSQL connection pool."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database pool.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        self.pool: Optional[Pool] = None
    
    async def initialize(self):
        """Create connection pool."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                max_inactive_connection_lifetime=300,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            yield connection


# Global database pool instance
db_pool = DatabasePool()

# Supabase pool — separate DB used for Doctor UI tables (patients, consultations,
# delivery_jobs). Initialized only if SUPABASE_DB_URL is set; otherwise stays None
# and any caller that needs it must check first.
class _SupabasePool(DatabasePool):
    def __init__(self):
        self.database_url = os.getenv("SUPABASE_DB_URL")
        self.pool: Optional[Pool] = None
        self._init_failed = False

    async def initialize(self):
        if not self.database_url:
            logger.warning("SUPABASE_DB_URL not set — Supabase pool disabled")
            return
        if self._init_failed:
            return
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=5,
                max_inactive_connection_lifetime=300,
                command_timeout=60,
            )
            logger.info("Supabase connection pool initialized")

    @asynccontextmanager
    async def acquire(self):
        if self.pool is None:
            raise RuntimeError("Supabase pool is not initialized")
        async with self.pool.acquire() as connection:
            yield connection


supabase_pool = _SupabasePool()


async def initialize_database():
    """Initialize database connection pool."""
    await db_pool.initialize()


async def initialize_supabase_db():
    """Initialize Supabase connection pool (no-op if SUPABASE_DB_URL unset)."""
    await supabase_pool.initialize()


async def close_database():
    """Close database connection pool."""
    await db_pool.close()


async def close_supabase_db():
    """Close Supabase connection pool."""
    await supabase_pool.close()


async def save_pipeline_timings(
    consultation_id: int,
    timings: dict[str, float],
    request_id: str = "",
) -> None:
    """Persist stage timings + request_id to the consultations row. Best-effort."""
    pool = supabase_pool.pool
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "SELECT update_consultation($1::integer, p_pipeline_timings => $2::jsonb, p_request_id => $3)",
                consultation_id,
                json.dumps(timings),
                request_id or None,
            )
    except Exception as exc:
        logger.warning("save_pipeline_timings failed (non-fatal): %s", exc)


async def log_machine_signal(
    signal_type: str,
    *,
    consultation_id: int | None = None,
    request_id: str = "",
    cpg_name: str | None = None,
    trigger: str | None = None,
    condition: str | None = None,
    detail: str | None = None,
    severity: str = "info",
    payload: dict | None = None,
) -> None:
    """Persist one pipeline insight to the machine_signals table (the "Machine
    Signals" feed of the Layer-3 feedback ecosystem). Direct INSERT into a
    standalone table — no RPC, so it sidesteps the update_consultation overload
    trap. Best-effort: never raises, never blocks the pipeline. Requires
    add_machine_signals.sql to have been run on Supabase.

    signal_type ∈ {'gate_failure','data_quality','kg_gap','coverage_gap','stage_error'}.
    """
    pool = supabase_pool.pool
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO machine_signals
                    (consultation_id, request_id, signal_type, cpg_name,
                     trigger, condition, detail, severity, payload)
                VALUES ($1::integer, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                """,
                consultation_id,
                request_id or None,
                signal_type,
                cpg_name,
                trigger,
                condition,
                detail,
                severity,
                json.dumps(payload) if payload is not None else None,
            )
    except Exception as exc:
        logger.warning("log_machine_signal failed (non-fatal): %s", exc)


# Session Management Functions
async def create_session(
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timeout_minutes: int = 60
) -> str:
    """
    Create a new session.
    
    Args:
        user_id: Optional user identifier
        metadata: Optional session metadata
        timeout_minutes: Session timeout in minutes
    
    Returns:
        Session ID
    """
    async with db_pool.acquire() as conn:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
        
        result = await conn.fetchrow(
            """
            INSERT INTO sessions (user_id, metadata, expires_at)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            user_id,
            json.dumps(metadata or {}),
            expires_at
        )
        
        return result["id"]


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get session by ID.
    
    Args:
        session_id: Session UUID
    
    Returns:
        Session data or None if not found/expired
    """
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT 
                id::text,
                user_id,
                metadata,
                created_at,
                updated_at,
                expires_at
            FROM sessions
            WHERE id = $1::uuid
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            session_id
        )
        
        if result:
            return {
                "id": result["id"],
                "user_id": result["user_id"],
                "metadata": json.loads(result["metadata"]),
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat(),
                "expires_at": result["expires_at"].isoformat() if result["expires_at"] else None
            }
        
        return None


async def update_session(session_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Update session metadata.
    
    Args:
        session_id: Session UUID
        metadata: New metadata to merge
    
    Returns:
        True if updated, False if not found
    """
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE sessions
            SET metadata = metadata || $2::jsonb
            WHERE id = $1::uuid
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            session_id,
            json.dumps(metadata)
        )
        
        return result.split()[-1] != "0"


# Message Management Functions
async def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add a message to a session.
    
    Args:
        session_id: Session UUID
        role: Message role (user/assistant/system)
        content: Message content
        metadata: Optional message metadata
    
    Returns:
        Message ID
    """
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO messages (session_id, role, content, metadata)
            VALUES ($1::uuid, $2, $3, $4)
            RETURNING id::text
            """,
            session_id,
            role,
            content,
            json.dumps(metadata or {})
        )
        
        return result["id"]


async def get_session_messages(
    session_id: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get messages for a session.
    
    Args:
        session_id: Session UUID
        limit: Maximum number of messages to return
    
    Returns:
        List of messages ordered by creation time
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT 
                id::text,
                role,
                content,
                metadata,
                created_at
            FROM messages
            WHERE session_id = $1::uuid
            ORDER BY created_at
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = await conn.fetch(query, session_id)
        
        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"].isoformat()
            }
            for row in results
        ]


# Document Management Functions
async def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Get document by ID.
    
    Args:
        document_id: Document UUID
    
    Returns:
        Document data or None if not found
    """
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT 
                id::text,
                title,
                source,
                content,
                metadata,
                created_at,
                updated_at
            FROM documents
            WHERE id = $1::uuid
            """,
            document_id
        )
        
        if result:
            return {
                "id": result["id"],
                "title": result["title"],
                "source": result["source"],
                "content": result["content"],
                "metadata": json.loads(result["metadata"]),
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat()
            }
        
        return None


async def list_documents(
    limit: int = 100,
    offset: int = 0,
    metadata_filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    List documents with optional filtering.
    
    Args:
        limit: Maximum number of documents to return
        offset: Number of documents to skip
        metadata_filter: Optional metadata filter
    
    Returns:
        List of documents
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT 
                d.id::text,
                d.title,
                d.source,
                d.metadata,
                d.created_at,
                d.updated_at,
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
        """
        
        params = []
        conditions = []
        
        if metadata_filter:
            conditions.append(f"d.metadata @> ${len(params) + 1}::jsonb")
            params.append(json.dumps(metadata_filter))
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += """
            GROUP BY d.id, d.title, d.source, d.metadata, d.created_at, d.updated_at
            ORDER BY d.created_at DESC
            LIMIT $%d OFFSET $%d
        """ % (len(params) + 1, len(params) + 2)
        
        params.extend([limit, offset])
        
        results = await conn.fetch(query, *params)
        
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "source": row["source"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "chunk_count": row["chunk_count"]
            }
            for row in results
        ]


# Vector Search Functions
async def vector_search(
    embedding: List[float],
    limit: int = 10,
    document_id_filter: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Perform vector similarity search.

    Args:
        embedding: Query embedding vector
        limit: Maximum number of results
        document_id_filter: If provided, restrict results to chunks from these document UUIDs

    Returns:
        List of matching chunks ordered by similarity (best first)
    """
    async with db_pool.acquire() as conn:
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        if document_id_filter:
            results = await conn.fetch(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.content,
                    1 - (c.embedding <=> $1::vector) AS similarity,
                    COALESCE(c.metadata::text, '{}') AS metadata,
                    d.title AS document_title,
                    d.source AS document_source,
                    d.metadata->>'published_year' AS published_year
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.document_id = ANY($3::uuid[])
                  AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_str,
                limit,
                document_id_filter,
            )
        else:
            results = await conn.fetch(
                "SELECT * FROM match_chunks($1::vector, $2)",
                embedding_str,
                limit,
            )

        def _merge_year(row) -> dict:
            md = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
            # match_chunks() doesn't return published_year — only the filter branch does
            year = row["published_year"] if "published_year" in row.keys() else None
            if year is not None:
                md = {**md, "published_year": int(year)}
            return md

        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "content": row["content"],
                "similarity": row["similarity"],
                "metadata": _merge_year(row),
                "document_title": row["document_title"],
                "document_source": row["document_source"],
            }
            for row in results
        ]


async def hybrid_search(
    embedding: List[float],
    query_text: str,
    limit: int = 10,
    rrf_k: int = 60,
    document_id_filter: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search (vector + keyword) using Reciprocal Rank Fusion.

    Args:
        embedding: Query embedding vector
        query_text: Query text for keyword search
        limit: Maximum number of results
        rrf_k: RRF constant (default 60); higher = diminish rank-position influence
        document_id_filter: If provided, restrict results to chunks from these document UUIDs

    Returns:
        List of matching chunks ordered by combined score (best first)
    """
    async with db_pool.acquire() as conn:
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        if document_id_filter:
            results = await conn.fetch(
                """
                WITH vector_results AS (
                    SELECT
                        c.id AS chunk_id,
                        c.document_id,
                        c.content,
                        1 - (c.embedding <=> $1::vector) AS vector_sim,
                        ROW_NUMBER() OVER (ORDER BY c.embedding <=> $1::vector) AS vector_rank,
                        c.metadata,
                        d.title  AS document_title,
                        d.source AS document_source,
                        d.metadata->>'published_year' AS published_year
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.document_id = ANY($5::uuid[])
                      AND c.embedding IS NOT NULL
                ),
                text_results AS (
                    SELECT
                        c.id AS chunk_id,
                        ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', $2)) AS text_sim,
                        ROW_NUMBER() OVER (
                            ORDER BY ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', $2)) DESC
                        ) AS text_rank
                    FROM chunks c
                    WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', $2)
                      AND c.document_id = ANY($5::uuid[])
                      AND c.embedding IS NOT NULL
                )
                SELECT
                    v.chunk_id,
                    v.document_id,
                    v.content,
                    (1.0 / ($4 + v.vector_rank) + COALESCE(1.0 / ($4 + t.text_rank), 0)) AS combined_score,
                    v.vector_sim AS vector_similarity,
                    COALESCE(t.text_sim, 0) AS text_similarity,
                    COALESCE(v.metadata::text, '{}') AS metadata,
                    v.document_title,
                    v.document_source,
                    v.published_year
                FROM vector_results v
                LEFT JOIN text_results t ON v.chunk_id = t.chunk_id
                ORDER BY combined_score DESC
                LIMIT $3
                """,
                embedding_str,
                query_text,
                limit,
                rrf_k,
                document_id_filter,
            )
        else:
            results = await conn.fetch(
                "SELECT * FROM hybrid_search($1::vector, $2, $3, $4)",
                embedding_str,
                query_text,
                limit,
                rrf_k,
            )

        def _merge_year(row) -> dict:
            md = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
            year = row["published_year"] if "published_year" in row.keys() else None
            if year is not None:
                md = {**md, "published_year": int(year)}
            return md

        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "content": row["content"],
                "combined_score": row["combined_score"],
                "vector_similarity": row["vector_similarity"],
                "text_similarity": row["text_similarity"],
                "metadata": _merge_year(row),
                "document_title": row["document_title"],
                "document_source": row["document_source"],
            }
            for row in results
        ]


# Chunk Management Functions
async def get_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """
    Get all chunks for a document.
    
    Args:
        document_id: Document UUID
    
    Returns:
        List of chunks ordered by chunk index
    """
    async with db_pool.acquire() as conn:
        results = await conn.fetch(
            "SELECT * FROM get_document_chunks($1::uuid)",
            document_id
        )
        
        return [
            {
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "metadata": json.loads(row["metadata"])
            }
            for row in results
        ]


# Utility Functions
async def execute_query(query: str, *params) -> List[Dict[str, Any]]:
    """
    Execute a custom query.
    
    Args:
        query: SQL query
        *params: Query parameters
    
    Returns:
        Query results
    """
    async with db_pool.acquire() as conn:
        results = await conn.fetch(query, *params)
        return [dict(row) for row in results]


async def test_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        True if connection successful
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def fetch_icd_ancestors(conn, code: str, max_depth: int = 2) -> list[dict[str, Any]]:
    """
    Fetch ICD-11 ancestors using the stored parent_code chain.

    Stops naturally when parent_code is not present in icd11_codes; this is
    expected for chapter roots and intentionally missing WHO block groupings.
    """
    rows = await conn.fetch(
        """
        WITH RECURSIVE ancestors AS (
          SELECT code, parent_code, 0 AS depth FROM icd11_codes WHERE code = $1
          UNION ALL
          SELECT c.code, c.parent_code, a.depth + 1
            FROM icd11_codes c JOIN ancestors a ON c.code = a.parent_code
           WHERE a.depth < $2
        )
        SELECT code, depth FROM ancestors WHERE depth > 0 ORDER BY depth
        """,
        code,
        max_depth,
    )
    return [dict(row) for row in rows]


async def fetch_icd_siblings(conn, code: str) -> list[str]:
    """Fetch ICD-11 sibling codes sharing the predicted code's parent_code.

    Includes .Y (other specified) and .Z (unspecified) variants — all codes
    whose parent_code equals the predicted code's parent_code.

    Guard: when the shared parent is a *chapter root* (a node whose own
    parent_code is empty/NULL, e.g. '08', '16' — chapter roots store
    parent_code = ''), the "siblings" would be the entire chapter — clinically
    meaningless (migraine and stroke are not peers). Such codes have no granular
    parent in the table, so the sibling step is skipped for them and routing falls
    through to the ancestor/semantic steps. Real siblings (e.g. children of BC81,
    whose parent BC81 sits below chapter '11') are unaffected.
    """
    rows = await conn.fetch(
        """
        SELECT s.code
        FROM icd11_codes p
        JOIN icd11_codes s
          ON s.parent_code = p.parent_code
         AND s.code <> p.code
        WHERE p.code = $1
          AND NOT EXISTS (
              SELECT 1 FROM icd11_codes par
              WHERE par.code = p.parent_code
                AND (par.parent_code IS NULL OR par.parent_code = '')
          )
        ORDER BY s.code
        """,
        code,
    )
    return [row["code"] for row in rows]


async def fetch_icd_ancestor_siblings(conn, code: str) -> list[str]:
    """Fetch peer categories of the predicted code's direct parent.

    For BA00.0 (parent=BA00, grandparent=Hypertensive diseases):
    returns BA01, BA02, BA03, BA04 — siblings of BA00, not of BA00.0.
    Excludes the direct parent itself (BA00) since ancestor_d1 already tried it.

    Guard: when the direct parent is itself a *chapter root* (parent_code empty),
    its "peers" are OTHER CHAPTERS — a cross-chapter explosion (e.g. migraine in
    ch.08 reaching neoplasms in ch.02). Skip the step in that case. Codes whose
    parent is a real block within a chapter (e.g. BA00 under chapter 11) are
    unaffected — their peers stay same-chapter.
    """
    rows = await conn.fetch(
        """
        SELECT s.code
        FROM icd11_codes p
        JOIN icd11_codes parent ON parent.code = p.parent_code
        JOIN icd11_codes s
          ON s.parent_code = parent.parent_code
         AND s.code <> parent.code
        WHERE p.code = $1
          AND parent.parent_code IS NOT NULL
          AND parent.parent_code <> ''
        ORDER BY s.code
        """,
        code,
    )
    return [row["code"] for row in rows]


async def fetch_icd_ancestor_sibling_children(conn, code: str) -> list[str]:
    """Fetch all children of the predicted code's parent-sibling categories.

    For BA00.0: returns BA01.0, BA01.Y, BA01.Z, BA02.0 ... BA04.Z —
    the full subtree of BA01-BA04, one level deep.
    Excludes the predicted code's own siblings (already tried in the sibling step).

    Guard: same chapter-root protection as fetch_icd_ancestor_siblings — when the
    direct parent is a chapter root, the "sibling categories" are other chapters and
    their children span unrelated chapters. Skip in that case.
    """
    rows = await conn.fetch(
        """
        SELECT child.code
        FROM icd11_codes p
        JOIN icd11_codes parent ON parent.code = p.parent_code
        JOIN icd11_codes sibling
          ON sibling.parent_code = parent.parent_code
         AND sibling.code <> parent.code
        JOIN icd11_codes child ON child.parent_code = sibling.code
        WHERE p.code = $1
          AND parent.parent_code IS NOT NULL
          AND parent.parent_code <> ''
        ORDER BY child.code
        """,
        code,
    )
    return [row["code"] for row in rows]
