"""Quick smoke test for graph_clinical.py"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import asyncio
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph_clinical import clinical_graph_lookup, format_flags_for_prompt


async def test():
    print("=" * 60)
    print("SMOKE TEST: clinical_graph_lookup")
    print("=" * 60)

    # Test 1: Drug interaction — Warfarin + Digoxin
    print("\nTest 1: Patient on Warfarin, candidate = Digoxin")
    flags = await clinical_graph_lookup(
        patient_meds=["warfarin"],
        candidate_drugs=["digoxin", "amiodarone"],
        comorbidities=["heart failure", "atrial fibrillation"],
        allergies=[],
    )
    print(f"  Flags returned: {len(flags)}")
    for f in flags:
        print(f"    [{f.flag_type}] {f.subject} <-> {f.object} ({f.relation})")
        if f.evidence:
            print(f"      Evidence: \"{f.evidence[:80]}...\"")

    # Test 2: Comorbidity — drugs with monitoring for AF
    print("\nTest 2: Comorbidities = AF, candidate = Warfarin")
    flags2 = await clinical_graph_lookup(
        patient_meds=[],
        candidate_drugs=["warfarin"],
        comorbidities=["atrial fibrillation", "bleeding"],
        allergies=[],
    )
    print(f"  Flags returned: {len(flags2)}")
    for f in flags2:
        print(f"    [{f.flag_type}] {f.subject} <-> {f.object} ({f.relation})")

    # Test 3: Empty case (should return empty, not crash)
    print("\nTest 3: Empty inputs (should gracefully return [])")
    flags3 = await clinical_graph_lookup()
    print(f"  Flags returned: {len(flags3)} (expected 0)")

    # Test 4: Format for prompt
    print("\nTest 4: Prompt formatting")
    all_flags = flags + flags2
    prompt_block = format_flags_for_prompt(all_flags)
    print(prompt_block)

    print("=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)

asyncio.run(test())
