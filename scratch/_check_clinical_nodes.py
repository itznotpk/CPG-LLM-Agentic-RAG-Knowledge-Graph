"""Check why clinical_graph_lookup returns 0 flags for warfarin/digoxin/AF queries."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
load_dotenv()

TARGETS = ["warfarin", "digoxin", "amiodarone", "atrial fibrillation", "heart failure", "bleeding"]

async def main():
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    async with driver.session() as s:
        print("=== 1. Node existence check (name_normalised) ===")
        r = await s.run(
            "MATCH (n) WHERE n.name_normalised IN $names RETURN n.name_normalised AS name, labels(n) AS labels",
            names=TARGETS
        )
        found = await r.data()
        found_names = {rec["name"] for rec in found}
        for rec in found:
            print(f"  FOUND: {rec['name']} -> {rec['labels']}")
        for t in TARGETS:
            if t not in found_names:
                print(f"  MISSING: '{t}' — not in graph at all")

        print("\n=== 2. Edges on warfarin node ===")
        r2 = await s.run(
            "MATCH (n)-[r]-(m) WHERE n.name_normalised = 'warfarin' RETURN type(r) AS rel, m.name_normalised AS other LIMIT 10"
        )
        edges = await r2.data()
        if edges:
            for e in edges:
                print(f"  warfarin -[{e['rel']}]-> {e['other']}")
        else:
            print("  No edges on warfarin node")

        print("\n=== 3. Edges on digoxin node ===")
        r3 = await s.run(
            "MATCH (n)-[r]-(m) WHERE n.name_normalised = 'digoxin' RETURN type(r) AS rel, m.name_normalised AS other LIMIT 10"
        )
        edges3 = await r3.data()
        if edges3:
            for e in edges3:
                print(f"  digoxin -[{e['rel']}]-> {e['other']}")
        else:
            print("  No edges on digoxin node")

        print("\n=== 4. INTERACTS_WITH / CONTRAINDICATED_WITH edges on AF ===")
        r4 = await s.run(
            """MATCH (n)-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(m)
               WHERE n.name_normalised = 'atrial fibrillation'
               RETURN type(r) AS rel, m.name_normalised AS other LIMIT 10"""
        )
        edges4 = await r4.data()
        if edges4:
            for e in edges4:
                print(f"  atrial fibrillation -[{e['rel']}]-> {e['other']}")
        else:
            print("  No INTERACTS/CONTRAINDICATED edges on atrial fibrillation")

    await driver.close()

asyncio.run(main())
