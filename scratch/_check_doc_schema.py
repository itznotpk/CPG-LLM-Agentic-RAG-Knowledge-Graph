import asyncio, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv; load_dotenv()
import asyncpg

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='documents'")
    print('documents columns:')
    for c in cols:
        print(f"  {c['column_name']}: {c['data_type']}")
    rows = await conn.fetch("SELECT title, source, metadata FROM documents LIMIT 3")
    print('\nSample rows:')
    for r in rows:
        print(f"  title: {r['title']}")
        print(f"  source: {r['source']}")
        md = r['metadata']
        if isinstance(md, str): md = json.loads(md)
        print(f"  metadata keys: {list(md.keys()) if md else None}")
        print(f"  metadata: {json.dumps(md, indent=2)[:400] if md else None}")
        print()
    await conn.close()

asyncio.run(main())
