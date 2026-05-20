"""Strict per-CPG cpg_chunk_id resolution rate across several CPGs, to tell
systemic sub-chunk artifact (low %) from real corruption (high %)."""
import asyncio, os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
import asyncpg
load_dotenv()

CPGS = ["Dyslipidaemia", "CVD-Prevention-Women", "Heart-Failure", "Hypertension", "Ischaemic-Stroke"]

async def main():
    driver = AsyncGraphDatabase.driver(os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
    pg = await asyncpg.connect(os.getenv("DATABASE_URL"))
    async with driver.session() as session:
        for cpg in CPGS:
            r = await session.run("""
                MATCH ()-[r]->() WHERE r.source_document CONTAINS $cpg AND r.cpg_chunk_id IS NOT NULL
                RETURN collect(DISTINCT r.cpg_chunk_id) AS ids
            """, cpg=cpg)
            ids = (await r.single())["ids"]
            if not ids:
                print(f"{cpg:24} no edges"); continue
            rows = await pg.fetch("SELECT id FROM chunks WHERE id::text = ANY($1::text[])", ids)
            live = {str(x["id"]) for x in rows}
            orph = len(ids) - len(live)
            print(f"{cpg:24} {len(live)}/{len(ids)} resolve  orphans={orph} ({100*orph/len(ids):.1f}%)")
    await pg.close(); await driver.close()
asyncio.run(main())
