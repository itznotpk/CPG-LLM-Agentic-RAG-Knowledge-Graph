"""
Knowledge Graph Verification Script
Run: venv\Scripts\python.exe scratch\kg_verify.py

Checks:
  1. Node count & types
  2. Relationship count & types
  3. Evidence text quality (non-empty)
  4. cpg_chunk_id linkage to PostgreSQL
  5. Orphan nodes (no relationships)
  6. Duplicate triple detection
  7. Spot-check: sample triples for manual review
"""

import os
import asyncio
import psycopg2
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
DATABASE_URL = os.getenv("DATABASE_URL")


async def run_checks():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=" * 60)
    print("KNOWLEDGE GRAPH VERIFICATION REPORT")
    print("=" * 60)
    issues = []

    async with driver.session(database=NEO4J_DATABASE) as session:

        # -- [CHECK 1] Node count & types --
        print("\n[CHECK 1] Node counts by label")
        result = await session.run(
            "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt ORDER BY cnt DESC"
        )
        records = [r async for r in result]
        total_nodes = 0
        for r in records:
            label = ", ".join(r["labels"]) or "(unlabelled)"
            cnt = r["cnt"]
            total_nodes += cnt
            print(f"   {label}: {cnt}")
        print(f"   TOTAL: {total_nodes}")
        if total_nodes == 0:
            issues.append(" No nodes found  graph is empty!")

        #  [CHECK 2] Relationship count & types 
        print("\n [CHECK 2] Relationship counts by type")
        result = await session.run(
            "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt ORDER BY cnt DESC"
        )
        records = [r async for r in result]
        total_rels = 0
        for r in records:
            total_rels += r["cnt"]
            print(f"   {r['rel_type']}: {r['cnt']}")
        print(f"   TOTAL: {total_rels}")
        if total_rels == 0:
            issues.append(" No relationships found  graph has no edges!")

        #  [CHECK 3] Evidence quality 
        print("\n [CHECK 3] Evidence text quality")
        result = await session.run(
            """
            MATCH ()-[r]->()
            WITH count(r) AS total,
                 sum(CASE WHEN r.evidence IS NULL OR trim(r.evidence) = '' THEN 1 ELSE 0 END) AS missing
            RETURN total, missing
            """
        )
        rec = await result.single()
        if rec:
            total, missing = rec["total"], rec["missing"]
            pct = (missing / total * 100) if total > 0 else 0
            print(f"   Total edges: {total}")
            print(f"   Missing evidence: {missing} ({pct:.1f}%)")
            if pct > 20:
                issues.append(f"  {pct:.1f}% of edges have no evidence text")

        #  [CHECK 4] cpg_chunk_id linkage 
        print("\n [CHECK 4] cpg_chunk_id linkage to PostgreSQL")
        result = await session.run(
            """
            MATCH ()-[r]->()
            WITH count(r) AS total,
                 sum(CASE WHEN r.cpg_chunk_id IS NOT NULL THEN 1 ELSE 0 END) AS linked
            RETURN total, linked
            """
        )
        rec = await result.single()
        if rec:
            total, linked = rec["total"], rec["linked"]
            print(f"   Edges with cpg_chunk_id: {linked}/{total}")
            if linked > 0 and DATABASE_URL:
                # Spot-check: do those UUIDs exist in PostgreSQL?
                sample_result = await session.run(
                    "MATCH ()-[r]->() WHERE r.cpg_chunk_id IS NOT NULL RETURN r.cpg_chunk_id AS cid LIMIT 10"
                )
                sample_ids = [r["cid"] async for r in sample_result]
                try:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    found = 0
                    for cid in sample_ids:
                        cur.execute("SELECT 1 FROM chunks WHERE id = %s::uuid", (cid,))
                        if cur.fetchone():
                            found += 1
                    print(f"   PG cross-check ({len(sample_ids)} sampled): {found} found, {len(sample_ids) - found} missing")
                    if found < len(sample_ids):
                        issues.append(f"  {len(sample_ids) - found}/{len(sample_ids)} sampled cpg_chunk_ids missing in PostgreSQL")
                    conn.close()
                except Exception as e:
                    print(f"   PG cross-check failed: {e}")

        #  [CHECK 5] Orphan nodes 
        print("\n [CHECK 5] Orphan nodes (no relationships)")
        result = await session.run(
            "MATCH (n) WHERE NOT (n)--() RETURN labels(n) AS labels, n.name AS name LIMIT 10"
        )
        orphans = [r async for r in result]
        result2 = await session.run(
            "MATCH (n) WHERE NOT (n)--() RETURN count(n) AS cnt"
        )
        orphan_count = (await result2.single())["cnt"]
        print(f"   Orphan nodes: {orphan_count}")
        if orphan_count > 0:
            for o in orphans[:5]:
                print(f"     - {', '.join(o['labels'])}: {o['name']}")
            if orphan_count > 5:
                print(f"     ... and {orphan_count - 5} more")
            issues.append(f"  {orphan_count} orphan nodes with no relationships")

        #  [CHECK 6] Duplicate detection 
        print("\n [CHECK 6] Duplicate triple detection")
        result = await session.run(
            """
            MATCH (s)-[r]->(o)
            WITH s.name AS subj, type(r) AS rel, o.name AS obj, count(*) AS cnt
            WHERE cnt > 1
            RETURN subj, rel, obj, cnt ORDER BY cnt DESC LIMIT 10
            """
        )
        dupes = [r async for r in result]
        if dupes:
            print(f"   Found {len(dupes)} duplicate triple patterns:")
            for d in dupes[:5]:
                print(f"     ({d['subj']}) -[{d['rel']}]-> ({d['obj']}) x{d['cnt']}")
            issues.append(f"  {len(dupes)} duplicate triple patterns found")
        else:
            print("   No duplicates found ")

        #  [CHECK 7] Sample triples for manual review 
        print("\n [CHECK 7] Sample triples (for manual review)")
        result = await session.run(
            """
            MATCH (s)-[r]->(o)
            RETURN labels(s)[0] AS s_type, s.name AS subject,
                   type(r) AS relation,
                   labels(o)[0] AS o_type, o.name AS object,
                   left(r.evidence, 100) AS evidence
            LIMIT 10
            """
        )
        samples = [r async for r in result]
        for s in samples:
            print(f"   [{s['s_type']}] {s['subject']}")
            print(f"     --{s['relation']}--> [{s['o_type']}] {s['object']}")
            if s["evidence"]:
                print(f"     Evidence: \"{s['evidence']}...\"")
            print()

    #  SUMMARY 
    print("=" * 60)
    if issues:
        print(f"  ISSUES FOUND: {len(issues)}")
        for issue in issues:
            print(f"   {issue}")
    else:
        print(" ALL CHECKS PASSED  Knowledge graph looks healthy!")
    print("=" * 60)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(run_checks())
