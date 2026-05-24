"""Apply per-row Approve/Reject decisions to T3 rows.

REJECT rows are listed by (group, idx) tuples where idx matches the row index in
_t3_<group>.jsonl (0-based). All other rows -> Approve.

Writes:
  tasks/Path_B_t3_decisions.jsonl     — one JSON per row: edge_id, decision, reason (rejects only)
  tasks/Path_B_review_grouped.md      — per-row tick checkboxes (rewritten)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "tasks")

# Rejects keyed by (group, idx) -> reason
REJECTS = {
    # value_not_in_evidence (16 rows): 11 rejects (Enoxaparin/Tinzaparin table-scrape weight bands + Vildagliptin BD->mg/day)
    ("value_not_in_evidence", 3): "weight band only in object name; evidence is bare table row without weight context (upstream KG-extractor defect)",
    ("value_not_in_evidence", 4): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 5): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 6): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 7): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 8): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 9): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 10): "weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 12): "Tinzaparin weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 13): "Tinzaparin weight band only in object name; evidence is bare table row",
    ("value_not_in_evidence", 15): "model converted 50mg BD -> 100 mg/day; derived value not in evidence; better stored as dose=50 + freq=BD",

    # op_paraphrased_or_missing (63 rows): 3 rejects
    ("op_paraphrased_or_missing", 7): "op inverted: '10% drop preclude further dilatation' means >=10% triggers stop; extracted <=10% is wrong direction",
    ("op_paraphrased_or_missing", 30): "Tinzaparin <50kg edge: weight band only in object name; bare table-row evidence",
    ("op_paraphrased_or_missing", 59): "hydrocortisone 100 mg 6-hourly is a stated dose, not a >= threshold",

    # unit_paraphrased_or_missing (55 rows): 5 rejects
    ("unit_paraphrased_or_missing", 8): "merged two distinct bands (45-59: 100mg OD; 30-44: not recommended) into one 30-59 range; loses adjustment vs avoid distinction",
    ("unit_paraphrased_or_missing", 18): "merged two distinct bands (45-59: no init; 30-44: not recommended) into one 30-59 range; loses distinction",
    ("unit_paraphrased_or_missing", 38): "30-50 eGFR triggers the 10mg adjustment, not the 15mg normal dose; threshold attached to wrong dose edge",
    ("unit_paraphrased_or_missing", 40): "30-50 CrCl triggers the 10mg dose, not the 15mg normal dose; wrong attachment",
    ("unit_paraphrased_or_missing", 43): "15mg edge is the normal dose; 30-50 eGFR triggers the 10mg adjustment; wrong attachment",

    # param_paraphrased (132 rows): 2 rejects
    ("param_paraphrased", 65): "op inverted: 'Max rate: 8 mcg/kg/min' is a ceiling (<=8); extracted >=8 is wrong direction",
    ("param_paraphrased", 66): "Tinzaparin 50-69kg edge: weight band only in object name; bare table-row evidence",
}

GROUP_ORDER = [
    ("param_paraphrased", "Param paraphrased (132)"),
    ("op_paraphrased_or_missing", "Op paraphrased or missing (63)"),
    ("unit_paraphrased_or_missing", "Unit paraphrased or missing (55)"),
    ("value_not_in_evidence", "Value not in evidence (16)"),
]

def load_group(g):
    rows = []
    with open(os.path.join(TASKS, f"_t3_{g}.jsonl"), encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows

def main():
    decisions = []
    md_lines = [
        "# Path B — Tier-3 review (per-row decisions)",
        "",
        f"All 266 T3 rows reviewed individually. Net: {266 - len(REJECTS)} Approve / {len(REJECTS)} Reject.",
        "",
        "Decisions are encoded as `[x]` ticked checkboxes. Rejects include a reason. ",
        "These feed the Path B backfill writer.",
        "",
    ]
    summary = {"approve": 0, "reject": 0}
    for g, title in GROUP_ORDER:
        rows = load_group(g)
        md_lines += [f"## {title}", ""]
        for i, r in enumerate(rows):
            e = r["edge"]; x = r["extracted"]
            key = (g, i)
            v = x.get("threshold_value")
            v2 = x.get("threshold_value2")
            vstr = f"{v}-{v2}" if v2 else f"{v}"
            extracted_str = f"{x.get('threshold_param')} {x.get('threshold_op')} {vstr} {x.get('threshold_unit') or ''}".strip()
            ev = (e.get("evidence") or "").replace("\n", " ").strip()
            if key in REJECTS:
                summary["reject"] += 1
                decisions.append({"edge_id": e["edge_id"], "decision": "reject", "reason": REJECTS[key], "extracted": x, "group": g})
                md_lines += [
                    f"### {i}. {e['relation']} — {e['subject']} → {e['object'][:60]}",
                    f"- Extracted: `{extracted_str}`",
                    f"- Evidence: {ev[:300]}",
                    f"- [ ] Approve",
                    f"- [x] **Reject** — {REJECTS[key]}",
                    "",
                ]
            else:
                summary["approve"] += 1
                decisions.append({"edge_id": e["edge_id"], "decision": "approve", "extracted": x, "group": g})
                md_lines += [
                    f"### {i}. {e['relation']} — {e['subject']} → {e['object'][:60]}",
                    f"- Extracted: `{extracted_str}`",
                    f"- Evidence: {ev[:300]}",
                    f"- [x] **Approve**",
                    f"- [ ] Reject",
                    "",
                ]
    out_md = os.path.join(TASKS, "Path_B_review_grouped.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    out_dec = os.path.join(TASKS, "Path_B_t3_decisions.jsonl")
    with open(out_dec, "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"Approve: {summary['approve']}  Reject: {summary['reject']}")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_dec}")

if __name__ == "__main__":
    main()
