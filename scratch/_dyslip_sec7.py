import asyncio, os
from dotenv import load_dotenv
import asyncpg
load_dotenv()

ORPHANS = [
 "e8623df3-5b87-4fbe-8a78-9d7b284d838b","811c91be-3e36-406a-ab60-6d24a72a8101",
 "9b8f3c3e-8009-4ce6-8208-164e6b25fcb5","14d28246-57a8-47f7-ad8a-7d78b1dfe4b7",
 "6cd52823-c676-4c1b-b61e-7d47edca3c82","b48c6bdb-ba6c-4f2e-a8ac-8d75cfea110d",
 "1ed223c3-978a-46aa-bca7-918674064325","1634e16d-cffe-4526-9960-2b2f52af6907",
]

async def main():
    pg = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await pg.fetch("""
        SELECT c.id::text AS id, c.chunk_level, c.embedding IS NULL AS null_emb,
               c.metadata->>'chunk_id' AS meta_chunk_id, left(c.content,40) AS snippet
        FROM chunks c JOIN documents d ON c.document_id=d.id
        WHERE d.title ILIKE '%Section 7: Management Of Dyslipidaemia%'
        ORDER BY c.chunk_index
    """)
    print(f"Section 7 chunks in Postgres: {len(rows)}")
    for r in rows:
        flag = "  <-- meta_chunk_id != row id" if r['meta_chunk_id'] and r['meta_chunk_id']!=r['id'] else ""
        print(f"  {r['id']} lvl={r['chunk_level']:8} null_emb={r['null_emb']} meta={r['meta_chunk_id']}{flag}")
    print("\nAre any orphan IDs present as a row id? ")
    for o in ORPHANS:
        n = await pg.fetchval("SELECT count(*) FROM chunks WHERE id::text=$1", o)
        m = await pg.fetchval("SELECT count(*) FROM chunks WHERE metadata->>'chunk_id'=$1", o)
        print(f"  {o}: as_row_id={n} as_meta_chunk_id={m}")
    await pg.close()
asyncio.run(main())
