r"""
Check for duplicate/near-duplicate nodes in the Knowledge Graph.
The issue: LLM extracts "Atrial Fibrillation" from one chunk and
"atrial fibrillation" or "AF" from another -> MERGE creates 2 nodes
because names don't match exactly.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


async def check_duplicates():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=" * 70)
    print("DUPLICATE / NEAR-DUPLICATE NODE DETECTION")
    print("=" * 70)

    async with driver.session(database=NEO4J_DATABASE) as session:

        # CHECK 1: Exact case-insensitive duplicates
        # e.g., "Atrial Fibrillation" vs "atrial fibrillation" vs "Atrial fibrillation"
        print("\n[CHECK 1] Case-insensitive duplicates (same name, different casing)")
        result = await session.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL
            WITH toLower(trim(n.name)) AS normalized, collect(n.name) AS variants, count(n) AS cnt
            WHERE cnt > 1
            RETURN normalized, variants, cnt
            ORDER BY cnt DESC
            LIMIT 20
        """)
        case_dupes = [r async for r in result]

        if case_dupes:
            print(f"  Found {len(case_dupes)} groups of case duplicates:")
            for d in case_dupes:
                print(f"    '{d['normalized']}' has {d['cnt']} nodes:")
                for v in d["variants"]:
                    print(f"      - \"{v}\"")
        else:
            print("  None found!")

        # CHECK 2: Same label, similar names (abbreviation issues)
        # e.g., "AF" vs "Atrial Fibrillation" vs "Atrial fibrillation (AF)"
        print("\n[CHECK 2] Known clinical abbreviation splits")
        known_pairs = [
            ("AF", "Atrial Fibrillation"),
            ("AF", "Atrial fibrillation"),
            ("HF", "Heart Failure"),
            ("HF", "Heart failure"),
            ("VKA", "Warfarin"),
            ("VKA", "Vitamin K Antagonist"),
            ("OAC", "Oral Anticoagulant"),
            ("DCCV", "Direct Current Cardioversion"),
            ("INR", "International Normalized Ratio"),
            ("TIA", "Transient Ischaemic Attack"),
            ("LMWH", "Low Molecular Weight Heparin"),
            ("ECG", "Electrocardiography"),
            ("TOE", "Transoesophageal Echocardiography"),
            ("LAA", "Left Atrial Appendage"),
        ]

        splits_found = 0
        for abbr, full in known_pairs:
            result = await session.run("""
                MATCH (a), (b)
                WHERE a.name =~ $abbr_pattern AND b.name =~ $full_pattern
                AND id(a) <> id(b)
                RETURN a.name AS abbr_node, labels(a) AS abbr_labels,
                       b.name AS full_node, labels(b) AS full_labels
                LIMIT 3
            """, abbr_pattern=f"(?i)^{abbr}$", full_pattern=f"(?i).*{full}.*")
            pairs = [r async for r in result]
            if pairs:
                splits_found += 1
                for p in pairs:
                    print(f"  SPLIT: \"{p['abbr_node']}\" ({','.join(p['abbr_labels'])}) vs \"{p['full_node']}\" ({','.join(p['full_labels'])})")

        if splits_found == 0:
            print("  No abbreviation splits found!")

        # CHECK 3: Nodes with very similar names (fuzzy match)
        # e.g., "stroke" vs "Stroke" vs "Strokes" vs "ischaemic stroke"
        print("\n[CHECK 3] Plural/variant duplicates (manual review)")
        result = await session.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL
            WITH toLower(trim(n.name)) AS base,
                 CASE
                   WHEN toLower(trim(n.name)) ENDS WITH 's'
                   THEN left(toLower(trim(n.name)), size(toLower(trim(n.name))) - 1)
                   ELSE toLower(trim(n.name))
                 END AS stem,
                 n.name AS original, labels(n)[0] AS label
            WITH stem, collect({name: original, label: label}) AS nodes, count(*) AS cnt
            WHERE cnt > 1
            RETURN stem, nodes, cnt
            ORDER BY cnt DESC
            LIMIT 15
        """)
        plural_dupes = [r async for r in result]

        if plural_dupes:
            print(f"  Found {len(plural_dupes)} potential plural/variant groups:")
            for d in plural_dupes:
                names = [f"\"{n['name']}\" ({n['label']})" for n in d["nodes"]]
                print(f"    stem='{d['stem']}': {', '.join(names)}")
        else:
            print("  None found!")

        # CHECK 4: Overall node count vs unique lowercased names
        print("\n[CHECK 4] Overall duplication ratio")
        result = await session.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL
            WITH count(n) AS total_nodes,
                 count(DISTINCT toLower(trim(n.name))) AS unique_names
            RETURN total_nodes, unique_names,
                   total_nodes - unique_names AS duplicates,
                   round(100.0 * (total_nodes - unique_names) / total_nodes, 1) AS dup_pct
        """)
        rec = await result.single()
        if rec:
            print(f"  Total nodes: {rec['total_nodes']}")
            print(f"  Unique names (case-insensitive): {rec['unique_names']}")
            print(f"  Duplicate nodes: {rec['duplicates']} ({rec['dup_pct']}%)")

            if rec['dup_pct'] > 10:
                print(f"\n  >> WARNING: {rec['dup_pct']}% duplication rate is high!")
                print("     Consider adding name normalization to graph_builder.py")
            elif rec['dup_pct'] > 0:
                print(f"\n  >> MINOR: {rec['dup_pct']}% duplication — manageable but worth cleaning")
            else:
                print(f"\n  >> CLEAN: No duplicates detected!")

    print("\n" + "=" * 70)
    await driver.close()


if __name__ == "__main__":
    asyncio.run(check_duplicates())
