"""Dump full metadata for a few chunks to see what keys exist."""
import asyncio, os, json
from dotenv import load_dotenv
load_dotenv()
import asyncpg

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        """
        SELECT c.id::text, c.chunk_level, c.metadata, LEFT(c.content, 120) AS preview
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.metadata->>'cpg_name' = 'Cancer-Pain(2nd Edition)'
          AND c.embedding IS NOT NULL
        ORDER BY c.metadata->>'source_file', c.chunk_level
        LIMIT 10
        """
    )
    for r in rows:
        meta = json.loads(r['metadata'])
        print(f"\nid={r['id']}  lvl={r['chunk_level']}")
        print(f"  meta keys: {list(meta.keys())}")
        print(f"  meta: {json.dumps(meta, indent=2)[:500]}")
        print(f"  preview: {r['preview']!r}")
    await conn.close()

asyncio.run(main())
