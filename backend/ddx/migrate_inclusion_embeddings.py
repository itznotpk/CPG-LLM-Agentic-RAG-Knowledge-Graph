"""
Migration Script: Add Inclusion Embeddings to icd11_codes table

Populates `icd11_codes.inclusion_embeddings` (JSONB) with one embedding per
inclusion term, keyed by the raw inclusion text. Codes with no inclusion terms
keep an empty `{}` — description-level matching is already covered by the main
`icd11_codes.embedding` vector (STEP_05 builds it from
"<title>. <description>. Also known as: <inclusions>"), so no separate
description vector is stored here. (Historical note: an earlier version of this
script also stored the description under a special "[DESCRIPTION]" key; that was
an undocumented deviation from STEP_05 and was removed 2026-05-17. Rows written
by that version are cleaned up by --force, see below.)

Idempotent by default: a row is skipped if its `inclusion_embeddings` already
contains a key for every inclusion term (and no stale "[DESCRIPTION]" key). Use
--force to recompute, --chapters to scope to specific ICD-11 chapters (e.g.
newly ingested ones), and --dry-run to preview without embedding calls or DB
writes.

Examples:
    # Only backfill newly ingested chapters 18 and 21 (skips already-done rows)
    python -m ddx.migrate_inclusion_embeddings --chapters 18,21

    # Preview what a full run would touch, no API/DB side effects
    python -m ddx.migrate_inclusion_embeddings --dry-run

    # Force a full recompute of every row (the old behaviour)
    python -m ddx.migrate_inclusion_embeddings --force
"""

