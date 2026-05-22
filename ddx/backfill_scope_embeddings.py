"""
Backfill document scope embeddings for semantic CPG fallback.

Embeds `f"{title}. {scope_rationale or ''}"` into
`documents.scope_embedding`. Idempotent by default: existing vectors are
skipped unless --force is passed.

Note: if scopes/rationales are still being populated, do not run this yet.
Run after scope review has been applied, or rerun later with --force.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

from agent.providers import get_embedding_client, get_embedding_model

BATCH_SIZE = 10


async def generate_embedding(text: str) -> list[float]:
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if embedding_provider == "bedrock":
        import boto3

        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        model_id = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v1")
        dimension = int(os.getenv("VECTOR_DIMENSION", "1536"))

        def _invoke() -> list[float]:
            if "titan" in model_id:
                body = json.dumps({"inputText": text})
            elif "cohere" in model_id:
                body = json.dumps({"texts": [text], "input_type": "search_query"})
            else:
                raise ValueError(f"Unsupported Bedrock embedding model: {model_id}")

            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            if "titan" in model_id:
                return result["embedding"][:dimension]
            return result["embeddings"][0][:dimension]

        return await asyncio.to_thread(_invoke)

    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(input=text, model=model_name)
    return response.data[0].embedding


def _parse_jsonb_list(value: Any) -> list[str]:
    """Return a flat list of strings from a JSONB array, text[], or None."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        import json as _json
        try:
            parsed = _json.loads(value)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if v]
        except Exception:
            pass
        return [value.strip()] if value.strip() else []
    return []


def _build_scope_text(row: asyncpg.Record | dict[str, Any]) -> str:
    """
    Build the text embedded into documents.scope_embedding.

    Uses the human-authored cpg_scope_rationale (stored in the scope_rationale
    column) plus the procedure_scope tags only. ICD-11 condition titles are
    intentionally NOT dumped in: for broad CPGs (100+ codes) they dilute the
    embedding into a blurry centroid. The rationale prose already describes the
    conditions in natural language, which is a stronger, compact semantic signal.
    """
    parts: list[str] = []

    rationale = (row["scope_rationale"] or "").strip()
    if rationale:
        parts.append(rationale)

    proc_tags = _parse_jsonb_list(row["procedure_scope"])
    if proc_tags:
        parts.append("Procedures: " + "; ".join(proc_tags) + ".")

    if not parts:
        # Bare minimum: just the document title so the row is not empty
        return (row["title"] or "").strip()

    return " ".join(parts)


def _needs_processing(row: asyncpg.Record | dict[str, Any], force: bool) -> bool:
    if force:
        return True
    return row["scope_embedding"] is None


def _batched(items: list[asyncpg.Record], size: int = BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _fetch_rows(
    conn: asyncpg.Connection,
    only_verified: bool,
    limit: int | None,
) -> list[asyncpg.Record]:
    clauses = ["title IS NOT NULL"]
    args: list[Any] = []

    if only_verified:
        clauses.append("scope_verified = TRUE")

    sql = f"""
        SELECT id::text, title, scope_rationale, icd11_scope, procedure_scope,
               scope_verified, scope_embedding
        FROM documents
        WHERE {' AND '.join(clauses)}
        ORDER BY title, id
    """

    if limit is not None:
        args.append(limit)
        sql += f"\nLIMIT ${len(args)}"

    return list(await conn.fetch(sql, *args))


async def backfill(
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    only_verified: bool = True,
) -> dict[str, int]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")

    conn = await asyncpg.connect(database_url)
    try:
        if dry_run:
            print("Step 1: (dry-run) skipping documents.scope_embedding DDL")
        else:
            print("Step 1: adding documents.scope_embedding column/index...")
            await conn.execute("""
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS scope_embedding vector(1536)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_scope_embedding
                ON documents USING ivfflat (scope_embedding vector_cosine_ops) WITH (lists = 16)
            """)

        print("Step 2: fetching document rows...")
        rows = await _fetch_rows(conn, only_verified=only_verified, limit=limit)
        pending = [row for row in rows if _needs_processing(row, force=force)]
        skipped = len(rows) - len(pending)
        print(
            f"Found {len(rows)} candidate rows; {len(pending)} pending, {skipped} skipped "
            f"({'verified only' if only_verified else 'all documents'})"
        )

        updated = 0
        embedding_calls = 0

        for batch in _batched(pending):
            updates: list[tuple[str, str]] = []
            for row in batch:
                text = _build_scope_text(row)
                if dry_run:
                    print(f"  {row['id']}: would embed {len(text)} chars")
                    updated += 1
                    embedding_calls += 1
                    continue

                emb = await generate_embedding(text)
                embedding_calls += 1
                vector = "[" + ",".join(map(str, emb)) + "]"
                updates.append((vector, row["id"]))

            if updates and not dry_run:
                await conn.executemany(
                    """
                    UPDATE documents
                    SET scope_embedding = $1::vector
                    WHERE id = $2::uuid
                    """,
                    updates,
                )
                updated += len(updates)

        print(
            f"{'Dry run complete' if dry_run else 'Backfill complete'}: "
            f"{updated} rows {'would be ' if dry_run else ''}updated, "
            f"{skipped} skipped, {embedding_calls} embedding calls"
        )
        return {
            "candidate_rows": len(rows),
            "updated_rows": updated,
            "skipped_rows": skipped,
            "embedding_calls": embedding_calls,
        }
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ddx.backfill_scope_embeddings",
        description="Backfill documents.scope_embedding for semantic CPG fallback.",
    )
    parser.add_argument("--dry-run", action="store_true", help="No embedding calls or DB writes.")
    parser.add_argument("--force", action="store_true", help="Recompute existing vectors.")
    parser.add_argument("--limit", type=int, help="Limit rows for testing.")
    parser.add_argument(
        "--all-documents",
        action="store_true",
        help="Process all documents instead of only scope_verified=TRUE rows.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        backfill(
            force=args.force,
            dry_run=args.dry_run,
            limit=args.limit,
            only_verified=not args.all_documents,
        )
    )
