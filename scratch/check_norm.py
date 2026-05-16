"""Check if the re-ingestion applied name_normalised correctly."""
import asyncio, os
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
load_dotenv()

async def check():
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    session = driver.session(database=os.getenv("NEO4J_DATABASE"))

    # 1. Nodes with name_normalised (new schema)
    r = await session.run("MATCH (n) WHERE n.name_normalised IS NOT NULL RETURN count(n) AS cnt")
    d = await r.single()
    print(f"Nodes WITH name_normalised (new):    {d['cnt']}")

    # 2. Nodes without name_normalised (old schema)
    r2 = await session.run("MATCH (n) WHERE n.name_normalised IS NULL AND n.name IS NOT NULL RETURN count(n) AS cnt")
    d2 = await r2.single()
    print(f"Nodes WITHOUT name_normalised (old):  {d2['cnt']}")

    # 3. Total edges
    r3 = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
    d3 = await r3.single()
    print(f"Total edges:                          {d3['cnt']}")

    # 4. Sample new nodes
    r4 = await session.run("MATCH (n) WHERE n.name_normalised IS NOT NULL RETURN n.name AS name, n.name_normalised AS norm, labels(n) AS labels LIMIT 5")
    records = [rec async for rec in r4]
    print("\nSample new nodes:")
    for rec in records:
        print(f"  {rec['labels']}: name={rec['name']}, name_normalised={rec['norm']}")

    # 5. Sample old nodes (if any)
    r5 = await session.run("MATCH (n) WHERE n.name_normalised IS NULL AND n.name IS NOT NULL RETURN n.name AS name, labels(n) AS labels LIMIT 5")
    old = [rec async for rec in r5]
    if old:
        print("\nSample OLD nodes (missing name_normalised):")
        for rec in old:
            print(f"  {rec['labels']}: name={rec['name']}")
    else:
        print("\nNo old nodes — all nodes have name_normalised!")

    await session.close()
    await driver.close()

asyncio.run(check())
