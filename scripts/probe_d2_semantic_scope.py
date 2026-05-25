"""D2 semantic_scope gate probe.

Stress-tests SEMANTIC_SCOPE_THRESHOLD = 0.32 in both directions:
  (A) Full-pipeline probe via find_cpgs_for_code — confirms the production
      routing path returns the expected route_method per code.
  (B) Raw D2-only probe via _semantic_scope_match — bypasses D1 to exercise
      the gate directly: for each code, report best similarity + accept/reject.

Positive cases  : ICD codes that should route (either via D1 or, if D1 misses,
                  via D2 above threshold).
Negative cases  : orphan ICD codes that should land at out_of_scope (D2 best
                  similarity must be < threshold).

Usage:
    python scripts/probe_d2_semantic_scope.py
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

from agent.routing import (  # noqa: E402
    SEMANTIC_SCOPE_THRESHOLD,
    _semantic_scope_match,
    find_cpgs_for_code,
)

# (code, label, expected_outcome). expected_outcome ∈ {"route", "out_of_scope"}.
POSITIVES: list[tuple[str, str]] = [
    ("BA41.1",  "Acute NSTEMI — should route to CAD / CVD"),
    ("BD11.0",  "HF with reduced EF — should route to Heart-Failure"),
    ("8B11.0",  "Cerebral ischaemic stroke subtype — should route to Stroke"),
    ("2C61.0",  "Invasive ductal carcinoma — should route to Breast-Cancer"),
    ("9B71.01", "Proliferative diabetic retinopathy — should route to T2DM"),
]

ORPHANS: list[tuple[str, str]] = [
    ("8A80", "Migraine — no neurology CPG"),
    ("8A60", "Epilepsy — no neurology CPG"),
    ("GC08", "UTI — no genitourinary CPG"),
    ("BC91", "Cardiac arrest — no resuscitation CPG"),
    ("CA22", "COPD — no respiratory CPG"),
    ("DA60", "Peptic ulcer — no GI CPG"),
]


def _fmt_sim(sim: float | None) -> str:
    return f"{sim:.3f}" if sim is not None else "  n/a"


async def probe_full_pipeline(conn, code: str) -> tuple[str, list[str]]:
    refs, method = await find_cpgs_for_code(code, conn)
    cpgs = sorted({r.cpg_name for r in refs})
    return method, cpgs


async def probe_d2_only(conn, code: str) -> tuple[float | None, str | None]:
    """Force the D2 gate: return best cosine + chosen CPG (None if gated out)."""
    # _semantic_scope_match itself enforces the threshold and returns []
    # if the best score is < SEMANTIC_SCOPE_THRESHOLD. To probe both above and
    # below cleanly we look up the best raw similarity ourselves.
    emb = await conn.fetchval(
        "SELECT embedding FROM icd11_codes WHERE code = $1", code
    )
    if emb is None:
        return None, "(code not in icd11_codes)"
    row = await conn.fetchrow(
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
    return float(row["sim"]), row["source"]


async def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL missing from .env")
    conn = await asyncpg.connect(db_url)
    await conn.execute("SET ivfflat.probes = 100")

    print(f"SEMANTIC_SCOPE_THRESHOLD = {SEMANTIC_SCOPE_THRESHOLD}\n")

    failures = 0

    print("=== POSITIVES (must route to some CPG) ===")
    print(f"{'code':<10} {'route_method':<18} {'best D2 sim':<12} {'D2 best CPG':<48} {'pipeline CPGs'}")
    for code, label in POSITIVES:
        method, cpgs = await probe_full_pipeline(conn, code)
        sim, d2_cpg = await probe_d2_only(conn, code)
        ok = method != "out_of_scope"
        mark = "OK " if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{mark}] {code:<8} {method:<18} {_fmt_sim(sim):<12} {(d2_cpg or '-'):<48} {cpgs}")
        print(f"         label: {label}")

    print()
    print("=== ORPHANS (must land at out_of_scope; D2 best < threshold) ===")
    print(f"{'code':<10} {'route_method':<18} {'best D2 sim':<12} {'D2 best CPG':<48}")
    for code, label in ORPHANS:
        method, cpgs = await probe_full_pipeline(conn, code)
        sim, d2_cpg = await probe_d2_only(conn, code)
        # Two checks: pipeline must say out_of_scope, AND raw D2 sim must be < threshold.
        pipeline_ok = method == "out_of_scope"
        gate_ok = (sim is None) or (sim < SEMANTIC_SCOPE_THRESHOLD)
        ok = pipeline_ok and gate_ok
        mark = "OK " if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{mark}] {code:<8} {method:<18} {_fmt_sim(sim):<12} {(d2_cpg or '-'):<48}")
        print(f"         label: {label}")
        if not pipeline_ok:
            print(f"         ! pipeline routed to {cpgs} (expected out_of_scope)")
        if not gate_ok:
            print(f"         ! D2 sim {sim:.3f} >= threshold {SEMANTIC_SCOPE_THRESHOLD}")

    await conn.close()

    print()
    if failures == 0:
        print(f"[PASS] {len(POSITIVES)} positives + {len(ORPHANS)} orphans behave correctly under threshold {SEMANTIC_SCOPE_THRESHOLD}.")
        return 0
    print(f"[FAIL] {failures} probe(s) violated expectations — see above.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
