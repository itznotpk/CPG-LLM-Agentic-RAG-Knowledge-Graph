import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("""
    SELECT d.source, c.chunk_level, COUNT(c.id) 
    FROM documents d
    LEFT JOIN chunks c ON d.id = c.document_id
    GROUP BY d.source, c.chunk_level
    ORDER BY d.source, c.chunk_level;
""")
print("Chunks per document in DB:")
for row in cur.fetchall():
    print(row)
