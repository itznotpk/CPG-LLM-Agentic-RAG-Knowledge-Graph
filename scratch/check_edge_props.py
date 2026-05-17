"""Check which cpg_chunk property edges actually have."""
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)
with driver.session() as session:
    # Check cpg_chunk_id (singular)
    res = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_id IS NOT NULL
        RETURN count(r) as cnt
    """)
    print(f"Edges with cpg_chunk_id (singular): {res.single()['cnt']}")

    # Check cpg_chunk_ids (plural)
    res2 = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_ids IS NOT NULL
        RETURN count(r) as cnt
    """)
    print(f"Edges with cpg_chunk_ids (plural): {res2.single()['cnt']}")

    # Sample a few edges to see BOTH properties
    res3 = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_ids IS NOT NULL
        RETURN type(r) as rtype, r.cpg_chunk_id as singular, r.cpg_chunk_ids as plural
        LIMIT 3
    """)
    print("\nSample edges:")
    for rec in res3:
        print(f"  {rec['rtype']}: singular={rec['singular']}, plural={rec['plural']}")

driver.close()
