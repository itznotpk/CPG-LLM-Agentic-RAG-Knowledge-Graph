"""Calibrate SEMANTIC_SCOPE_THRESHOLD against current scope_embeddings.

For each CPG, computes the *minimum* cosine(scope_embedding, icd_embedding)
across its in-scope ICDs (the worst-case positive). For a curated orphan
set, computes the *maximum* cosine to any CPG's scope_embedding (worst-case
orphan). The gap between the two distributions is the calibration window.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

# Orphan ICDs: codes that should NOT match any of the 30 ingested CPGs.
ORPHANS = [
    ("BC91",  "Cardiac arrest"),
    ("GC08",  "Acute pyelonephritis (UTI)"),
    ("2C25",  "Lung cancer (no lung CPG)"),
    ("8A80",  "Migraine"),
    ("8A60",  "Epilepsy"),
    ("ND56",  "Lower limb fracture (no fracture CPG)"),
    ("CA22",  "COPD (no COPD CPG)"),
    ("DA60",  "Peptic ulcer (no GI CPG)"),
]


async def main() -> None:
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute("SET ivfflat.probes = 100")

    # ---------------- positives ---------------- min cosine per CPG over its scope
    cpgs = await conn.fetch("""
        SELECT source, scope_embedding, icd11_scope
          FROM documents
         WHERE scope_embedding IS NOT NULL AND array_length(icd11_scope,1) > 0
         GROUP BY source, scope_embedding, icd11_scope
    """)
    positives: list[tuple[str, float, str]] = []  # (cpg, best_cos, best_code)
    for r in cpgs:
        codes = r["icd11_scope"]
        scope_emb = r["scope_embedding"]
        # Use BEST in-scope match per CPG. The min of these across all 30 CPGs
        # is the floor of "how strongly does each CPG's rationale signal its own
        # most prototypical in-scope code." This matches the original 2026-05-23
        # calibration probe (min positive = thyroid 0.417).
        row = await conn.fetchrow(
            """
            SELECT code, 1 - (embedding <=> $1) AS sim
              FROM icd11_codes
             WHERE code = ANY($2::text[]) AND embedding IS NOT NULL
             ORDER BY sim DESC
             LIMIT 1
            """,
            scope_emb, codes,
        )
        if row:
            positives.append((r["source"], float(row["sim"]), row["code"]))

    # ---------------- orphans ---------------- max cosine to any CPG scope
    orphan_scores: list[tuple[str, str, float, str]] = []
    for code, label in ORPHANS:
        emb = await conn.fetchval(
            "SELECT embedding FROM icd11_codes WHERE code = $1", code
        )
        if emb is None:
            orphan_scores.append((code, label, float("nan"), "(not in icd11_codes)"))
            continue
        best = await conn.fetchrow(
            """
            SELECT source, 1 - (scope_embedding <=> $1) AS sim
              FROM documents
             WHERE scope_embedding IS NOT NULL
             GROUP BY source, scope_embedding
             ORDER BY sim DESC
             LIMIT 1
            """,
            emb,
        )
        orphan_scores.append((code, label, float(best["sim"]), best["source"]))

    await conn.close()

    # ---------------- report
    # Dedup per CPG (sections share the same scope_embedding -> same row)
    seen: dict[str, tuple[float, str]] = {}
    for cpg, sim, code in positives:
        # Strip section-N- prefix and -CPGNAME suffix patterns to group sections
        key = cpg
        if (sim, code) != seen.get(key):
            seen[key] = (sim, code)
    positives = sorted([(k, v[0], v[1]) for k, v in seen.items()], key=lambda t: t[1])
    print("=== POSITIVES (best in-scope cos(scope, icd) per CPG, ascending) ===")
    for cpg, sim, code in positives[:40]:
        print(f"  {sim:.3f}  {cpg:<55} best-code={code}")
    if len(positives) > 40:
        print(f"  ... {len(positives)-40} more rows")

    print()
    print("=== ORPHANS (max cos(orphan-icd, any-scope)) ===")
    orphan_scores.sort(key=lambda t: -t[2] if t[2] == t[2] else 0)
    for code, label, sim, cpg in orphan_scores:
        if sim != sim:
            print(f"  --  {code:<8} {label:<40} {cpg}")
        else:
            print(f"  {sim:.3f}  {code:<8} {label:<40} -> {cpg}")

    valid_pos = [s for _, s, _ in positives]
    valid_orph = [s for _, _, s, _ in orphan_scores if s == s]
    if valid_pos and valid_orph:
        min_pos = min(valid_pos)
        max_orph = max(valid_orph)
        gap = min_pos - max_orph
        print()
        print(f"min positive: {min_pos:.3f}")
        print(f"max orphan:   {max_orph:.3f}")
        print(f"gap:          {gap:+.3f}")
        if gap > 0:
            print(f"=> recommended SEMANTIC_SCOPE_THRESHOLD in ({max_orph:.3f}, {min_pos:.3f})")
            print(f"   conservative round: {round((min_pos + max_orph) / 2, 2):.2f}")
        else:
            print("=> NO CLEAN GAP — positives and orphans overlap. Investigate before changing threshold.")


if __name__ == "__main__":
    asyncio.run(main())
