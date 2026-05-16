"""Check chunks table schema and category distribution."""
import asyncio, os, json
from dotenv import load_dotenv
load_dotenv()
import asyncpg

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL"))

    # Distinct category values
    rows = await conn.fetch(
        "SELECT metadata->>'category' AS cat, count(*) AS n "
        "FROM chunks GROUP BY cat ORDER BY n DESC LIMIT 20"
    )
    print("=== category distribution ===")
    for r in rows:
        print(f"  {r['cat']!r:40s} {r['n']}")

    # Sample row with a non-null category
    sample = await conn.fetchrow(
        "SELECT id, chunk_level, metadata FROM chunks "
        "WHERE metadata->>'category' IS NOT NULL LIMIT 1"
    )
    if sample:
        print(f"\n=== sample row with category ===")
        print(f"  id: {sample['id']}")
        print(f"  chunk_level: {sample['chunk_level']}")
        meta = json.loads(sample['metadata'])
        print(f"  category: {meta.get('category')!r}")

    await conn.close()

asyncio.run(main())
