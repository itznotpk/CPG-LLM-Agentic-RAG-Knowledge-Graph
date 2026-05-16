import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from agent.db_utils import db_pool

async def main():
    await db_pool.initialize()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT title FROM documents ORDER BY title")
        print("All documents:")
        for r in rows:
            print(f"  {r['title']}")
        rows2 = await conn.fetch("SELECT DISTINCT chunk_level, count(*) as cnt FROM chunks GROUP BY chunk_level")
        print("\nChunk levels:")
        for r in rows2:
            print(f"  {r['chunk_level']}: {r['cnt']}")
    await db_pool.close()

asyncio.run(main())
