"""Path B audit — count edges carrying parseable numeric thresholds.

Surveys edge types that plausibly encode dose/monitoring thresholds, samples
their string fields (trigger / severity_threshold / dosage_text / notes), and
estimates how many would benefit from typed numeric properties
(threshold_param, threshold_op, threshold_value, threshold_unit).
"""
import asyncio
import os
import re
import sys
from collections import Counter, defaultdict

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agent.graph_clinical import _get_neo4j_session

EDGE_TYPES = [
    "REQUIRES_DOSE_ADJUSTMENT",
    "REQUIRES_MONITORING",
    "HAS_DOSAGE",
    "CONTRAINDICATED_WITH",
    "INTERACTS_WITH",
    "INCREASES_RISK_OF",
    "FIRST_LINE_FOR",
    "SECOND_LINE_FOR",
    "RECOMMENDED_FOR",
]

STRING_FIELDS = ["trigger", "severity_threshold", "dosage_text", "threshold", "notes", "evidence", "condition_trigger"]

NUMERIC_PATTERN = re.compile(
    r"(?P<param>[A-Za-z][A-Za-z0-9 _\-/]{1,30}?)\s*"
    r"(?P<op>>=|<=|>|<|=|≥|≤)\s*"
    r"(?P<value>\d+(?:\.\d+)?)"
    r"\s*(?P<unit>[A-Za-zµ%/\^0-9.\-]{0,20})"
)


async def main():
    print("=" * 78)
    print("Path B audit — typed-threshold extractability across KG edges")
    print("=" * 78)

    async with await _get_neo4j_session() as session:
        for etype in EDGE_TYPES:
            res = await session.run(f"MATCH ()-[r:{etype}]->() RETURN count(r) AS n")
            rec = await res.single()
            total = rec["n"] if rec else 0
            print(f"\n[{etype}] total edges: {total}")
            if total == 0:
                continue

            # Inspect properties present on a sample
            res = await session.run(
                f"MATCH ()-[r:{etype}]->() WITH r LIMIT 200 "
                f"RETURN keys(r) AS k, properties(r) AS p"
            )
            key_counter = Counter()
            field_examples = defaultdict(list)
            parseable_by_field = Counter()
            string_field_nonempty = Counter()
            sample_count = 0
            async for row in res:
                sample_count += 1
                for k in row["k"]:
                    key_counter[k] += 1
                for f in STRING_FIELDS:
                    v = row["p"].get(f)
                    if isinstance(v, str) and v.strip():
                        string_field_nonempty[f] += 1
                        if len(field_examples[f]) < 3:
                            field_examples[f].append(v[:140])
                        if NUMERIC_PATTERN.search(v):
                            parseable_by_field[f] += 1

            print(f"  sampled: {sample_count} edges")
            print(f"  property keys present: {dict(key_counter.most_common(8))}")
            for f in STRING_FIELDS:
                if string_field_nonempty[f]:
                    n = string_field_nonempty[f]
                    p = parseable_by_field[f]
                    pct = (p / n * 100) if n else 0
                    print(f"  field '{f}': {n} nonempty, {p} regex-parseable ({pct:.0f}%)")
                    for ex in field_examples[f]:
                        print(f"      ex: {ex!r}")

            # Check whether any typed-threshold property already exists
            res = await session.run(
                f"MATCH ()-[r:{etype}]->() "
                f"WHERE r.threshold_param IS NOT NULL OR r.threshold_value IS NOT NULL "
                f"RETURN count(r) AS n"
            )
            rec = await res.single()
            typed = rec["n"] if rec else 0
            print(f"  already-typed (threshold_param/value present): {typed}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
