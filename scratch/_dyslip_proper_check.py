"""Identify Dyslipidaemia edges by their ACTUAL section titles (both spellings),
not the substring 'Dyslipidaemia'. Measure orphan rate properly."""
import asyncio, os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
import asyncpg
load_dotenv()

async def main():
    pg = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # The 15 real section titles for this CPG
    titles = [r["title"] for r in await pg.fetch("""
        SELECT DISTINCT title FROM documents
        WHERE metadata->>'cpg_name' = 'Dyslipidaemia(6th-Edition)'
    """)]
    print(f"Dyslipidaemia section titles ({len(titles)}):")
    for t in titles: print(f"   - {t}")

    driver = AsyncGraphDatabase.driver(os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
    async with driver.session() as session:
        # Edges whose source_document is one of these titles
        r = await session.run("""
            MATCH ()-[r]->()
            WHERE r.source_document IN $titles
            RETURN r.source_document AS doc, collect(DISTINCT r.cpg_chunk_id) AS ids
        """, titles=titles)
        per_doc = {rec["doc"]: [i for i in rec["ids"] if i] async for rec in r}

        # Also: edges matched by the OLD broken filter
        r2 = await session.run("""
            MATCH ()-[r]->() WHERE r.source_document CONTAINS 'Dyslipidaemia'
            RETURN count(r) AS c
        """)
        old_filter_cnt = (await r2.single())["c"]

    print(f"\nOld cleanup filter (CONTAINS 'Dyslipidaemia') matches: {old_filter_cnt} edges")
    print("\nPer-section edge cpg_chunk_id resolution (proper title match):")
    all_ids, total_orph = set(), 0
    for doc, ids in sorted(per_doc.items()):
        uids = set(ids); all_ids |= uids
        rows = await pg.fetch("SELECT id FROM chunks WHERE id::text = ANY($1::text[])", list(uids))
        live = {str(x["id"]) for x in rows}
        orph = len(uids) - len(live)
        total_orph += orph
        flag = "  <-- ORPHANS" if orph else ""
        print(f"   {doc[:55]:55} {len(live)}/{len(uids)} resolve{flag}")
    print(f"\nTOTAL distinct ids: {len(all_ids)}, orphaned across sections: {total_orph}")
    await pg.close(); await driver.close()
asyncio.run(main())
