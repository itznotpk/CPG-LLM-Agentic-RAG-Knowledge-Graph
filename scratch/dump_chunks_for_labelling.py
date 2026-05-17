"""Dump all chunks for the 5 ingested CPGs to a text file so we can label gold by hand."""
import asyncio, os, json
from dotenv import load_dotenv
load_dotenv()
import asyncpg

CPGS = [
    "Atrial-Fibrillation(2012)",
    "Cancer-Pain(2nd Edition)",
    "Patient-Safety-Minimal-Monitoring",
    "Pre-Anaesthetic-Assessment",
    "Anaesthesia-Medication-Safety",
]

OUT = "scratch/chunk_dump.txt"

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    lines = []
    for cpg in CPGS:
        lines.append("\n" + "="*80)
        lines.append(f"CPG: {cpg}")
        lines.append("="*80)
        rows = await conn.fetch(
            """
            SELECT c.id::text, c.chunk_level,
                   c.metadata->>'source' AS source,
                   c.metadata->>'title' AS title,
                   c.metadata->>'h2_title' AS h2_title,
                   c.metadata->>'context_path' AS context_path,
                   LEFT(c.content, 220) AS preview
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE d.metadata->>'cpg_name' = $1
              AND c.embedding IS NOT NULL
            ORDER BY c.metadata->>'source', c.chunk_level, c.metadata->>'h2_title'
            """, cpg
        )
        current_source = None
        for r in rows:
            if r["source"] != current_source:
                current_source = r["source"]
                lines.append(f"\n--- file: {current_source} ---")
            label = r["h2_title"] or r["title"] or ""
            cp = (r["context_path"] or "")[:80]
            preview = (r["preview"] or "").replace("\n", " ")
            lines.append(f"  {r['id']}  [{r['chunk_level']:8s}]  {label[:60]!r}")
            lines.append(f"      ctx: {cp}")
            lines.append(f"      prev: {preview[:200]}")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {len(rows)} rows (last cpg) | total lines: {len(lines)} -> {OUT}")
    await conn.close()

asyncio.run(main())
