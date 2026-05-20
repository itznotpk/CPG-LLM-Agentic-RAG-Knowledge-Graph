"""Check both cpg_chunk_id (singular) AND cpg_chunk_ids (list) for Dyslipidaemia edges."""
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
        # Singular cpg_chunk_id
        r1 = await session.run("""
            MATCH ()-[r]->()
            WHERE r.source_document CONTAINS 'Dyslipidaemia'
              AND r.cpg_chunk_id IS NOT NULL
            RETURN collect(DISTINCT r.cpg_chunk_id) AS ids
        """)
        singular = (await r1.single())["ids"]

        # Plural cpg_chunk_ids
        r2 = await session.run("""
            MATCH ()-[r]->()
            WHERE r.source_document CONTAINS 'Dyslipidaemia'
              AND r.cpg_chunk_ids IS NOT NULL
            UNWIND r.cpg_chunk_ids AS cid
            RETURN collect(DISTINCT cid) AS ids
        """)
        plural = (await r2.single())["ids"]

    # Resolve both against Postgres
    for name, ids in [("cpg_chunk_id (singular)", singular), ("cpg_chunk_ids (list)", plural)]:
        rows = await pg.fetch(
            "SELECT id FROM chunks WHERE id::text = ANY($1::text[])",
            list(ids),
        )
        live = {str(r["id"]) for r in rows}
        print(f"{name}: {len(live)}/{len(ids)} resolve in Postgres (orphans: {len(ids) - len(live)})")

    # Cross-check: how many chunks does Postgres currently hold for Dyslipidaemia docs?
    pg_cnt = await pg.fetchval("""
        SELECT count(*) FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.source ILIKE '%Dyslipidaemia%'
    """)
    print(f"Postgres chunks under Dyslipidaemia documents: {pg_cnt}")

    await pg.close()
    await driver.close()

asyncio.run(main())
