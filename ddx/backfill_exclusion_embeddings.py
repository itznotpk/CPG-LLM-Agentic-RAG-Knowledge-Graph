"""
Backfill ICD-11 exclusion phrase embeddings.

Populates `icd11_codes.exclusion_embeddings` (JSONB) with one embedding per
WHO exclusion term, keyed by the raw exclusion text. This is intentionally
exclusion-term-only: do not add description vectors or synthetic keys.

Idempotent by default: rows are skipped when every non-empty exclusion term
already has an embedding. Use --force to recompute, --dry-run to preview
without embedding calls or DB writes, --limit for test runs, and --chapters to
scope future chapter top-ups cheaply.

Examples:
    python -m ddx.backfill_exclusion_embeddings --dry-run
    python -m ddx.backfill_exclusion_embeddings --limit 20
    python -m ddx.backfill_exclusion_embeddings --chapters 18,21
    python -m ddx.backfill_exclusion_embeddings --force
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
    """Generate an embedding using the configured provider."""
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


def _normalise_jsonb(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value) if value else {}
    return dict(value)


def _exclusion_terms(row: asyncpg.Record | dict) -> list[str]:
    return [t for t in (row["exclusions"] or []) if t and t.strip()]


def _needs_processing(row: asyncpg.Record | dict, force: bool) -> bool:
    """Return True when a row needs exclusion_embeddings written."""
    if force:
        return True

    existing = _normalise_jsonb(row["exclusion_embeddings"])
    for term in _exclusion_terms(row):
        if term not in existing:
            return True
    return False


def _batched(items: list[asyncpg.Record], size: int = BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _fetch_rows(
    conn: asyncpg.Connection,
    chapters: list[str] | None,
    limit: int | None,
) -> list[asyncpg.Record]:
    clauses = ["cardinality(exclusions) > 0"]
    args: list[Any] = []

    if chapters:
        args.append(chapters)
        clauses.append(f"chapter = ANY(${len(args)}::text[])")

    sql = f"""
        SELECT code, title, exclusions, chapter, exclusion_embeddings
        FROM icd11_codes
        WHERE {' AND '.join(clauses)}
        ORDER BY code
    """

    if limit is not None:
        args.append(limit)
        sql += f"\nLIMIT ${len(args)}"

    return list(await conn.fetch(sql, *args))


async def backfill(
    chapters: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")

    conn = await asyncpg.connect(database_url)
    try:
        if dry_run:
            print("Step 1: (dry-run) skipping exclusion_embeddings DDL")
        else:
            print("Step 1: adding exclusion_embeddings column...")
            await conn.execute("""
                ALTER TABLE icd11_codes
                ADD COLUMN IF NOT EXISTS exclusion_embeddings JSONB DEFAULT '{}'
            """)

        print("Step 2: fetching ICD-11 rows with exclusions...")
        rows = await _fetch_rows(conn, chapters=chapters, limit=limit)
        pending = [row for row in rows if _needs_processing(row, force=force)]
        skipped = len(rows) - len(pending)

        print(f"Scope: {'all chapters' if not chapters else ','.join(chapters)}")
        print(f"Found {len(rows)} candidate rows; {len(pending)} pending, {skipped} skipped")

        updated = 0
        embedding_calls = 0

        for batch in _batched(pending):
            updates: list[tuple[str, str]] = []
            for row in batch:
                code = row["code"]
                terms = _exclusion_terms(row)

                if dry_run:
                    print(f"  {code} (ch {row['chapter']}): would embed {len(terms)} exclusion(s)")
                    updated += 1
                    embedding_calls += len(terms)
                    continue

                embeddings: dict[str, list[float]] = {}
                for term in terms:
                    print(f"  {code}: embedding exclusion '{term[:60]}...'")
                    embeddings[term] = await generate_embedding(term)
                    embedding_calls += 1

                updates.append((json.dumps(embeddings), code))

            if updates and not dry_run:
                await conn.executemany(
                    """
                    UPDATE icd11_codes
                    SET exclusion_embeddings = $1
                    WHERE code = $2
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
        prog="python -m ddx.backfill_exclusion_embeddings",
        description="Backfill icd11_codes.exclusion_embeddings (idempotent).",
    )
    parser.add_argument(
        "--chapters",
        help="Comma-separated ICD-11 chapters to process, e.g. '18,21'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rows only; no embedding calls or DB writes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute rows even when already populated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit candidate rows for testing.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    chapters = (
        [c.strip() for c in args.chapters.split(",") if c.strip()]
        if args.chapters
        else None
    )
    asyncio.run(
        backfill(
            chapters=chapters,
            force=args.force,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    )
