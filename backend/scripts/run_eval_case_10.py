"""Non-interactive runner for EVALUATION_FRAMEWORK_README.md Case 10.

HTN in Pregnancy + GDM — Teratogen KG-Veto on Current Med.

The patient was on losartan for pre-existing HTN *before* the pregnancy was
known; the booking visit at 30 weeks surfaces both GDM and elevated BP. The
system must audit the existing medication list against the patient's current
state (pregnant + female + GA 30w) and STOP losartan from the KG-sourced
`(:Drug)-[:CONTRAINDICATED_WITH]->(:Condition)` edge — even though the
clinician did not ask about losartan. That is the case-10 showcase: vetoing
a drug the patient is actively taking, not one a clinician proposed.

Pipeline aspects exercised here that cases 8/9 do not exercise:
  * Pregnancy CPG context filter (`pregnancy_context_missing_reason`) —
    Heart-Disease-in-Pregnancy(2nd Edition) + Diabetes-in-Pregnancy(2017)
    must NOT be excluded for this case (they are excluded for cases 8/9).
  * Sex-aware routing (female + pregnancy → obstetric CPGs invoked).
  * KG teratogen veto on an existing med (the harder safety direction).
  * Cross-CPG bridge on PPCM family history (Heart-Disease-in-Pregnancy).
  * Mode-A/B framing: the chief complaint is a "booking visit + management
    plan", which is task-framed but does NOT trigger
    `_TASK_FRAMED_MARKERS` — case 10 therefore exercises Stage-2 stability
    Layers 1–3 (seed-pin, regex disease fallback, phrase cache) WITHOUT the
    Layer-4 Mode-B rule-based bypass. Intentional: gives a holdout for the
    LLM-path determinism claim independent of case 9.

Usage:
    python scripts/run_eval_case_10.py             # uses http://localhost:8058
    python scripts/run_eval_case_10.py --url http://localhost:8000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tasks" / "eval_runs"

# Fixture mirrors EVALUATION_FRAMEWORK_README.md Case 10 (Doctor UI Step-1 schema).
# Notes that don't fit a UI slot (OGTT, urinalysis, family history, BP confirmation)
# live inside the `history` blob so they reach Stage 2 / Stage 5 verbatim.
CASE_10 = {
    "chief_complaint": (
        "Booking visit at 30 weeks (late booker). BP elevated; GDM diagnosed on OGTT. "
        "Plan for HTN + GDM management."
    ),
    "history": (
        "CC: Booking visit at 30 weeks (late booker). BP elevated; GDM diagnosed on OGTT. "
        "Plan for HTN + GDM management.\n"
        "HPI: Primigravida, 30 weeks gestation by dates. Losartan started 2 years ago, "
        "before pregnancy was known. No headache, visual symptoms, or RUQ pain. "
        "No dyspnoea, orthopnoea, or oedema beyond physiological.\n"
        "PE / Labs: BP 158/104 confirmed on 2 readings 4h apart. Fasting glucose "
        "7.4 mmol/L, OGTT 2h 11.2 mmol/L. Urinalysis: no proteinuria.\n"
        "FHx: Sister had peripartum cardiomyopathy (PPCM)."
    ),
    "age": 35,
    "sex": "F",
    "comorbidities": [
        "Essential Hypertension (pre-existing 2 years)",
        "Gestational Diabetes Mellitus (newly diagnosed)",
        "Pregnancy 30 weeks (primigravida)",
    ],
    "current_medications": [
        "Losartan 50mg OD",
    ],
    "allergies": [],
    "vitals": {
        "sbp": 158,
        "dbp": 104,
        "hr": 88,
        "spO2": 98,
        "weight": 78,
        "temp": 36.8,
    },
    "severity_staging": {
        "eGFR": "102",
        "WHO Pregnancy Risk Class": "II",
    },
}


async def stream_case(url: str) -> tuple[list[dict], dict | None]:
    """Mirror of case 8/9 stream_case — same SSE wire protocol, same parse loop.

    Reuses the raw-byte chunked reader so large safety_review payloads
    (case 10 tends to produce big LLM-flag JSON given the teratogen + PPCM
    surface) don't hit aiohttp line-length limits.
    """
    events: list[dict] = []
    final_result: dict | None = None
    timeout = aiohttp.ClientTimeout(total=900, connect=10)
    headers = {"Connection": "close", "Accept": "text/event-stream"}
    payload = {"case": CASE_10}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{url}/clinical/plan/stream", json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"HTTP {resp.status}: {text}")
                sys.exit(1)
            ev_type = None
            buffer = b""
            async for chunk in resp.content.iter_chunked(8192):
                buffer += chunk
                lines = buffer.split(b"\n")
                buffer = lines[-1]
                for line_bytes in lines[:-1]:
                    s = line_bytes.decode("utf-8").strip()
                    if not s:
                        continue
                    if s.startswith("event:"):
                        ev_type = s[6:].strip()
                    elif s.startswith("data:") and ev_type:
                        data_str = s[5:].strip()
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            ev_type = None
                            continue
                        events.append({"event": ev_type, "data": data})
                        if ev_type == "stage_update":
                            status = data.get("status")
                            stage = data.get("stage")
                            name = data.get("name", "")
                            if status == "running":
                                print(f"[Stage {stage}] {name} >>")
                            elif status == "complete":
                                print(f"[Stage {stage}] {name} OK")
                            elif status == "error":
                                print(f"[Stage {stage}] {name} ERR")
                        elif ev_type == "sub_step":
                            print(f"  -> {data.get('detail','')}")
                        elif ev_type == "final_result":
                            final_result = data
                        elif ev_type == "error":
                            print(f"ERROR: {data}")
                        elif ev_type == "done":
                            ev_type = None
                            break
                        ev_type = None
            if buffer.strip():
                s = buffer.decode("utf-8").strip()
                if s.startswith("data:") and ev_type:
                    data_str = s[5:].strip()
                    try:
                        data = json.loads(data_str)
                        events.append({"event": ev_type, "data": data})
                        if ev_type == "final_result":
                            final_result = data
                    except json.JSONDecodeError:
                        pass
    return events, final_result


def _summarise_showcase_checks(plan: dict, safety: dict) -> list[str]:
    """Quick pass/fail readout for the case-10 differentiators.

    Not a pytest assertion — just a human-readable scorecard appended to the
    summary so a reader can immediately see whether the four core showcase
    behaviours actually fired this run. Useful when batching reruns through
    the stability harness.
    """
    lines: list[str] = []
    recs = plan.get("recommendations") or []
    flags = safety.get("flags") or []

    losartan_stop = any(
        (r.get("action") or "").lower() == "stop"
        and "losartan" in (r.get("intervention") or "").lower()
        for r in recs
    )
    safe_alt_started = any(
        (r.get("action") or "").lower() == "start"
        and any(
            agent in (r.get("intervention") or "").lower()
            for agent in ("labetalol", "methyldopa", "nifedipine")
        )
        for r in recs
    )
    teratogen_flag = any(
        "losartan" in ((f.get("title") or "") + (f.get("detail") or "")).lower()
        or "arb" in ((f.get("title") or "") + (f.get("detail") or "")).lower()
        or "ace" in ((f.get("title") or "") + (f.get("detail") or "")).lower()
        for f in flags
    )
    obstetric_referral = any(
        (r.get("type") or "").lower() == "referral"
        and any(
            kw in ((r.get("specialty") or "") + (r.get("intervention") or "")).lower()
            for kw in ("maternal", "obstetric", "o&g", "ogn", "foetal", "fetal")
        )
        for r in recs
    )

    lines.append(f"- STOP losartan present:           {'YES' if losartan_stop else 'NO'}")
    lines.append(f"- Safe-in-pregnancy antiHTN START: {'YES' if safe_alt_started else 'NO'}")
    lines.append(f"- Teratogen/ARB safety flag fired: {'YES' if teratogen_flag else 'NO'}")
    lines.append(f"- Obstetric referral present:      {'YES' if obstetric_referral else 'NO'}")
    return lines


def write_summary(md_path: Path, final: dict) -> None:
    """Render the run as a Markdown summary alongside the JSON trace.

    Structure follows cases 8/9 so the eval_runs/ folder stays uniformly
    diffable, with one extra section ("Showcase capability checks") that
    surfaces the case-10-specific clinical expectations defined in
    EVALUATION_FRAMEWORK_README.md §Case 10.
    """
    plan = final.get("treatment_plan", {}) or {}
    ddx = final.get("ddx", []) or []
    safety = final.get("safety_report") or {}
    cpgs_matched = final.get("cpgs_matched", []) or []

    lines: list[str] = []
    lines.append("# Case 10 Run — HTN in Pregnancy + GDM (Teratogen KG-Veto)")
    lines.append("")
    lines.append(f"- Run at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- elapsed_ms: {final.get('elapsed_ms', 0)}")
    lines.append(f"- ICD primary: {plan.get('icd_primary', 'n/a')}")
    lines.append(f"- Confidence: {plan.get('confidence', 0)}")
    lines.append("")

    lines.append("## DDx top 5 (LLM-reranked)")
    for i, d in enumerate(ddx[:5], 1):
        final_score = d.get("final_score")
        sim = d.get("similarity") or d.get("probability") or 0
        math_rank = d.get("math_rank")
        score_str = f"final={final_score:.3f}" if isinstance(final_score, (int, float)) else f"sim={sim:.3f}"
        rank_str = f", math_rank={math_rank}" if math_rank else ""
        lines.append(f"{i}. {d.get('code','')} — {d.get('title','')} ({score_str}{rank_str})")
    lines.append("")

    lines.append("## CPGs matched")
    if cpgs_matched:
        for c in cpgs_matched:
            if isinstance(c, dict):
                lines.append(f"- {c.get('cpg_name','?')} (score={c.get('score','?')})")
            else:
                lines.append(f"- {c}")
    else:
        lines.append("- (none reported)")
    lines.append("")

    lines.append("## Summary")
    lines.append(plan.get("summary", "(none)"))
    lines.append("")

    lines.append("## Recommendations")
    for r in plan.get("recommendations", []) or []:
        action = (r.get("action") or "?").upper()
        lines.append(
            f"- [{action}] {r.get('intervention','')} — "
            f"{r.get('rationale','')} (src: {r.get('cpg_source','')}, grade: {r.get('evidence_grade','')})"
        )
    lines.append("")

    lines.append("## Monitoring")
    for m in plan.get("monitoring", []) or []:
        if isinstance(m, dict):
            lines.append(f"- {m.get('parameter','?')}: {m.get('schedule','')} target={m.get('target','')}")
        else:
            lines.append(f"- {m}")
    lines.append("")

    lines.append("## Safety Flags")
    llm_count = 0
    graph_count = 0
    for f in (safety.get("flags") or []):
        title = f.get('title') or f.get('flag_type', '?')
        detail = f.get('detail') or f.get('issue', '')
        severity = f.get('severity', '?')
        source = f.get('source', '?')
        if source == "llm":
            llm_count += 1
        elif source == "graph":
            graph_count += 1
        lines.append(f"- [{severity}/{source}] {title}")
        if detail:
            lines.append(f"  {detail}")
    lines.append("")
    lines.append(f"- safe_to_proceed: {safety.get('safe_to_proceed')}")
    lines.append(f"- flag source counts: llm={llm_count}, graph={graph_count}")
    lines.append("")

    lines.append("## Unresolved")
    for u in plan.get("unresolved_questions", []) or []:
        lines.append(f"- {u}")
    lines.append("")

    audit = plan.get("gate_audit", []) or []
    if audit:
        lines.append("## Gate audit (ruled out)")
        for a in audit:
            lines.append(f"- {a}")
        lines.append("")

    # Case-10-specific clinical expectations — see EVALUATION_FRAMEWORK_README.md §Case 10.
    lines.append("## Showcase capability checks")
    lines.extend(_summarise_showcase_checks(plan, safety))

    md_path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8058")
    args = parser.parse_args()
    url = args.url.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = OUT_DIR / f"case10_{stamp}_trace.json"
    summary_path = OUT_DIR / f"case10_{stamp}_summary.md"

    t0 = time.monotonic()
    events, final = await stream_case(url)
    elapsed = time.monotonic() - t0

    trace_path.write_text(
        json.dumps({"case": CASE_10, "events": events, "final": final}, indent=2),
        encoding="utf-8",
    )
    if final:
        write_summary(summary_path, final)
        print(f"\nWrote {summary_path}")
    print(f"Wrote {trace_path}")
    print(f"Total wall time: {elapsed:.1f}s")
    return 0 if final else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
