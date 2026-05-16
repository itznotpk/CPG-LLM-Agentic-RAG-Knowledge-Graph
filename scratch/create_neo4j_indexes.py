r"""
Create Neo4j indexes on name_normalised for all entity labels.
Run ONCE after deploying the name_normalised MERGE change.

Run: venv\Scripts\python.exe scratch\create_neo4j_indexes.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

# All entity labels used in graph_builder.py extraction
ENTITY_LABELS = [
    "Drug", "Condition", "Procedure", "DiagnosticTool",
    "AdverseEvent", "RiskFactor", "PatientProfile",
    "Dosage", "Organization", "Entity", "OTHER",
]


async def create_indexes():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=" * 60)
    print("CREATING Neo4j INDEXES ON name_normalised")
    print("=" * 60)

    async with driver.session(database=NEO4J_DATABASE) as session:
        for label in ENTITY_LABELS:
            index_name = f"idx_{label.lower()}_name_norm"
            cypher = f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON (n.name_normalised)"
            try:
                await session.run(cypher)
                print(f"  Created index: {index_name}")
            except Exception as e:
                print(f"  Index {index_name}: {e}")

        # Also verify indexes exist
        print("\nVerifying indexes...")
        result = await session.run("SHOW INDEXES YIELD name, labelsOrTypes, properties WHERE 'name_normalised' IN properties RETURN name, labelsOrTypes, properties")
        indexes = [r async for r in result]
        print(f"  Found {len(indexes)} name_normalised indexes:")
        for idx in indexes:
            print(f"    {idx['name']}: {idx['labelsOrTypes']} on {idx['properties']}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())
