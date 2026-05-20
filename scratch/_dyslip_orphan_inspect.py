"""Inspect which Dyslipidaemia edge cpg_chunk_ids don't resolve, and why."""
import asyncio, os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
import asyncpg

load_dotenv()

async def main():
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    pg = await asyncpg.connect(os.getenv("DATABASE_URL"))

    async with driver.session() as session:
        r = await session.run("""
            MATCH ()-[r]->()
            WHERE r.source_document CONTAINS 'Dyslipidaemia'
              AND r.cpg_chunk_id IS NOT NULL
            RETURN r.cpg_chunk_id AS cid, r.source_document AS doc,
                   type(r) AS rel
        """)
        edges = [dict(rec) async for rec in r]

    ids = list({e["cid"] for e in edges})
    rows = await pg.fetch("SELECT id FROM chunks WHERE id::text = ANY($1::text[])", ids)
    live = {str(r["id"]) for r in rows}
    orphan_ids = [i for i in ids if i not in live]

    print(f"Distinct singular cpg_chunk_id on Dyslipidaemia edges: {len(ids)}")
    print(f"Orphans: {len(orphan_ids)}\n")
    for oid in orphan_ids:
        sample = next(e for e in edges if e["cid"] == oid)
        # does this id exist anywhere in chunks (any CPG)?
        anywhere = await pg.fetchval("SELECT count(*) FROM chunks WHERE id::text=$1", oid)
        print(f"  {oid}  exists_in_chunks_any_cpg={anywhere}  doc={sample['doc'][:50]}  rel={sample['rel']}")

    await pg.close()
    await driver.close()

asyncio.run(main())
