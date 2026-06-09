"""
§4.3.1 Grounding-store integrity smoke test (Neon pgvector).

This is the standalone connectivity-and-integrity check named as the one gap in
report §4.3.1: the rest of the pgvector store is validated *indirectly* through
the Layer A/B/C accuracy layers, but those would not cleanly attribute a failure
to a broken probes setting, a wrong embedding dimension, a missing ivfflat index,
or a row with no scope wiring. These tests assert those invariants in isolation
so such a defect surfaces as a named store failure rather than as mysterious
recall loss several layers up.

LIVE DB ONLY — skipped automatically when DATABASE_URL is unset (so the mocked
unit suite and DB-less CI runs are unaffected). Run explicitly with:

    cd backend; pytest tests/test_grounding_store_smoke.py -m integration
"""

from __future__ import annotations

import os

import asyncpg
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="grounding-store smoke test requires a live DATABASE_URL",
    ),
]

EXPECTED_EMBEDDING_DIM = 1536

# (table, column) pairs that must be vector(1536). pgvector stores the dimension
# directly in atttypmod, so atttypmod == dim with no varchar-style +4 offset.
VECTOR_COLUMNS = [
    ("chunks", "embedding"),
    ("documents", "scope_embedding"),
    ("icd11_codes", "embedding"),
]

# ivfflat indexes the DDx / scope vector paths depend on.
IVFFLAT_INDEXES = [
    "idx_chunks_embedding",
    "idx_documents_scope_embedding",
]


async def _vector_dim(conn: asyncpg.Connection, table: str, column: str) -> int:
    return await conn.fetchval(
        """
        SELECT a.atttypmod
        FROM pg_attribute a
        WHERE a.attrelid = $1::regclass
          AND a.attname = $2
          AND NOT a.attisdropped
        """,
        table,
        column,
    )


# ---------------------------------------------------------------------------
# Connectivity + pgvector extension + probes guard
# ---------------------------------------------------------------------------

async def test_vector_extension_installed(db_conn):
    """The pgvector extension must be present, or every vector path is dead."""
    installed = await db_conn.fetchval(
        "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
    )
    assert installed == 1, "pgvector extension is not installed in this database"


async def test_ivfflat_probes_guard_takes_effect(db_conn):
    """
    `SET ivfflat.probes = 100` is the silent-drop guard in search_ddx.py and
    routing.py: at the default probes=1 the approximate index scans ~1/10 of
    vectors and silently drops true top matches. Prove the GUC is accepted and
    actually applied on this connection.
    """
    await db_conn.execute("SET ivfflat.probes = 100")
    value = await db_conn.fetchval("SHOW ivfflat.probes")
    assert value == "100", f"ivfflat.probes did not stick (got {value!r})"


# ---------------------------------------------------------------------------
# Embedding dimension = 1536 across all three vector spaces
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table,column", VECTOR_COLUMNS)
async def test_embedding_dimension_is_1536(db_conn, table, column):
    dim = await _vector_dim(db_conn, table, column)
    assert dim == EXPECTED_EMBEDDING_DIM, (
        f"{table}.{column} is vector({dim}), expected vector({EXPECTED_EMBEDDING_DIM}); "
        "a dimension drift breaks cosine search against Titan 1536-dim embeddings"
    )


# ---------------------------------------------------------------------------
# ivfflat indexes present on the live vector columns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("index_name", IVFFLAT_INDEXES)
async def test_ivfflat_index_present(db_conn, index_name):
    indexdef = await db_conn.fetchval(
        "SELECT indexdef FROM pg_indexes WHERE indexname = $1", index_name
    )
    assert indexdef is not None, f"missing index {index_name}"
    assert "ivfflat" in indexdef.lower(), (
        f"{index_name} is not an ivfflat index: {indexdef}"
    )


# ---------------------------------------------------------------------------
# Corpus is non-empty and fully embedded (no dead, unsearchable rows)
# ---------------------------------------------------------------------------

async def test_corpus_non_empty(db_conn):
    docs = await db_conn.fetchval("SELECT count(*) FROM documents")
    chunks = await db_conn.fetchval("SELECT count(*) FROM chunks")
    assert docs > 0, "documents table is empty — no CPGs ingested"
    assert chunks > 0, "chunks table is empty — nothing to retrieve"


async def test_every_leaf_chunk_is_embedded(db_conn):
    """
    Every *leaf* chunk (one with no children) must be embedded — an un-embedded
    leaf is invisible to vector search, a silent recall hole. Structural *parent*
    chunks (h1/intermediate containers that have children) are intentionally left
    un-embedded; retrieval filters `embedding IS NOT NULL`, so they are skipped by
    design and must NOT be asserted against.
    """
    unembedded_leaves = await db_conn.fetchval(
        """
        SELECT count(*) FROM chunks c
        WHERE c.embedding IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM chunks ch WHERE ch.parent_chunk_id = c.id
          )
        """
    )
    assert unembedded_leaves == 0, (
        f"{unembedded_leaves} leaf chunk(s) have NULL embedding — unsearchable recall hole"
    )


# ---------------------------------------------------------------------------
# Scope wiring: every verified (live) CPG can route and fall back semantically
# ---------------------------------------------------------------------------

async def test_verified_documents_exist(db_conn):
    verified = await db_conn.fetchval(
        "SELECT count(*) FROM documents WHERE scope_verified = TRUE"
    )
    assert verified > 0, "no scope_verified documents — Stage 3 routing has no corpus"


async def test_verified_documents_have_scope_wiring(db_conn):
    """
    Every live (scope_verified) document must carry routing scope — an ICD-11
    scope array OR a procedure_scope array (procedure-only CPGs have the latter).
    A verified row with neither can never be routed to.
    """
    missing_scope = await db_conn.fetchval(
        """
        SELECT count(*) FROM documents
        WHERE scope_verified = TRUE
          AND cardinality(icd11_scope) = 0
          AND cardinality(procedure_scope) = 0
        """
    )
    assert missing_scope == 0, (
        f"{missing_scope} verified document(s) have neither icd11_scope nor procedure_scope"
    )


async def test_verified_documents_have_scope_embedding(db_conn):
    """D2 semantic fallback needs scope_embedding on every verified document."""
    missing_embedding = await db_conn.fetchval(
        """
        SELECT count(*) FROM documents
        WHERE scope_verified = TRUE
          AND scope_embedding IS NULL
        """
    )
    assert missing_embedding == 0, (
        f"{missing_embedding} verified document(s) have NULL scope_embedding "
        "(D2 semantic routing fallback would silently skip them)"
    )


# ---------------------------------------------------------------------------
# DDx vector table is populated (Stage 2 depends on it)
# ---------------------------------------------------------------------------

async def test_icd11_codes_have_embeddings(db_conn):
    total = await db_conn.fetchval("SELECT count(*) FROM icd11_codes")
    embedded = await db_conn.fetchval(
        "SELECT count(*) FROM icd11_codes WHERE embedding IS NOT NULL"
    )
    assert total > 0, "icd11_codes table is empty — Stage 2 DDx has no search space"
    assert embedded > 0, (
        "icd11_codes has no non-NULL embeddings — DDx vector search would return nothing"
    )