import argparse
import asyncio
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from agent.providers import get_embedding_client, get_embedding_model


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using the configured provider.

    Provider-aware: branches on EMBEDDING_PROVIDER. Inlined here (rather than
    importing from agent.tools) to avoid agent.graph_utils -> graphiti_core,
    a heavy dependency this script doesn't need.
    """
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if embedding_provider == "bedrock":
        import boto3

        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        model_id = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v1")
        dimension = int(os.getenv("VECTOR_DIMENSION", "1536"))

        def _invoke():
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

    # OpenAI-compatible fallback
    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(input=text, model=model_name)
    return response.data[0].embedding


DESCRIPTION_KEY = "[DESCRIPTION]"  # legacy: cleaned up, never written anymore


def _needs_processing(row, force: bool) -> bool:
    """Idempotency check: True if this row still needs (re)writing.

    A row is already done when its inclusion_embeddings JSONB has a key for
    every non-empty inclusion term AND contains NO stale legacy
    "[DESCRIPTION]" key. A code with zero inclusion terms is "done" only if
    its JSONB is empty (or just needs the stale key stripped). --force
    bypasses the skip entirely.
    """
    if force:
        return True

    existing = row["inclusion_embeddings"]
    if existing is None:
        return True
    if isinstance(existing, str):
        existing = json.loads(existing) if existing else {}

    # A leftover [DESCRIPTION] key from the old script means this row must be
    # rewritten so the key is removed.
    if DESCRIPTION_KEY in existing:
        return True

    inclusions = [t for t in (row["inclusions"] or []) if t and t.strip()]
    for inc_text in inclusions:
        if inc_text not in existing:
            return True
    return False


async def migrate(chapters: list[str] | None, force: bool, dry_run: bool):
    """Add inclusion_embeddings column and populate it.

    Args:
        chapters: restrict to these ICD-11 chapter values (e.g. ["18","21"]);
                  None means all chapters.
        force:    recompute even rows that are already fully populated.
        dry_run:  no embedding calls, no DB writes — just report what would run.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")

    conn = await asyncpg.connect(database_url)

    try:
        # Step 1: Add column if not exists (skipped on dry-run)
        if dry_run:
            print("📋 Step 1: (dry-run) skipping column DDL")
        else:
            print("📋 Step 1: Adding inclusion_embeddings column...")
            try:
                await conn.execute("""
                    ALTER TABLE icd11_codes
                    ADD COLUMN IF NOT EXISTS inclusion_embeddings JSONB DEFAULT '{}'
                """)
                print("   ✅ Column added (or already exists)")
            except Exception as e:
                print(f"   ⚠️ Column may already exist: {e}")

        # Step 2: Fetch candidate rows (chapter-scoped if requested)
        print("\n📋 Step 2: Fetching codes with inclusions or descriptions...")
        if chapters:
            rows = await conn.fetch("""
                SELECT code, title, description, inclusions, chapter, inclusion_embeddings
                FROM icd11_codes
                WHERE ((inclusions IS NOT NULL AND array_length(inclusions, 1) > 0)
                       OR (description IS NOT NULL AND description != ''))
                  AND chapter = ANY($1::text[])
            """, chapters)
            print(f"   Scope: chapters {','.join(chapters)}")
        else:
            rows = await conn.fetch("""
                SELECT code, title, description, inclusions, chapter, inclusion_embeddings
                FROM icd11_codes
                WHERE (inclusions IS NOT NULL AND array_length(inclusions, 1) > 0)
                   OR (description IS NOT NULL AND description != '')
            """)
            print("   Scope: all chapters")
        print(f"   Found {len(rows)} candidate codes")

        # Idempotency filter
        pending = [r for r in rows if _needs_processing(r, force)]
        skipped = len(rows) - len(pending)
        print(f"   {len(pending)} need embedding, {skipped} already complete (skipped)"
              f"{' [--force overrides skip]' if force else ''}")

        # Step 3: Generate one embedding per inclusion term (inclusion-only;
        # description matching lives in the main `embedding` column per STEP_05).
        print("\n📋 Step 3: Generating inclusion embeddings"
              f"{' (DRY RUN — no API/DB calls)' if dry_run else ''}...")
        updated = 0
        cleaned = 0  # rows rewritten purely to strip a stale [DESCRIPTION] key

        for row in pending:
            code = row["code"]
            inclusions = [t for t in (row["inclusions"] or []) if t and t.strip()]

            existing = row["inclusion_embeddings"]
            if isinstance(existing, str):
                existing = json.loads(existing) if existing else {}
            had_stale_desc = bool(existing) and DESCRIPTION_KEY in existing

            if dry_run:
                if inclusions:
                    note = f"would embed {len(inclusions)} inclusion(s)"
                else:
                    note = "no inclusions → would set {}"
                if had_stale_desc:
                    note += " (+ strip stale [DESCRIPTION])"
                print(f"   • {code} (ch {row['chapter']}): {note}")
                updated += 1
                continue

            inclusion_embeddings = {}
            for inc_text in inclusions:
                print(f"   🔄 {code}: Embedding inclusion '{inc_text[:40]}...'")
                emb = await generate_embedding(inc_text)
                inclusion_embeddings[inc_text] = emb

            # Always write — even an empty {} — so any leftover [DESCRIPTION]
            # key from the old script is removed for inclusion-less codes.
            await conn.execute("""
                UPDATE icd11_codes
                SET inclusion_embeddings = $1
                WHERE code = $2
            """, json.dumps(inclusion_embeddings), code)
            updated += 1
            if not inclusion_embeddings and had_stale_desc:
                cleaned += 1

        verb = "Would update" if dry_run else "Updated"
        extra = f", {cleaned} of them cleared a stale [DESCRIPTION] key" if cleaned else ""
        print(f"\n✅ {'Dry run complete' if dry_run else 'Migration complete'}! "
              f"{verb} {updated} codes ({skipped} skipped as already complete){extra}.")

    finally:
        await conn.close()


def _parse_args():
    p = argparse.ArgumentParser(
        prog="python -m ddx.migrate_inclusion_embeddings",
        description="Backfill icd11_codes.inclusion_embeddings (idempotent).",
    )
    p.add_argument(
        "--chapters",
        help="Comma-separated ICD-11 chapters to scope to, e.g. '18,21'. "
             "Omit to process all chapters.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Recompute even rows that are already fully populated.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No embedding calls, no DB writes — only report what would run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    chapters = (
        [c.strip() for c in args.chapters.split(",") if c.strip()]
        if args.chapters else None
    )
    print("=" * 60)
    print("  ICD-11 Inclusion Embeddings Migration")
    print("=" * 60)
    asyncio.run(migrate(chapters=chapters, force=args.force, dry_run=args.dry_run))
