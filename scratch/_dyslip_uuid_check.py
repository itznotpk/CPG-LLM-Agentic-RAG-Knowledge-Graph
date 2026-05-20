"""Full cross-DB integrity check for Dyslipidaemia edges:
verify every cpg_chunk_id on Neo4j edges resolves to a live Postgres chunk."""
import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
import asyncpg

load_dotenv()

async def main():
    neo_uri = os.getenv("NEO4J_URI")
    neo_user = os.getenv("NEO4J_USER")
    neo_pass = os.getenv("NEO4J_PASSWORD")
    pg_dsn = os.getenv("DATABASE_URL")

    driver = AsyncGraphDatabase.driver(neo_uri, auth=(neo_user, neo_pass))

    # Collect all cpg_chunk_ids referenced by edges tied to Dyslipidaemia chunks
    async with driver.session() as session:
        result = await session.run("""
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_ids IS NOT NULL
              AND (r.source_document CONTAINS 'Dyslipidaemia' OR r.source CONTAINS 'Dyslipidaemia')
            RETURN r.cpg_chunk_ids AS ids
        """)
        records = [r async for r in result]

    # Fallback: just pull every edge that mentions Dyslipidaemia anywhere
    if not records:
        async with driver.session() as session:
            result = await session.run("""
                MATCH ()-[r]->()
                WHERE r.cpg_chunk_ids IS NOT NULL
                RETURN r.cpg_chunk_ids AS ids, properties(r) AS props
                LIMIT 5
            """)
            sample = [r async for r in result]
            print("Sample edge properties (no source/cpg_source filter matched):")
            for s in sample:
                print(s["props"].keys())

    all_ids = set()
    for r in records:
        for cid in r["ids"]:
            all_ids.add(cid)

    print(f"Edges with Dyslipidaemia ref: {len(records)}")
    print(f"Distinct cpg_chunk_ids referenced: {len(all_ids)}")

    if all_ids:
        pg = await asyncpg.connect(pg_dsn)
        rows = await pg.fetch(
            "SELECT id FROM chunks WHERE id::text = ANY($1::text[])",
            list(all_ids),
        )
        live = {str(r["id"]) for r in rows}
        missing = all_ids - live
        print(f"Resolved in Postgres: {len(live)}/{len(all_ids)}")
        print(f"Orphaned (missing): {len(missing)}")
        if missing:
            print("First 5 missing:", list(missing)[:5])
        await pg.close()

    await driver.close()

asyncio.run(main())
