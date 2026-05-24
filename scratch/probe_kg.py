import sys, io, os, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from neo4j import AsyncGraphDatabase

PROBES = [
    "amlodipine", "lisinopril", "ramipril",
    "spironolactone", "hydrochlorothiazide", "hctz",
    "chronic kidney disease", "ckd", "renal impairment",
    "sulfa", "sulfonamide", "hypertension",
]

async def main():
    drv = AsyncGraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
    async with drv.session(database=os.getenv("NEO4J_DATABASE") or None) as s:
        print("=== Node counts ===")
        for lbl in ["Drug","Condition","AdverseEvent","RiskFactor","Procedure"]:
            r = await s.run(f"MATCH (n:{lbl}) RETURN count(n) AS c")
            rec = await r.single()
            print(f"  {lbl}: {rec['c']}")
        print("\n=== Edge type counts ===")
        r = await s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC LIMIT 30")
        async for rec in r:
            print(f"  {rec['t']}: {rec['c']}")

        print("\n=== Probe name_normalised lookups ===")
        for name in PROBES:
            r = await s.run("MATCH (n) WHERE n.name_normalised = $n RETURN labels(n)[0] AS lbl, n.name AS name LIMIT 3", n=name.lower())
            rows = [x async for x in r]
            print(f"  {name!r:35s} -> {rows}")

        print("\n=== CONTAINS search (partial) ===")
        for name in ["lisinopril","ramipril","spironolactone","hydrochlorothiazide","sulfa","kidney"]:
            r = await s.run("MATCH (n) WHERE toLower(n.name_normalised) CONTAINS $n RETURN labels(n)[0] AS lbl, n.name_normalised AS nn, n.name AS nm LIMIT 5", n=name.lower())
            rows = [(x['lbl'], x['nn']) async for x in r]
            print(f"  {name!r:25s} -> {rows}")

        print("\n=== Edges around a few key drugs ===")
        for d in ["spironolactone","lisinopril","ramipril","hydrochlorothiazide"]:
            r = await s.run(
                "MATCH (a)-[r]-(b) WHERE toLower(a.name_normalised) CONTAINS $d "
                "RETURN a.name_normalised AS a, type(r) AS rel, b.name_normalised AS b, r.severity AS sev LIMIT 8",
                d=d)
            rows = [(x['a'], x['rel'], x['b'], x['sev']) async for x in r]
            print(f"  {d}: {len(rows)} edges")
            for row in rows[:4]:
                print(f"    {row}")
    await drv.close()

asyncio.run(main())
