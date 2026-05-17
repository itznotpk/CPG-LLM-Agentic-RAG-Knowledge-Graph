"""
resolve_gold_chunk_ids.py

Resolves placeholder chunk IDs in eval/gold_sets/retrieval_gold.jsonl
by doing a vector similarity search scoped to the CPG's documents,
taking the top 3 chunk UUIDs as ground truth.
"""

import sys
import os
import json
import asyncio

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from agent.tools import generate_embedding

GOLD_FILE = os.path.join(os.path.dirname(__file__), '..', 'eval', 'gold_sets', 'retrieval_gold.jsonl')
GOLD_FILE = os.path.normpath(GOLD_FILE)

TOP_K = 3

# Gold-set filter name → actual cpg_name slug in DB.
# Only CPGs that have been ingested need entries here; others stay unresolved.
FILTER_TO_CPG_SLUG: dict[str, str] = {
    "Atrial Fibrillation":            "Atrial-Fibrillation(2012)",
    "Cancer Pain":                    "Cancer-Pain(2nd Edition)",
    "Patient Safety Minimal Monitoring": "Patient-Safety-Minimal-Monitoring",
    "Pre-Anaesthetic Assessment":     "Pre-Anaesthetic-Assessment",
    "Anaesthesia Medication Safety":  "Anaesthesia-Medication-Safety",
    "Anaesthesia Safe Medication Use":"Anaesthesia-Medication-Safety",
}


def is_placeholder(chunk_id: str) -> bool:
    return chunk_id.startswith("REPLACE_WITH_")


async def get_document_ids_for_filter(conn, document_filter: str):
    """
    Find document UUIDs for a given gold-set filter name.
    Uses the explicit slug map first; falls back to substring match.
    """
    slug = FILTER_TO_CPG_SLUG.get(document_filter)
    if slug:
        rows = await conn.fetch(
            "SELECT id::text FROM documents WHERE metadata->>'cpg_name' = $1",
            slug,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id::text FROM documents
            WHERE LOWER(metadata->>'cpg_name') LIKE LOWER($1)
            """,
            f"%{document_filter}%",
        )
    return [row["id"] for row in rows]


async def resolve_query(conn, query_text: str, document_filter: str):
    """
    Generate embedding for query_text, then do a vector search scoped to
    documents matching document_filter. Returns top-3 chunk UUIDs.
    """
    # Get document IDs matching the filter
    doc_ids = await get_document_ids_for_filter(conn, document_filter)

    if not doc_ids:
        print(f"  [WARN] No documents found for filter '{document_filter}'")
        return None

    # Generate embedding for the query
    embedding = await generate_embedding(query_text)
    embedding_str = '[' + ','.join(map(str, embedding)) + ']'

    # Vector search scoped to the matching documents
    rows = await conn.fetch(
        """
        SELECT
            c.id::text AS chunk_id,
            1 - (c.embedding <=> $1::vector) AS similarity
        FROM chunks c
        WHERE c.document_id = ANY($3::uuid[])
          AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> $1::vector
        LIMIT $2
        """,
        embedding_str,
        TOP_K,
        doc_ids
    )

    if not rows:
        print(f"  [WARN] No chunks found for filter '{document_filter}' (doc_ids={doc_ids[:3]}...)")
        return None

    chunk_ids = [row['chunk_id'] for row in rows]
    return chunk_ids


async def main():
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set in environment")
        sys.exit(1)

    print(f"Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    print(f"Connected. Reading gold set from: {GOLD_FILE}")

    with open(GOLD_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    entries = [json.loads(line) for line in lines]
    print(f"Loaded {len(entries)} entries from gold set.\n")

    resolved_count = 0
    failed_count = 0
    sample_resolved = []

    for i, entry in enumerate(entries):
        query_id = entry.get('id', f'entry_{i}')
        query_text = entry['query']
        document_filter = entry['document_filter']
        chunk_ids = entry.get('relevant_chunk_ids', [])

        # Check if any placeholders need resolving
        has_placeholder = any(is_placeholder(cid) for cid in chunk_ids)
        if not has_placeholder:
            print(f"[{query_id}] Already resolved — skipping.")
            resolved_count += 1
            continue

        print(f"[{query_id}] Resolving: '{query_text[:60]}...' | filter='{document_filter}'")

        try:
            resolved_ids = await resolve_query(conn, query_text, document_filter)
        except Exception as e:
            print(f"  [ERROR] Failed to resolve {query_id}: {e}")
            failed_count += 1
            continue

        if resolved_ids is None:
            failed_count += 1
            continue

        # Replace the relevant_chunk_ids with real UUIDs
        entry['relevant_chunk_ids'] = resolved_ids
        resolved_count += 1
        print(f"  -> {resolved_ids}")

        if len(sample_resolved) < 3:
            sample_resolved.append(entry)

    await conn.close()

    # Write back
    print(f"\nWriting resolved gold set back to: {GOLD_FILE}")
    with open(GOLD_FILE, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"  Total queries:     {len(entries)}")
    print(f"  Resolved (real):   {resolved_count}")
    print(f"  Failed:            {failed_count}")
    print()
    print("Sample resolved entries (3):")
    for sample in sample_resolved:
        print(f"\n  ID: {sample['id']}")
        print(f"  Query: {sample['query'][:80]}")
        print(f"  Filter: {sample['document_filter']}")
        print(f"  Chunk IDs: {sample['relevant_chunk_ids']}")
    print()


if __name__ == '__main__':
    asyncio.run(main())
