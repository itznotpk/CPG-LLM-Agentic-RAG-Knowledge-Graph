"""Check Neo4j edges - are the 714 Breast Cancer edges still there?"""
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
URI = os.getenv('NEO4J_URI')
USER = os.getenv('NEO4J_USER')
PASSWORD = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session() as session:
    # Count ALL edges in Neo4j
    res = session.run("MATCH ()-[r]->() RETURN type(r) as rtype, count(r) as cnt ORDER BY cnt DESC")
    print("=== ALL Neo4j edges by type ===")
    total = 0
    for rec in res:
        print(f"  {rec['rtype']}: {rec['cnt']}")
        total += rec['cnt']
    print(f"  TOTAL: {total}")

    # Check cpg_chunk_ids on clinical edges
    print("\n=== Edges with cpg_chunk_ids property ===")
    res2 = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_ids IS NOT NULL
        RETURN type(r) as rtype, count(r) as cnt
        ORDER BY cnt DESC
    """)
    total2 = 0
    for rec in res2:
        print(f"  {rec['rtype']}: {rec['cnt']}")
        total2 += rec['cnt']
    print(f"  TOTAL with cpg_chunk_ids: {total2}")

    # Sample a cpg_chunk_id to see what it looks like
    print("\n=== Sample cpg_chunk_ids values ===")
    res3 = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_ids IS NOT NULL
        RETURN type(r) as rtype, r.cpg_chunk_ids as ids
        LIMIT 5
    """)
    for rec in res3:
        print(f"  {rec['rtype']}: {rec['ids']}")

driver.close()
