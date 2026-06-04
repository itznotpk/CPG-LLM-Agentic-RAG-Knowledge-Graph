"""Diagnostic for Gap 1: why aren't warfarin x fluconazole / amiodarone
DDIs surfacing as `source="graph"` safety flags in case 09?

Queries Neo4j directly to check:
  1. Drug nodes exist with the expected names.
  2. INTERACTS_WITH edges connect them.
  3. Edges carry a severity property.
  4. The Cypher used by `_kg_verify_plan` would actually match them.

Run:  python scripts/inspect_kg_warfarin_ddis.py
"""
from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

URI  = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PWD  = os.environ["NEO4J_PASSWORD"]

DRUGS = ["Warfarin", "Fluconazole", "Amiodarone", "Aspirin", "Clopidogrel"]


async def main() -> None:
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PWD))
    async with driver.session() as sess:
        print("=" * 78)
        print("1. Drug nodes — case-insensitive name match")
        print("=" * 78)
        for name in DRUGS:
            res = await sess.run(
                "MATCH (d:Drug) WHERE toLower(d.name) CONTAINS toLower($n) "
                "RETURN d.name AS name LIMIT 5",
                n=name,
            )
            rows = await res.data()
            print(f"  {name:14} → {[r['name'] for r in rows] or 'NOT FOUND'}")

        print()
        print("=" * 78)
        print("2. INTERACTS_WITH edges between target drugs (any direction)")
        print("=" * 78)
        for a, b in [
            ("Warfarin", "Fluconazole"),
            ("Warfarin", "Amiodarone"),
            ("Warfarin", "Aspirin"),
            ("Amiodarone", "Fluconazole"),
            ("Amiodarone", "Clopidogrel"),
        ]:
            res = await sess.run(
                """
                MATCH (a:Drug)-[r:INTERACTS_WITH]-(b:Drug)
                 WHERE toLower(a.name) CONTAINS toLower($a)
                   AND toLower(b.name) CONTAINS toLower($b)
                RETURN a.name AS a, b.name AS b,
                       properties(r) AS props
                LIMIT 5
                """,
                a=a, b=b,
            )
            rows = await res.data()
            if not rows:
                print(f"  {a:11} x {b:14} → NO EDGE")
            else:
                for row in rows:
                    print(f"  {row['a']:11} x {row['b']:14} → {row['props']}")

        print()
        print("=" * 78)
        print("3. All INTERACTS_WITH edges touching Warfarin (top 20)")
        print("=" * 78)
        res = await sess.run(
            """
            MATCH (w:Drug)-[r:INTERACTS_WITH]-(o:Drug)
             WHERE toLower(w.name) CONTAINS 'warfarin'
            RETURN o.name AS other, properties(r) AS props
            LIMIT 20
            """
        )
        rows = await res.data()
        if not rows:
            print("  (none)")
        for row in rows:
            sev = row["props"].get("severity", "?")
            evi = (row["props"].get("evidence") or "")[:60]
            print(f"  warfarin x {row['other']:30} severity={sev:10} ev={evi}")

        print()
        print("=" * 78)
        print("4. Edge property keys observed on INTERACTS_WITH")
        print("=" * 78)
        res = await sess.run(
            """
            MATCH ()-[r:INTERACTS_WITH]->()
            UNWIND keys(r) AS k
            RETURN DISTINCT k ORDER BY k
            """
        )
        rows = await res.data()
        print(f"  keys: {[r['k'] for r in rows]}")

        print()
        print("=" * 78)
        print("5. Total counts")
        print("=" * 78)
        for label, q in [
            ("Drug nodes",      "MATCH (d:Drug) RETURN count(d) AS n"),
            ("INTERACTS_WITH",  "MATCH ()-[r:INTERACTS_WITH]->() RETURN count(r) AS n"),
        ]:
            res = await sess.run(q)
            row = await res.single()
            print(f"  {label:18} = {row['n']}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
