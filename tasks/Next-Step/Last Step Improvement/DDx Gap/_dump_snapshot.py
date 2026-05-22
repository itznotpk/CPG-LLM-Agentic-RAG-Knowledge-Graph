"""Regenerate ddx_routing_p0_documents_scope_snapshot.json from live Neon."""
import asyncio, os, json
import asyncpg
from dotenv import load_dotenv

load_dotenv()
OUT = os.path.join(os.path.dirname(__file__), "ddx_routing_p0_documents_scope_snapshot.json")

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        rows = await conn.fetch(
            "SELECT title, icd11_scope, scope_verified "
            "FROM documents ORDER BY title")
        data = [
            {
                "title": r["title"],
                "icd11_scope": list(r["icd11_scope"]) if r["icd11_scope"] else [],
                "scope_verified": bool(r["scope_verified"]),
            }
            for r in rows
        ]
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(data)} rows to {OUT}")
    finally:
        await conn.close()

asyncio.run(main())
