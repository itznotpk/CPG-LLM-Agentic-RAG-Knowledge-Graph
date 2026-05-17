from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
URI = os.getenv('NEO4J_URI')
USER = os.getenv('NEO4J_USER')
PASSWORD = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session() as session:
    res1 = session.run('MATCH (e:Episodic) DETACH DELETE e RETURN count(e) as count')
    count1 = res1.single()['count']
    res2 = session.run('MATCH (e:Entity) DETACH DELETE e RETURN count(e) as count')
    count2 = res2.single()['count']
    print(f"Deleted {count1} Episodic nodes and {count2} Entity nodes.")
