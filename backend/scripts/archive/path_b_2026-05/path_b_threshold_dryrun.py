"""Path B (option 1a) — typed-threshold extraction dry-run.

Samples existing KG edges in the four target relationship types, prompts an
LLM to extract a structured numeric threshold (or return null), and prints
proposed Neo4j MERGE updates. WRITES NOTHING — this is dry-run only.

Target edges: REQUIRES_DOSE_ADJUSTMENT, REQUIRES_MONITORING,
              CONTRAINDICATED_WITH, HAS_DOSAGE.

New properties proposed on each matched edge (additive — leaves existing
trigger/evidence strings untouched):
    threshold_param   e.g. "eGFR"
    threshold_op      one of: "<", "<=", ">", ">=", "=", "between"
    threshold_value   numeric (float)
    threshold_value2  numeric (float) — only when op="between"
    threshold_unit    e.g. "mL/min/1.73m2"
    threshold_negated true if the threshold is the SAFE band, false if it's
                      the TRIGGER band (default false)
"""
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

import openai
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agent.graph_clinical import _get_neo4j_session

TARGET_RELS = [
    "REQUIRES_DOSE_ADJUSTMENT",
    "REQUIRES_MONITORING",
    "CONTRAINDICATED_WITH",
    "HAS_DOSAGE",
]
SAMPLES_PER_REL = 25
GATE_CONFIDENCE = "high"   # only edges where the LLM self-rates "high" become typed writes
REVIEW_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tasks", "Path_B_threshold_review.md",
)

EXTRACTOR_SYSTEM = """You extract structured numeric clinical thresholds from short evidence strings.

Given a relationship between a drug (or condition) and a target, plus the evidence text and an optional trigger string, decide if the text encodes a SPECIFIC NUMERIC THRESHOLD against a clinical parameter (lab value, vital sign, age, dose, duration).

Return STRICT JSON:
{
  "threshold_param": "<short canonical name, e.g. eGFR, SBP, age, HR, K+, INR, creatinine, simvastatin_dose>" | null,
  "threshold_op": "<" | "<=" | ">" | ">=" | "=" | "between" | null,
  "threshold_value": <number> | null,
  "threshold_value2": <number> | null,   // ONLY when op == "between"
  "threshold_unit": "<unit string, e.g. mL/min/1.73m2, mmHg, bpm, years, mg/day>" | null,
  "threshold_negated": true | false,     // true if the threshold marks the SAFE band, false (default) if it marks the TRIGGER/UNSAFE band
  "confidence": "high" | "medium" | "low",
  "rationale": "<one short sentence>"
}

Rules:
- If the text is purely categorical (e.g. "Heart Failure", "hepatic impairment", "elderly") with NO numeric value, return all threshold_* fields as null and confidence="low".
- If multiple thresholds exist, pick the one most clinically actionable for THIS edge (the trigger for action).
- Do NOT invent values. Only extract numbers that appear literally in the text.
- Use ASCII operators (>=, <=) not unicode.
- Canonicalise common parameter names: eGFR, creatinine, SBP, DBP, MAP, HR, age, weight, BMI, K+, Na+, INR, HbA1c, LDL, platelet, hemoglobin.
"""


def make_user_prompt(edge: Dict[str, Any]) -> str:
    return json.dumps({
        "relation": edge["relation"],
        "drug_or_subject": edge["subject"],
        "target_or_object": edge["object"],
        "trigger": edge.get("trigger"),
        "evidence": edge.get("evidence"),
    }, ensure_ascii=False)


