# -*- coding: utf-8 -*-
"""Step 2: Neo4j cleanup of stale Breast Cancer edges."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

print("PostgreSQL: already cleaned (13 docs, 66 chunks deleted)")

# Get all CURRENT chunk IDs from Postgres (all remaining CPGs)
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SELECT id::text FROM chunks")
all_current_ids = set(r[0] for r in cur.fetchall())
print(f"Current Postgres chunk IDs (all CPGs): {len(all_current_ids)}")
conn.close()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    # Count edges with stale cpg_chunk_ids
    res = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_id IS NOT NULL
        RETURN r.cpg_chunk_id AS cid
    """)
    stale_ids = []
    valid_count = 0
    for rec in res:
        if rec['cid'] in all_current_ids:
            valid_count += 1
        else:
            stale_ids.append(rec['cid'])

    stale_set = set(stale_ids)
    print(f"Edges with valid cpg_chunk_id (other CPGs): {valid_count}")
    print(f"Edges with STALE cpg_chunk_id (Breast Cancer old): {len(stale_ids)} ({len(stale_set)} unique)")

    if stale_ids:
        res2 = session.run("""
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_id IN $stale_ids
            DELETE r
            RETURN count(r) as deleted
        """, stale_ids=list(stale_set))
        deleted = res2.single()['deleted']
        print(f"Deleted {deleted} stale edges from Neo4j")

    # Clean up orphan nodes
    res3 = session.run("""
        MATCH (n)
        WHERE n.name IS NOT NULL AND NOT (n)-[]-()
        RETURN count(n) as orphans
    """)
    orphans = res3.single()['orphans']
    print(f"Orphan nodes (no edges): {orphans}")
    if orphans > 0:
        session.run("MATCH (n) WHERE n.name IS NOT NULL AND NOT (n)-[]-() DELETE n")
        print(f"Deleted {orphans} orphan nodes")

    # Final counts
    res4 = session.run("MATCH ()-[r]->() RETURN count(r) as total")
    res5 = session.run("MATCH (n) RETURN count(n) as total")
    print(f"\nFinal Neo4j state: {res5.single()['total']} nodes, {res4.single()['total']} edges")

driver.close()
print("\nCLEANUP COMPLETE - Ready for fresh Breast Cancer ingestion")
