"""Phase A audit: severity coverage, evidence_list shape, new-relation usage."""
import os, asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


async def main():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    async with driver.session(database=NEO4J_DATABASE) as s:

        print("\n=== Severity coverage by relation type ===")
        q = """
        MATCH ()-[r]->()
        WITH type(r) AS rel, count(r) AS total,
             sum(CASE WHEN r.severity IS NOT NULL THEN 1 ELSE 0 END) AS with_sev
        WHERE rel IN ['INTERACTS_WITH','CONTRAINDICATED_WITH','REQUIRES_DOSE_ADJUSTMENT',
                      'CROSS_REACTS_WITH','REQUIRES_MONITORING','CAUSES','HAS_DOSAGE']
        RETURN rel, total, with_sev, round(100.0*with_sev/total,1) AS pct
        ORDER BY total DESC
        """
        async for r in await s.run(q):
            print(f"  {r['rel']:30s}  {r['with_sev']:3d}/{r['total']:3d}  ({r['pct']}%)")

        print("\n=== Severity value distribution ===")
        q = """
        MATCH ()-[r]->() WHERE r.severity IS NOT NULL
        RETURN r.severity AS sev, count(r) AS cnt ORDER BY cnt DESC
        """
        async for r in await s.run(q):
            print(f"  {r['sev']}: {r['cnt']}")

        print("\n=== evidence_list shape ===")
        q = """
        MATCH ()-[r]->() WHERE r.evidence_list IS NOT NULL
        WITH size(r.evidence_list) AS sz
        RETURN count(*) AS edges,
               min(sz) AS min, max(sz) AS max,
               avg(sz) AS mean,
               percentileCont(sz, 0.5) AS p50,
               percentileCont(sz, 0.95) AS p95
        """
        async for r in await s.run(q):
            print(f"  edges={r['edges']}  min={r['min']}  p50={r['p50']}  mean={r['mean']:.2f}  p95={r['p95']}  max={r['max']}")

        print("\n=== Top edges by evidence_list size (cross-CPG accumulation) ===")
        q = """
        MATCH (a)-[r]->(b) WHERE r.evidence_list IS NOT NULL
        RETURN a.name AS subj, type(r) AS rel, b.name AS obj,
               size(r.evidence_list) AS n_ev,
               size(coalesce(r.cpg_chunk_ids,[])) AS n_chunks
        ORDER BY n_ev DESC LIMIT 10
        """
        async for r in await s.run(q):
            print(f"  ({r['subj']}) -[{r['rel']}]-> ({r['obj']})  evidence={r['n_ev']}  chunks={r['n_chunks']}")

        print("\n=== Trigger / risk_pct population ===")
        q = """
        MATCH ()-[r]->()
        RETURN
          sum(CASE WHEN r.trigger IS NOT NULL THEN 1 ELSE 0 END) AS with_trigger,
          sum(CASE WHEN r.risk_pct IS NOT NULL THEN 1 ELSE 0 END) AS with_risk_pct
        """
        async for r in await s.run(q):
            print(f"  trigger populated: {r['with_trigger']}")
            print(f"  risk_pct populated: {r['with_risk_pct']}")

        print("\n=== Source document spread ===")
        q = """
        MATCH ()-[r]->()
        RETURN r.source_document AS doc, count(r) AS cnt
        ORDER BY cnt DESC
        """
        async for r in await s.run(q):
            print(f"  {r['cnt']:4d}  {r['doc']}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
