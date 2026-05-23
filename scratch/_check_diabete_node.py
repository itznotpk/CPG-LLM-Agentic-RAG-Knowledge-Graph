"""Check the truncated 'Diabete' node from KG-5 output."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
load_dotenv()

async def main():
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    async with driver.session() as s:
        print("=== Nodes with name starting 'Diabete' (not 'Diabetes') ===")
        r = await s.run(
            "MATCH (n) WHERE n.name STARTS WITH 'Diabete' AND NOT n.name STARTS WITH 'Diabetes' "
            "RETURN n.name AS name, n.name_normalised AS norm, labels(n) AS labels"
        )
        recs = await r.data()
        if not recs:
            print("  None found — 'Diabete' may be a display truncation only.")
        for rec in recs:
            print(f"  name='{rec['name']}' | norm='{rec['norm']}' | labels={rec['labels']}")

        print("\n=== Edges on any 'Diabete*' node ===")
        r2 = await s.run(
            "MATCH (n)-[r]->(m) WHERE n.name STARTS WITH 'Diabete' AND NOT n.name STARTS WITH 'Diabetes' "
            "RETURN n.name AS subj, type(r) AS rel, m.name AS obj, r.source_document AS src LIMIT 10"
        )
        recs2 = await r2.data()
        for rec in recs2:
            print(f"  ({rec['subj']}) -[{rec['rel']}]-> ({rec['obj']})  | src: {rec['src']}")

        print("\n=== Does 'Diabetes' (full) node exist too? ===")
        r3 = await s.run(
            "MATCH (n) WHERE n.name_normalised = 'diabetes' "
            "RETURN n.name AS name, labels(n) AS labels LIMIT 5"
        )
        recs3 = await r3.data()
        for rec in recs3:
            print(f"  name='{rec['name']}' | labels={rec['labels']}")

    await driver.close()

asyncio.run(main())
