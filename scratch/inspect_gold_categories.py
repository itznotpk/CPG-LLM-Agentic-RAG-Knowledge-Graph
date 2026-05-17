"""Show category metadata for every gold chunk in the 22 labelled questions."""
import asyncio, os, json
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
import asyncpg

GOLD = "eval/gold_sets/retrieval_gold.jsonl"

BOOST = {
    "Treatment": 1.4, "Supportive Treatment": 1.3,
    "Assessment": 1.2, "Diagnosis": 1.2, "Prevention": 1.2,
    "Special Populations": 1.1, "Reference": 1.0,
    "Introduction": 0.5, "Pathophysiology": 0.4,
    "Epidemiology": 0.4, "Methodology": 0.3,
}

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    with open(GOLD, "r", encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]

    cat_counts = Counter()
    boost_buckets = Counter()
    print(f"{'qid':10s} {'eff_boost':>9s}  categories                          | section")
    print("-" * 100)
    for r in rows:
        if not r["id"].startswith("ret_"):
            continue
        ids = r["relevant_chunk_ids"]
        if any(str(c).startswith("REPLACE_WITH_") for c in ids):
            continue
        for cid in ids:
            row = await conn.fetchrow(
                """SELECT c.metadata->>'category' AS cat,
                          c.metadata->>'title' AS title,
                          c.metadata->>'h2_title' AS h2,
                          c.metadata->>'source' AS src
                   FROM chunks c WHERE c.id = $1::uuid""", cid)
            if not row:
                print(f"  MISSING {cid}")
                continue
            cats = json.loads(row["cat"]) if row["cat"] else []
            for c in cats:
                cat_counts[c] += 1
            eff = max((BOOST.get(c, 1.0) for c in cats), default=1.0) if cats else 1.0
            if eff >= 1.2: bucket = "BOOSTED"
            elif eff >= 1.0: bucket = "neutral"
            else: bucket = "DEMOTED"
            boost_buckets[bucket] += 1
            label = (row["h2"] or row["title"] or "")[:35]
            print(f"  {r['id']:8s} {eff:>5.2f}     {str(cats)[:35]:35s} | {label}")

    print("\n=== Category frequency across all 66 gold chunks ===")
    for c, n in cat_counts.most_common():
        b = BOOST.get(c, 1.0)
        print(f"  {c:25s} x{b}   ({n} hits)")

    print("\n=== Boost buckets (per chunk, using max-of-cats) ===")
    for k in ("BOOSTED", "neutral", "DEMOTED"):
        print(f"  {k:8s} {boost_buckets[k]}")

    await conn.close()

asyncio.run(main())