async def fetch_sample_edges() -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    async with await _get_neo4j_session() as session:
        for rel in TARGET_RELS:
            # Prefer edges that already carry a trigger string (highest signal),
            # then fill remaining slots with evidence-only edges so we also test
            # the "no trigger field but numeric in evidence" case.
            q = f"""
                MATCH (a)-[r:{rel}]->(b)
                WITH a, r, b,
                     CASE WHEN r.trigger IS NOT NULL AND r.trigger <> '' THEN 1 ELSE 0 END AS has_trigger
                ORDER BY has_trigger DESC, rand()
                LIMIT $n
                RETURN
                    r.elementId AS _ignored,
                    elementId(r) AS edge_id,
                    type(r) AS relation,
                    coalesce(a.name, a.name_normalised) AS subject,
                    coalesce(b.name, b.name_normalised) AS object,
                    r.trigger AS trigger,
                    r.evidence AS evidence,
                    r.cpg_chunk_id AS cpg_chunk_id,
                    r.source_document AS source_document
            """
            result = await session.run(q, n=SAMPLES_PER_REL)
            async for row in result:
                edges.append({
                    "edge_id": row["edge_id"],
                    "relation": row["relation"],
                    "subject": row["subject"],
                    "object": row["object"],
                    "trigger": row["trigger"],
                    "evidence": row["evidence"],
                    "cpg_chunk_id": row["cpg_chunk_id"],
                    "source_document": row["source_document"],
                })
    return edges


async def extract_threshold(client, model: str, edge: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM},
                {"role": "user", "content": make_user_prompt(edge)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"_error": str(e)}


def format_merge_cypher(edge: Dict[str, Any], extracted: Dict[str, Any]) -> str:
    if not extracted or extracted.get("threshold_param") is None:
        return "  -- (no typed threshold; edge unchanged)"
    params = {
        "threshold_param": extracted.get("threshold_param"),
        "threshold_op": extracted.get("threshold_op"),
        "threshold_value": extracted.get("threshold_value"),
        "threshold_value2": extracted.get("threshold_value2"),
        "threshold_unit": extracted.get("threshold_unit"),
        "threshold_negated": bool(extracted.get("threshold_negated", False)),
    }
    sets = ",\n      ".join(f"r.{k} = ${k}" for k in params if params[k] is not None)
    return (
        "  MATCH ()-[r]->() WHERE elementId(r) = $edge_id\n"
        f"  SET {sets}\n"
        f"  // params: {json.dumps(params, ensure_ascii=False)}"
    )


async def main():
    base_url = os.getenv("SAFETY_CRITIC_LLM_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("SAFETY_CRITIC_LLM_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    stage5_model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    model = os.getenv("SAFETY_CRITIC_MODEL", stage5_model)
    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)

    print("=" * 90)
    print(f"Path B (option 1a) — typed-threshold extraction DRY-RUN")
    print(f"model: {model}")
    print(f"target relations: {TARGET_RELS}")
    print(f"samples per relation: {SAMPLES_PER_REL}")
    print("=" * 90)

    edges = await fetch_sample_edges()
    print(f"\nSampled {len(edges)} edges from Neo4j.\n")

    summary = {"typed_high": 0, "typed_low_conf": 0, "skipped": 0, "errors": 0, "by_rel": {}}
    review_rows: List[Dict[str, Any]] = []  # high-conf extractions for the markdown review file

    for i, edge in enumerate(edges, 1):
        print("-" * 90)
        print(f"[{i}/{len(edges)}] {edge['relation']}: {edge['subject']!r} -> {edge['object']!r}")
        print(f"  trigger:  {edge.get('trigger')!r}")
        ev = (edge.get("evidence") or "")[:220]
        print(f"  evidence: {ev!r}")
        print(f"  source:   {edge.get('source_document')}")

        extracted = await extract_threshold(client, model, edge)
        if not extracted:
            print("  -> (no response)")
            summary["errors"] += 1
            continue
        if "_error" in extracted:
            print(f"  -> ERROR: {extracted['_error']}")
            summary["errors"] += 1
            continue

        has_typed = extracted.get("threshold_param") is not None
        conf = extracted.get("confidence")
        passes_gate = has_typed and conf == GATE_CONFIDENCE
        if passes_gate:
            marker = "WRITE"
        elif has_typed:
            marker = f"GATED({conf})"
        else:
            marker = "skip"
        print(f"  -> [{marker}] conf={conf} :: {extracted.get('rationale')}")
        if has_typed:
            print(f"     param={extracted.get('threshold_param')} "
                  f"op={extracted.get('threshold_op')} "
                  f"value={extracted.get('threshold_value')}"
                  + (f"..{extracted.get('threshold_value2')}" if extracted.get('threshold_value2') is not None else "")
                  + f" unit={extracted.get('threshold_unit')} "
                  f"negated={extracted.get('threshold_negated')}")
            if passes_gate:
                print("  Proposed Cypher (NOT executed):")
                print(format_merge_cypher(edge, extracted))
                summary["typed_high"] += 1
                review_rows.append({"edge": edge, "extracted": extracted})
            else:
                print(f"  (gated by confidence != {GATE_CONFIDENCE!r} — would NOT write)")
                summary["typed_low_conf"] += 1
        else:
            summary["skipped"] += 1
        rel_stats = summary["by_rel"].setdefault(edge["relation"], {"typed_high": 0, "typed_low_conf": 0, "skipped": 0})
        if passes_gate:
            rel_stats["typed_high"] += 1
        elif has_typed:
            rel_stats["typed_low_conf"] += 1
        else:
            rel_stats["skipped"] += 1

    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"  WRITE (typed + conf={GATE_CONFIDENCE!r}): {summary['typed_high']}")
    print(f"  gated (typed but lower conf):       {summary['typed_low_conf']}")
    print(f"  skipped (no numeric threshold):     {summary['skipped']}")
    print(f"  errors:                              {summary['errors']}")
    print(f"  by relation:")
    for rel, stats in summary["by_rel"].items():
        n = stats["typed_high"] + stats["typed_low_conf"] + stats["skipped"]
        pct = (stats["typed_high"] / n * 100) if n else 0
        print(f"    {rel}: WRITE={stats['typed_high']}/{n} ({pct:.0f}%)  "
              f"gated={stats['typed_low_conf']}  skipped={stats['skipped']}")
    # Write a clinician-reviewable markdown file containing only the WRITE-gated rows.
    write_review_file(review_rows, summary)
    print(f"\nReview file written: {REVIEW_OUT}")
    print("No writes performed. Review the proposed Cypher above before running for real.")


