"""Path B — full-corpus threshold extraction across all target edges.

Walks every edge in the 4 target relation types (REQUIRES_DOSE_ADJUSTMENT,
REQUIRES_MONITORING, CONTRAINDICATED_WITH, HAS_DOSAGE), extracts a typed
numeric threshold via LLM, then sorts the result into four tiers:

  Tier 1 — auto-approve: extracted value+unit appear literally in evidence text.
  Tier 2 — auto-approve after a small unit/synonym normalisation table.
  Tier 3 — flagged for human review, grouped by failure pattern.
  Tier 4 — auto-reject: LLM confidence != "high" or no threshold extracted.

WRITES NOTHING to Neo4j. Produces three artifacts under tasks/:
  Path_B_auto_approved.jsonl       — Tier 1+2 rows for the future backfill writer.
  Path_B_review_grouped.md         — Tier 3 grouped by failure pattern.
  Path_B_extraction_summary.md     — tier counts + per-relation breakdown.
"""
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import openai
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agent.graph_clinical import _get_neo4j_session
from scripts.path_b_threshold_dryrun import EXTRACTOR_SYSTEM, make_user_prompt

TARGET_RELS = [
    "REQUIRES_DOSE_ADJUSTMENT",
    "REQUIRES_MONITORING",
    "CONTRAINDICATED_WITH",
    "HAS_DOSAGE",
]

CONCURRENCY = 8

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_RAW = os.path.join(REPO_ROOT, "tasks", "Path_B_raw_results.jsonl")
OUT_APPROVED = os.path.join(REPO_ROOT, "tasks", "Path_B_auto_approved.jsonl")
OUT_REVIEW = os.path.join(REPO_ROOT, "tasks", "Path_B_review_grouped.md")
OUT_SUMMARY = os.path.join(REPO_ROOT, "tasks", "Path_B_extraction_summary.md")

# Unit / synonym normalisation (Tier 2).
# Keys are extracted strings; values are the canonical form we compare against the
# evidence text. ASCII only — strip whitespace, normalise case at match time.
UNIT_SYNONYMS = {
    "ml/min/1.73m2": ["ml/min/1.73 m2", "mls/min/1.73m2", "ml/min/1.73 m²", "ml/min/1.73m²",
                       "ml/min per 1.73 m2", "ml/min per 1.73 m²", "ml/min", "mls/min"],
    "ml/min": ["mls/min", "mls / min", "ml/min/1.73m2"],
    "mmhg": ["mm hg", "mm/hg"],
    "bpm": ["/bpm", "/min", "beats/min", "beats per minute"],
    "iu/kg/day": ["iu/kg/d", "iu/kg per day"],
    "mg/day": ["mg/d", "mg per day", "mg od", "mg daily", "mg/day", "mg per day"],
    "mg": ["mg", "mg/day", "milligram"],
    "mcg/hour": ["mcg/h", "mcg per hour", "ug/hour", "mcg/hour"],
    "mmol/l": ["mmol/litre", "mmol per litre", "mmol/l"],
    "%": ["percent", "per cent"],
    "years": ["yr", "yrs", "y/o", "years old", "year", "years"],
    "weeks": ["wks", "wk", "week"],
    "hours": ["hrs", "hr", "hour", "h"],
    "days": ["day", "d"],
    "months": ["mth", "month"],
    "kg": ["kgs", "kilograms"],
}

PARAM_SYNONYMS = {
    # extracted -> list of phrases that count as "literally present" in evidence
    "egfr": ["egfr", "estimated gfr", "gfr", "glomerular filtration"],
    "crcl": ["crcl", "creatinine clearance", "cockcroft", "cc"],
    "sbp": ["sbp", "systolic bp", "systolic blood pressure", "systolic"],
    "dbp": ["dbp", "diastolic bp", "diastolic blood pressure", "diastolic"],
    "hr": ["hr", "heart rate", "/bpm", "beats/min", "pulse"],
    "k+": ["k+", "potassium", "serum potassium", "hyperkalaemia", "hyperkalemia", "hypokalaemia", "hypokalemia"],
    "creatinine": ["creatinine", "scr", "serum creatinine"],
    "age": ["age", "years", "year-old", "y/o", "aged", "elderly"],
    "weight": ["weight", "kg", "body weight", "bw"],
    "duration": ["duration", "weeks", "days", "months", "hours", "at least", "before", "after"],
    "inr": ["inr"],
    "hba1c": ["hba1c", "a1c"],
    "ldl": ["ldl", "ldl-c", "ldl cholesterol", "low density lipoprotein"],
    "platelet": ["platelet", "thrombocyte"],
    "haemoglobin": ["hb", "haemoglobin", "hemoglobin"],
    "sodium": ["na+", "na", "sodium", "hyponatraemia", "hyponatremia"],
    "qtc": ["qtc", "qt interval", "qt"],
}

