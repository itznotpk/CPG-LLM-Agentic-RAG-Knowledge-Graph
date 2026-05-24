"""Dry-run count + sample of KG edges whose evidence is comparison-table-row noise.

Pass --delete to actually remove them.
"""
import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agent.graph_clinical import _get_neo4j_session

PATTERN = r"(?s).*(?:\|\s*[+\-]{1,3}\$?\s*){3,}.*"


async def main(delete: bool):
    session_ctx = await _get_neo4j_session()
    async with session_ctx as s:
        res = await s.run(
            "MATCH ()-[r]->() WHERE r.evidence =~ $p RETURN count(r) AS c",
            p=PATTERN,
        )
        total = (await res.single())["c"]
        print(f"Matched edges: {total}")

        res = await s.run(
            "MATCH ()-[r]->() WHERE r.evidence =~ $p "
            "RETURN type(r) AS rel, count(*) AS c ORDER BY c DESC",
            p=PATTERN,
        )
        rows = [r async for r in res]
        print("\nBy relation type:")
        for row in rows:
            print(f"  {row['rel']:30s} {row['c']}")

        res = await s.run(
            "MATCH (a)-[r]->(b) WHERE r.evidence =~ $p "
            "RETURN a.name AS subj, type(r) AS rel, b.name AS obj, "
            "substring(r.evidence, 0, 120) AS ev LIMIT 10",
            p=PATTERN,
        )
        sample = [r async for r in res]
        print("\nSample (up to 10):")
        for row in sample:
            print(f"  ({row['subj']}) -[{row['rel']}]-> ({row['obj']})")
            print(f"    evidence: {row['ev']}")

        if delete:
            print("\n--- DELETING ---")
            res = await s.run(
                "MATCH ()-[r]->() WHERE r.evidence =~ $p DELETE r RETURN count(*) AS c",
                p=PATTERN,
            )
            row = await res.single()
            print(f"Deleted: {row['c']}")
        else:
            print("\n(dry-run; pass --delete to remove)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.delete))