def write_review_file(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(REVIEW_OUT), exist_ok=True)
    by_rel: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_rel.setdefault(r["edge"]["relation"], []).append(r)

    lines: List[str] = []
    lines.append("# Path B threshold-extraction review")
    lines.append("")
    lines.append(f"Sampled {SAMPLES_PER_REL} edges per relation, gated on `confidence == \"{GATE_CONFIDENCE}\"`.")
    lines.append(f"Shown below: {len(rows)} extractions that would be MERGEd onto existing edges.")
    lines.append("")
    lines.append("**For each row, verify the extracted threshold against the evidence text and tick one box.**")
    lines.append("`source_document` points at the section in the CPG markdown for cross-reference.")
    lines.append("")
    lines.append("---")
    lines.append("")
    for rel, items in by_rel.items():
        lines.append(f"## {rel}  ({len(items)} extractions)")
        lines.append("")
        for i, r in enumerate(items, 1):
            e, x = r["edge"], r["extracted"]
            v = x.get("threshold_value")
            v2 = x.get("threshold_value2")
            value_str = f"{v}..{v2}" if v2 is not None else f"{v}"
            lines.append(f"### {rel} #{i}: `{e['subject']}` → `{e['object']}`")
            lines.append("")
            lines.append(f"- **Source:** {e.get('source_document') or '(unknown)'}")
            lines.append(f"- **Existing trigger string:** `{e.get('trigger')!r}`")
            lines.append(f"- **Evidence:** _{(e.get('evidence') or '').strip()}_")
            lines.append(f"- **Extracted:** `{x.get('threshold_param')} {x.get('threshold_op')} {value_str} {x.get('threshold_unit') or ''}`"
                         f"  (negated={x.get('threshold_negated')})")
            lines.append(f"- **Rationale:** {x.get('rationale')}")
            lines.append(f"- **edge_id:** `{e['edge_id']}`")
            lines.append("")
            lines.append("- [ ] Approve  [ ] Edit  [ ] Reject")
            lines.append("")
        lines.append("---")
        lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- WRITE (would be merged): {summary['typed_high']}")
    lines.append(f"- Gated by confidence:     {summary['typed_low_conf']}")
    lines.append(f"- Skipped (no threshold):  {summary['skipped']}")
    lines.append(f"- Errors:                  {summary['errors']}")
    with open(REVIEW_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
