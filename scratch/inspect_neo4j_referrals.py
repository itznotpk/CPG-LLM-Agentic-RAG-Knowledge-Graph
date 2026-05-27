import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

async def main():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    db = os.getenv("NEO4J_DATABASE") or None
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    async with driver.session(database=db) as session:
        cypher = """
        MATCH (c:Condition)-[r:REQUIRES_REFERRAL]->(s:Specialty)
        RETURN c.name AS condition, s.name AS specialty, r.urgency AS urgency, r.source_document AS source_doc
        LIMIT 20
        """
        result = await session.run(cypher)
        print("=== NEO4J REFERRAL SOURCE DOCUMENTS ===")
        async for record in result:
            print(f"Condition: {record['condition']:30s} | Specialty: {record['specialty']:20s} | Source: {record['source_doc']}")
            
    await driver.close()

if __name__ == '__main__':
    asyncio.run(main())