# Compound-parameter patterns. If extracted param matches a regex here, the
# matcher should check evidence for the captured token + a numeric clause.
COMPOUND_PARAM_PATTERNS = [
    # "<drug>_dose" — match if the drug name appears in evidence near a number/unit
    (re.compile(r"^(.+?)_(dose|maintenance_dose|max_dose|daily_dose|tdd)$"), "drug"),
    # "<thing>_diameter|size|level|count" — match if the thing appears in evidence
    (re.compile(r"^(.+?)_(diameter|size|level|count|inhibition|change|reduction)$"), "thing"),
]


def compound_param_match(param: Optional[str], text: str) -> bool:
    if not param:
        return False
    p = normalise(param)
    t = normalise(text)
    for pat, _kind in COMPOUND_PARAM_PATTERNS:
        m = pat.match(p)
        if m:
            head = m.group(1).replace("_", " ").strip()
            if head and head in t:
                return True
    return False


def normalise(s: Optional[str]) -> str:
    if not s:
        return ""
    out = s.lower().strip()
    out = out.replace("²", "2").replace("μ", "u").replace("µ", "u")
    out = out.replace("≥", ">=").replace("≤", "<=")
    out = re.sub(r"\s+", " ", out)
    return out


def value_in_text(value: Any, value2: Any, text: str) -> bool:
    """Check whether the numeric value(s) appear literally in the evidence."""
    if value is None:
        return False
    t = normalise(text)
    # try a few common renderings of the number
    candidates = []
    for v in (value, value2):
        if v is None:
            continue
        candidates.append(str(v))
        if isinstance(v, float) and v.is_integer():
            candidates.append(str(int(v)))
        if isinstance(v, (int, float)):
            candidates.append(f"{v:g}")
    return any(c.lower() in t for c in candidates)


def unit_in_text(unit: Optional[str], text: str) -> bool:
    """Check unit literal presence, with the Tier-2 synonym table."""
    if not unit:
        return True   # missing unit shouldn't block Tier 1 if the value matches
    u = normalise(unit)
    t = normalise(text)
    if u in t:
        return True
    # check synonym group
    for canonical, alts in UNIT_SYNONYMS.items():
        if canonical == u or u in alts:
            if canonical in t or any(a in t for a in alts):
                return True
    return False


def param_in_text(param: Optional[str], text: str) -> bool:
    if not param:
        return False
    p = normalise(param)
    t = normalise(text)
    if p in t:
        return True
    for canonical, alts in PARAM_SYNONYMS.items():
        if canonical == p or canonical in p:
            if any(a in t for a in alts):
                return True
    if compound_param_match(param, text):
        return True
    return False


def op_in_text(op: Optional[str], text: str) -> bool:
    if not op:
        return False
    t = normalise(text)
    if op == "between":
        # "between" thresholds: accept "-" or "to" between two numbers
        return ("-" in t) or (" to " in t) or ("between" in t)
    # extracted op -> set of literal forms that satisfy it
    forms = {
        "<": ["<", "below", "less than", "under"],
        "<=": ["<=", "≤", "less than or equal", "up to", "no more than"],
        ">": [">", "above", "more than", "greater than", "over"],
        ">=": [">=", "≥", "at least", "no less than"],
        "=": ["="],
    }.get(op, [op])
    return any(f in t for f in forms)


