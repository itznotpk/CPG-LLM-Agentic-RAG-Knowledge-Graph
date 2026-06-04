"""
Calibrate CC_BOOST_WEIGHT with the FULL pipeline simulation:
  1. search_ddx(cc_text) -> natural pool
  2. search_ddx(target_code) -> fetch missing codes (as the real pipeline does)
  3. Apply cc_boost = weight * confidence additively
  4. Re-sort by (similarity + cc_boost) and check if targets land in top-5

Usage:
  cd "CPG LLM"
  $env:PYTHONIOENCODING='utf-8'; python scripts/calibrate_cc_boost.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)


TEST_CASES = [
    {
        "name": "Textbook STEMI",
        "cc": "Acute central chest pain radiating to left arm, diaphoresis, ST elevation on ECG",
        "targets": ["BA41.0", "BA41.1", "BA41"],
        "expected_conf": 0.92,
    },
    {
        "name": "Vague chest discomfort",
        "cc": "Mild chest discomfort, intermittent, worse with deep breathing",
        "targets": ["BA41.0", "BA41.1"],
        "expected_conf": 0.45,
    },
    {
        "name": "Classic AF",
        "cc": "Palpitations, irregular pulse, breathlessness on exertion, known AF on warfarin",
        "targets": ["BC81.3", "BC81.30", "BC81.31"],
        "expected_conf": 0.90,
    },
    {
        "name": "Heart failure",
        "cc": "Progressive breathlessness NYHA III, bilateral ankle swelling, orthopnoea",
        "targets": ["BD11", "BD11.0", "BD11.1", "BD11.2", "BD10"],
        "expected_conf": 0.88,
    },
    {
        "name": "Non-specific fatigue",
        "cc": "Feeling tired for 2 weeks, no other symptoms",
        "targets": [],
        "expected_conf": 0.0,
    },
    {
        "name": "T2DM presentation",
        "cc": "Polyuria, polydipsia, weight loss, HbA1c 9.2%, known T2DM",
        "targets": ["5A11"],
        "expected_conf": 0.93,
    },
]

WEIGHTS_TO_TEST = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]


async def main():
    from agent.db_utils import initialize_database, close_database
    from ddx.search_ddx import search_ddx

    await initialize_database()

    print("=" * 95)
    print("CC_BOOST_WEIGHT CALIBRATION (full pipeline: fetch missing + boost)")
    print("=" * 95)

    all_results = []

    for case in TEST_CASES:
        print(f"\n{'=' * 95}")
        print(f"Case: {case['name']}")
        print(f"CC: {case['cc'][:80]}")
        print(f"Targets: {case['targets']}  |  Expected conf: {case['expected_conf']}")

        # Step 1: Natural DDx search with CC text
        try:
            ddx_results = await search_ddx(case["cc"], top_k=15)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        # Build natural pool
        pool = {}
        for r in ddx_results:
            code = r.get("code", "")
            pool[code] = r.get("similarity", 0)

        # Step 2: Fetch missing target codes (as the real pipeline does)
        fetched_sims = {}
        if case["targets"]:
            for tc in case["targets"]:
                if tc not in pool:
                    try:
                        fetch_results = await search_ddx(tc, top_k=5)
                        matched = next((r for r in fetch_results if r.get("code") == tc), None)
                        if matched:
                            sim = matched.get("similarity", 0)
                            pool[tc] = sim
                            fetched_sims[tc] = sim
                    except Exception:
                        pass

        # Print natural pool (top 10 + any target)
        sorted_natural = sorted(pool.items(), key=lambda x: x[1], reverse=True)
        print(f"\n  Natural pool (top-10 + fetched targets):")
        print(f"  {'Rank':<6} {'Code':<12} {'Sim':<10} {'Target?':<10} {'Fetched?'}")
        print(f"  {'-' * 55}")
        shown = set()
        for rank, (code, sim) in enumerate(sorted_natural[:10], 1):
            is_target = "***" if code in case["targets"] else ""
            is_fetched = "(fetched)" if code in fetched_sims else ""
            print(f"  {rank:<6} {code:<12} {sim:<10.4f} {is_target:<10} {is_fetched}")
            shown.add(code)
        # Also show targets if outside top-10
        for code, sim in sorted_natural[10:]:
            if code in case["targets"] and code not in shown:
                rank = [i for i, (c, _) in enumerate(sorted_natural, 1) if c == code][0]
                is_fetched = "(fetched)" if code in fetched_sims else ""
                print(f"  {rank:<6} {code:<12} {sim:<10.4f} ***        {is_fetched}")

        if not case["targets"] or case["expected_conf"] == 0:
            print("  (No targets to boost)")
            continue

        # Step 3: Simulate boost for each weight
        # Find the best target code's natural similarity
        best_target = None
        best_target_sim = 0
        for tc in case["targets"]:
            if tc in pool and pool[tc] > best_target_sim:
                best_target = tc
                best_target_sim = pool[tc]

        if not best_target:
            print(f"  !!! No target code found even after fetching")
            continue

        natural_rank = sorted([s for s in pool.values()], reverse=True).index(best_target_sim) + 1
        print(f"\n  Best target: {best_target}  natural_sim={best_target_sim:.4f}  natural_rank=#{natural_rank}")

        conf = case["expected_conf"]
        # Get threshold: the sim of the 5th-ranked code (what we need to beat)
        fifth_sim = sorted(pool.values(), reverse=True)[4] if len(pool) >= 5 else 0

        print(f"\n  {'Weight':<10} {'Boost':<10} {'Boosted':<12} {'5th-place':<12} {'Rank':<8} {'Status'}")
        print(f"  {'-' * 65}")

        for w in WEIGHTS_TO_TEST:
            boost = w * conf
            boosted = best_target_sim + boost

            # Count codes with higher (sim + their_boost) — only target gets boosted
            higher = sum(1 for c, s in pool.items() if c not in case["targets"] and s > boosted)
            rank = higher + 1

            status = "TOP-5 OK" if rank <= 5 else f"rank #{rank}"
            beats_5th = ">" if boosted > fifth_sim else "<"
            print(f"  {w:<10.2f} +{boost:<9.4f} {boosted:<12.4f} {beats_5th} {fifth_sim:<10.4f} #{rank:<6} {status}")

            all_results.append({
                "case": case["name"],
                "weight": w,
                "conf": conf,
                "natural_sim": best_target_sim,
                "boosted": boosted,
                "rank": rank,
                "in_top5": rank <= 5,
                "is_high_conf": conf >= 0.80,
            })

    # Summary
    print(f"\n\n{'=' * 95}")
    print("OPTIMAL WEIGHT SELECTION")
    print(f"{'=' * 95}")
    print(f"\n  Criteria:")
    print(f"    - All high-confidence cases (conf >= 0.80) must reach top-5")
    print(f"    - Vague cases (conf < 0.80) should NOT reach top-3 (avoid false promotion)")

    high_conf_names = {r["case"] for r in all_results if r["is_high_conf"]}
    vague_names = {r["case"] for r in all_results if not r["is_high_conf"]}

    print(f"\n  High-confidence cases: {high_conf_names}")
    print(f"  Vague cases: {vague_names}")

    print(f"\n  {'Weight':<12} {'High-conf all top-5':<24} {'Vague safe':<16} {'Verdict'}")
    print(f"  {'-' * 65}")

    best_weight = None
    for w in WEIGHTS_TO_TEST:
        hc_ok = all(
            r["in_top5"]
            for r in all_results if r["weight"] == w and r["is_high_conf"]
        )
        # Vague: shouldn't jump above rank 3
        vague_ok = all(
            r["rank"] >= 3
            for r in all_results if r["weight"] == w and not r["is_high_conf"]
        )
        verdict = "OPTIMAL" if hc_ok and vague_ok else ("HC FAIL" if not hc_ok else "VAGUE RISK")
        if hc_ok and vague_ok and best_weight is None:
            best_weight = w
            verdict = ">>> OPTIMAL <<<"
        print(f"  {w:<12.2f} {str(hc_ok):<24} {str(vague_ok):<16} {verdict}")

    if best_weight:
        print(f"\n  RECOMMENDED CC_BOOST_WEIGHT = {best_weight}")
    else:
        print(f"\n  No single weight satisfies all criteria. Review per-case results above.")
        # Find min weight for high-conf
        for w in WEIGHTS_TO_TEST:
            hc_ok = all(r["in_top5"] for r in all_results if r["weight"] == w and r["is_high_conf"])
            if hc_ok:
                print(f"  Minimum weight for high-conf top-5: {w} (but check vague case safety)")
                break

    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
