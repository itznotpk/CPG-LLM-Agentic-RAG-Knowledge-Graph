"""Audit REQUIRES_REFERRAL edges for low-quality triples."""
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from neo4j import AsyncGraphDatabase

async def main():
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    async with driver.session() as s:
        # Counts
        r = await s.run("MATCH ()-[r:REQUIRES_REFERRAL]->() RETURN count(r) AS n")
        total = (await r.single())["n"]
        print(f"Total REQUIRES_REFERRAL edges: {total}")

        # By specialty
        r = await s.run("""
            MATCH (c:Condition)-[r:REQUIRES_REFERRAL]->(s:Specialty)
            RETURN s.name AS specialty, count(r) AS n ORDER BY n DESC
        """)
        print("\nBy specialty:")
        async for rec in r:
            print(f"  {rec['specialty']}: {rec['n']}")

        # Low-quality candidates
        print("\n--- Low-quality candidates ---")
        r = await s.run("""
            MATCH (c:Condition)-[r:REQUIRES_REFERRAL]->(s:Specialty)
            WHERE r.trigger IN ['None','none','null','N/A','n/a','']
               OR r.evidence IS NULL
               OR size(r.evidence) < 20
               OR c.name_normalised IS NULL
               OR size(c.name_normalised) < 4
            RETURN c.name AS condition, s.name AS specialty,
                   r.urgency AS urgency, r.trigger AS trigger,
                   substring(coalesce(r.evidence,''),0,80) AS evidence,
                   c.name_normalised AS norm
            LIMIT 50
        """)
        bad = 0
        async for rec in r:
            bad += 1
            print(f"  [{rec['specialty']}] {rec['condition']!r} | norm={rec['norm']!r} | trigger={rec['trigger']!r} | ev={rec['evidence']!r}")
        print(f"\nLow-quality count: {bad}")

        # Distinct conditions
        r = await s.run("""
            MATCH (c:Condition)-[:REQUIRES_REFERRAL]->()
            RETURN c.name AS n, c.name_normalised AS norm ORDER BY norm
        """)
        print("\n--- All referral source Conditions ---")
        async for rec in r:
            print(f"  {rec['norm']!r}  ({rec['n']!r})")
    await driver.close()

asyncio.run(main())