def classify(edge: Dict[str, Any], x: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return (tier, reason). Tier in {T1, T2, T3, T4}. reason for T3 grouping."""
    conf = x.get("confidence")
    if conf != "high":
        return "T4", f"confidence={conf!r}"
    if not x.get("threshold_param"):
        return "T4", "no_threshold_extracted"

    text = (edge.get("evidence") or "") + " " + (edge.get("trigger") or "")
    v_ok = value_in_text(x.get("threshold_value"), x.get("threshold_value2"), text)
    p_ok = param_in_text(x.get("threshold_param"), text)
    u_ok = unit_in_text(x.get("threshold_unit"), text)
    o_ok = op_in_text(x.get("threshold_op"), text)

    # Tier 1: everything matches literally (no synonym substitution).
    if v_ok and p_ok and o_ok and (not x.get("threshold_unit") or normalise(x["threshold_unit"]) in normalise(text)):
        return "T1", None

    # Tier 2: same as T1 but unit/param matched only via synonym table.
    if v_ok and p_ok and o_ok and u_ok:
        return "T2", None

    # Tier 3: at least the value is literal but something else doesn't match.
    if not v_ok:
        return "T3", "value_not_in_evidence"
    if not o_ok:
        return "T3", "op_paraphrased_or_missing"
    if not p_ok:
        return "T3", "param_paraphrased"
    if not u_ok:
        return "T3", "unit_paraphrased_or_missing"
    return "T3", "other"


async def fetch_all_target_edges(session) -> List[Dict[str, Any]]:
    edges = []
    for rel in TARGET_RELS:
        q = f"""
            MATCH (a)-[r:{rel}]->(b)
            RETURN
                elementId(r) AS edge_id,
                type(r) AS relation,
                coalesce(a.name, a.name_normalised) AS subject,
                coalesce(b.name, b.name_normalised) AS object,
                r.trigger AS trigger,
                r.evidence AS evidence,
                r.cpg_chunk_id AS cpg_chunk_id,
                r.source_document AS source_document
        """
        result = await session.run(q)
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


async def extract_one(client, model: str, edge: Dict[str, Any], sem: asyncio.Semaphore) -> Dict[str, Any]:
    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": EXTRACTOR_SYSTEM},
                    {"role": "user", "content": make_user_prompt(edge)},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                # mimo-v2.5-pro is a reasoning model; without enable_thinking=False
                # short-output calls return empty content -> JSON parse error.
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = resp.choices[0].message.content
            if not content or not content.strip():
                return {"_error": "empty_content"}
            return json.loads(content)
        except Exception as e:
            return {"_error": str(e)}


def load_cached_raw() -> Dict[str, Dict[str, Any]]:
    """Load previous raw extractions keyed by edge_id (errors excluded so they retry)."""
    cache: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(OUT_RAW):
        return cache
    with open(OUT_RAW, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                if "_error" in row.get("extracted", {}):
                    continue
                cache[row["edge"]["edge_id"]] = row["extracted"]
            except Exception:
                continue
    return cache


async def main():
    base_url = os.getenv("SAFETY_CRITIC_LLM_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("SAFETY_CRITIC_LLM_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    stage5_model = os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", "gpt-4o")
    model = os.getenv("SAFETY_CRITIC_MODEL", stage5_model)
    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)

    print(f"Path B full-corpus extraction. model={model} concurrency={CONCURRENCY}")
    async with await _get_neo4j_session() as session:
        edges = await fetch_all_target_edges(session)
    total = len(edges)
    print(f"Fetched {total} edges across {TARGET_RELS}")

    cache = load_cached_raw()
    cached_hits = sum(1 for e in edges if e["edge_id"] in cache)
    to_run = [e for e in edges if e["edge_id"] not in cache]
    print(f"  cache: {cached_hits} hits, {len(to_run)} edges to call LLM for")

    sem = asyncio.Semaphore(CONCURRENCY)
    CHUNK = 100
    new_results: Dict[str, Dict[str, Any]] = {}
    raw_fp = open(OUT_RAW, "a", encoding="utf-8")
    for i in range(0, len(to_run), CHUNK):
        chunk = to_run[i : i + CHUNK]
        chunk_results = await asyncio.gather(*[extract_one(client, model, e, sem) for e in chunk])
        for e, x in zip(chunk, chunk_results):
            new_results[e["edge_id"]] = x
            raw_fp.write(json.dumps({"edge": e, "extracted": x}, ensure_ascii=False) + "\n")
        raw_fp.flush()
        print(f"  [{min(i + CHUNK, len(to_run))}/{len(to_run)}] new extractions done")
    raw_fp.close()
    results = [cache.get(e["edge_id"]) or new_results.get(e["edge_id"], {"_error": "missing"}) for e in edges]

    tier_counts = {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "ERROR": 0}
    per_rel_tier: Dict[str, Dict[str, int]] = defaultdict(lambda: {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "ERROR": 0})
    approved: List[Dict[str, Any]] = []
    review_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for edge, x in zip(edges, results):
        if not isinstance(x, dict) or "_error" in x:
            tier_counts["ERROR"] += 1
            per_rel_tier[edge["relation"]]["ERROR"] += 1
            continue
        tier, reason = classify(edge, x)
        tier_counts[tier] += 1
        per_rel_tier[edge["relation"]][tier] += 1
        if tier in ("T1", "T2"):
            approved.append({"edge": edge, "extracted": x, "tier": tier})
        elif tier == "T3":
            review_groups[reason or "other"].append({"edge": edge, "extracted": x})

    # Write artifacts
    os.makedirs(os.path.dirname(OUT_APPROVED), exist_ok=True)
    with open(OUT_APPROVED, "w", encoding="utf-8") as f:
        for r in approved:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(OUT_REVIEW, "w", encoding="utf-8") as f:
        f.write("# Path B — Tier 3 review (grouped by failure pattern)\n\n")
        f.write(f"Total Tier-3 rows: {sum(len(v) for v in review_groups.values())}\n\n")
        f.write("Each group shares a single failure pattern. Decide on the **pattern** "
                "(typically a one-line rule) and that decision applies to every row in the group.\n\n")
        for reason, rows in sorted(review_groups.items(), key=lambda kv: -len(kv[1])):
            f.write(f"## Pattern: `{reason}` ({len(rows)} rows)\n\n")
            f.write("- [ ] Approve all  [ ] Reject all  [ ] Mixed — review individually\n\n")
            # show up to 12 representative rows
            for i, r in enumerate(rows[:12], 1):
                e, x = r["edge"], r["extracted"]
                v = x.get("threshold_value")
                v2 = x.get("threshold_value2")
                val_str = f"{v}..{v2}" if v2 is not None else f"{v}"
                f.write(f"<details><summary>{i}. {e['relation']} `{e['subject']}` → `{e['object']}`</summary>\n\n")
                f.write(f"- trigger: `{e.get('trigger')!r}`\n")
                f.write(f"- evidence: _{(e.get('evidence') or '').strip()}_\n")
                f.write(f"- extracted: `{x.get('threshold_param')} {x.get('threshold_op')} {val_str} {x.get('threshold_unit') or ''}`\n")
                f.write(f"- source: {e.get('source_document')}\n")
                f.write(f"- edge_id: `{e['edge_id']}`\n\n")
                f.write("</details>\n\n")
            if len(rows) > 12:
                f.write(f"_…plus {len(rows) - 12} more rows in this group._\n\n")

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("# Path B extraction summary\n\n")
        f.write(f"- Total target edges: **{total}**\n")
        f.write(f"- Model: `{model}`\n")
        f.write(f"- Concurrency: {CONCURRENCY}\n\n")
        f.write("## Tier counts\n\n")
        f.write("| Tier | Count | Disposition |\n|---|---|---|\n")
        f.write(f"| T1 literal match | {tier_counts['T1']} | auto-approve, write to KG |\n")
        f.write(f"| T2 normalised match | {tier_counts['T2']} | auto-approve via synonym table |\n")
        f.write(f"| T3 needs review | {tier_counts['T3']} | grouped review file |\n")
        f.write(f"| T4 auto-reject | {tier_counts['T4']} | string-only, no typed write |\n")
        f.write(f"| ERROR | {tier_counts['ERROR']} | re-run or investigate |\n\n")
        f.write("## Per-relation breakdown\n\n")
        f.write("| Relation | T1 | T2 | T3 | T4 | err |\n|---|---|---|---|---|---|\n")
        for rel in TARGET_RELS:
            r = per_rel_tier[rel]
            f.write(f"| {rel} | {r['T1']} | {r['T2']} | {r['T3']} | {r['T4']} | {r['ERROR']} |\n")
        f.write("\n## Tier-3 patterns\n\n")
        f.write("| Pattern | Count |\n|---|---|\n")
        for reason, rows in sorted(review_groups.items(), key=lambda kv: -len(kv[1])):
            f.write(f"| `{reason}` | {len(rows)} |\n")

    print(f"\nDone.\n  approved: {OUT_APPROVED}\n  review:   {OUT_REVIEW}\n  summary:  {OUT_SUMMARY}")
    print(f"  tier counts: {tier_counts}")


if __name__ == "__main__":
    asyncio.run(main())
