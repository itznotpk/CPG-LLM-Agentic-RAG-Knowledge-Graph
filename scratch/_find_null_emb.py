import os, sys
from dotenv import load_dotenv
import psycopg2

# Force stdout to UTF-8 so we see the real characters
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("""
    SELECT c.id, c.content
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.id = '39c4c0b0-ea19-4a33-b762-56a2eaef94f0'
""")
row = cur.fetchone()
content = row[1]
print(f"id={row[0]}")
print(f"len={len(content)} chars")
print("--- content ---")
print(content)
print("--- end ---")

# Look for any U+FFFD (real replacement char) or other control/odd chars
bad = [(i, ch, hex(ord(ch))) for i, ch in enumerate(content) if ord(ch) == 0xFFFD]
print(f"\nU+FFFD count: {len(bad)}")
for b in bad[:5]:
    print(b)
