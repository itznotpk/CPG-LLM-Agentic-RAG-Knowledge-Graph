"""
Silent-degradation and infrastructure-robustness probes for TESTING_STRATEGY.md.

These are mock-based, single-failure probes. They do not break real services.
They ask whether the current code surfaces degradation clearly enough when an
internal dependency or stage fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from agent.clinical_stages import DDxResult, _llm_rerank_ddx
from agent.clinical_workflow import run_clinical_workflow, run_clinical_workflow_streaming
from agent.models import PatientCase, Recommendation, SafetyReport, TreatmentPlan
from agent.routing import CPGDocRef
from agent.safety_critic import run_safety_critic
from eval.io_utils import print_summary, write_results


def _case() -> PatientCase:
    return PatientCase(
        chief_complaint="chest pain for 2 hours",
        age=62,
        sex="M",
        comorbidities=["hypertension"],
        vitals={"systolic_bp": 142, "diastolic_bp": 88, "heart_rate": 86},
    )


def _ddx() -> list[DDxResult]:
    return [
        DDxResult(code="BA41.1", title="Acute non-ST elevation myocardial infarction", similarity=0.87),
        DDxResult(code="BA40.0", title="Unstable angina", similarity=0.79),
    ]


def _cpgs() -> list[CPGDocRef]:
    return [
        CPGDocRef(
            cpg_name="NSTE-ACS(3rd Edition)",
            document_id="doc-nste",
            document_ids=["doc-nste"],
            title="NSTE-ACS(3rd Edition)",
            match_type="exact",
            score=0.9,
            matched_scope="BA41.1",
        )
    ]


def _plan(confidence: float = 0.9, unresolved: list[str] | None = None) -> TreatmentPlan:
    return TreatmentPlan(
        icd_primary="BA41.1",
        summary="Confident ACS plan generated for synthetic degradation probe.",
        recommendations=[
            Recommendation(
                intervention="Aspirin 300 mg stat then 100 mg OD",
                type="pharmacological",
                action="start",
                cpg_source="Synthetic ACS CPG",
                rationale="Synthetic recommendation for degradation probe.",
            )
        ],
        confidence=confidence,
        unresolved_questions=unresolved or [],
    )


def _mock_llm_client(payload: dict | str):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock(content=content)
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


async def _sil01() -> dict:
    """Malformed Stage 2 rerank response should emit explicit fallback/degraded signal."""
    events: list[tuple[str, dict]] = []

    async def emit(event_type, data):
        events.append((event_type, data))

    async def bad_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock(content="this is not valid rerank JSON", reasoning=None, thinking=None, reasoning_content=None)
        yield chunk

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=bad_stream())

    with patch("agent.clinical_stages.openai.AsyncOpenAI", return_value=fake_client):
        result = await _llm_rerank_ddx(_case(), _ddx(), emit=emit)

    event_blob = json.dumps(events, default=str).lower()
    degraded_signal = any(k in event_blob for k in ["degraded", "fallback", "warning", "rerank fallback"])
    preserved_order = [r.code for r in result] == [r.code for r in _ddx()]
    ok = degraded_signal and preserved_order
    return {
        "id": "SIL-01",
        "class": "silent degradation",
        "pass": float(ok),
        "reason": f"preserved_order={preserved_order}; degraded_signal={degraded_signal}; events={event_blob[:220] or 'none'}",
        "elapsed_min": 0.0,
    }


async def _sil02() -> dict:
    """0 retrieval chunks should not lead to a confident final plan."""
    with (
        patch("agent.clinical_workflow.stage_2_ddx", new=AsyncMock(return_value=_ddx())),
        patch("agent.clinical_workflow.stage_3_route", new=AsyncMock(return_value=_cpgs())),
        patch("agent.clinical_workflow.route_comorbidities", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_4_retrieve", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.extract_candidate_drugs_from_chunks", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.clinical_graph_lookup", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.get_graph_constraints", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_5_synthesize", new=AsyncMock(return_value=_plan(confidence=0.92))),
        patch("agent.safety_critic.run_safety_critic", new=AsyncMock(return_value=SafetyReport(flags=[], safe_to_proceed=True))),
    ):
        result = await run_clinical_workflow(_case())

    confident_from_empty = len(result.evidence) == 0 and result.treatment_plan.confidence >= 0.3 and not result.treatment_plan.unresolved_questions
    ok = not confident_from_empty
    return {
        "id": "SIL-02",
        "class": "silent degradation",
        "pass": float(ok),
        "reason": (
            f"evidence_chunks={len(result.evidence)}; confidence={result.treatment_plan.confidence}; "
            f"unresolved={len(result.treatment_plan.unresolved_questions)}; confident_from_empty={confident_from_empty}"
        ),
        "elapsed_min": round(result.elapsed_ms / 60000, 2),
    }


async def _sil03() -> dict:
    """KG safety failure should be labelled as partial/degraded while LLM critic still clears."""
    report = await _safety_with_kg_failure()
    note = (report.reviewer_notes or "").lower()
    labelled = report.kg_verification_degraded and any(k in note for k in ["neo4j", "unavailable", "skipped", "degraded"])
    ok = labelled and report.safe_to_proceed
    return {
        "id": "SIL-03",
        "class": "silent degradation",
        "pass": float(ok),
        "reason": f"kg_degraded={report.kg_verification_degraded}; safe_to_proceed={report.safe_to_proceed}; notes={report.reviewer_notes}",
        "elapsed_min": 0.0,
    }


async def _safety_with_kg_failure() -> SafetyReport:
    case = PatientCase(
        chief_complaint="atrial fibrillation follow-up",
        age=68,
        sex="M",
        comorbidities=["Atrial fibrillation"],
        current_medications=["aspirin"],
    )
    plan = TreatmentPlan(
        icd_primary="BC81.3",
        summary="AF anticoagulation plan.",
        recommendations=[
            Recommendation(
                intervention="Warfarin 5 mg OD",
                type="pharmacological",
                action="start",
                cpg_source="AF CPG",
                rationale="Stroke prevention.",
            )
        ],
        confidence=0.8,
    )
    with (
        patch("agent.safety_critic.openai.AsyncOpenAI", return_value=_mock_llm_client({"flags": [], "safe_to_proceed": True, "reviewer_notes": None})),
        patch("agent.safety_critic.match_plan_drugs", new=AsyncMock(side_effect=RuntimeError("neo4j connection refused"))),
    ):
        return await run_safety_critic(case, plan)


async def _inf01() -> dict:
    """Neo4j outage should be clearly labelled, not silently treated as clean graph pass."""
    report = await _safety_with_kg_failure()
    note = (report.reviewer_notes or "").lower()
    labelled = report.kg_verification_degraded and "neo4j" in note and "unavailable" in note
    return {
        "id": "INF-01",
        "class": "infrastructure failure",
        "pass": float(labelled),
        "reason": f"kg_degraded={report.kg_verification_degraded}; notes={report.reviewer_notes}",
        "elapsed_min": 0.0,
    }


async def _inf02() -> dict:
    """Embedding 429 should not silently continue to Stage 5 with empty evidence."""
    stage5_called = False

    async def fake_stage5(*args, **kwargs):
        nonlocal stage5_called
        stage5_called = True
        return _plan(confidence=0.91)

    with (
        patch("agent.clinical_workflow.stage_2_ddx", new=AsyncMock(return_value=_ddx())),
        patch("agent.clinical_workflow.stage_3_route", new=AsyncMock(return_value=_cpgs())),
        patch("agent.clinical_workflow.route_comorbidities", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_4_retrieve", new=AsyncMock(side_effect=RuntimeError("Bedrock embedding 429 rate limit"))),
        patch("agent.clinical_workflow.extract_candidate_drugs_from_chunks", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.clinical_graph_lookup", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.get_graph_constraints", new=AsyncMock(return_value=[])),
        patch("agent.clinical_workflow.stage_5_synthesize", new=fake_stage5),
        patch("agent.safety_critic.run_safety_critic", new=AsyncMock(return_value=SafetyReport(flags=[], safe_to_proceed=True))),
    ):
        result = await run_clinical_workflow(_case())

    errors = "|".join(f"{e.stage}:{e.message}" for e in result.stage_errors).lower()
    has_error = "429" in errors or "embedding" in errors
    ok = has_error and not stage5_called
    return {
        "id": "INF-02",
        "class": "infrastructure failure",
        "pass": float(ok),
        "reason": f"stage_error_labelled={has_error}; stage5_called={stage5_called}; stage_errors={errors}",
        "elapsed_min": round(result.elapsed_ms / 60000, 2),
    }


async def _inf03() -> dict:
    """pgvector outage should produce HTTP 503 rather than generic 500."""
    from agent.api import app

    with patch("agent.clinical_workflow.run_clinical_workflow", new=AsyncMock(side_effect=ConnectionError("pgvector connection refused"))):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/clinical/plan", json={"case": {"chief_complaint": "chest pain"}})

    ok = resp.status_code == 503
    return {
        "id": "INF-03",
        "class": "infrastructure failure",
        "pass": float(ok),
        "reason": f"status_code={resp.status_code}; expected=503; body={resp.text[:180]}",
        "elapsed_min": 0.0,
    }


CASES = {
    "SIL-01": _sil01,
    "SIL-02": _sil02,
    "SIL-03": _sil03,
    "INF-01": _inf01,
    "INF-02": _inf02,
    "INF-03": _inf03,
}


async def main(ids: list[str] | None = None):
    selected = [i.upper() for i in ids] if ids else list(CASES)
    rows = []
    for case_id in selected:
        fn = CASES[case_id]
        print(f"[run] {case_id}...", flush=True)
        t0 = time.monotonic()
        try:
            row = await fn()
            if not row.get("elapsed_min"):
                row["elapsed_min"] = round((time.monotonic() - t0) / 60, 2)
        except Exception as exc:
            row = {
                "id": case_id,
                "class": "unknown",
                "pass": 0.0,
                "reason": f"runner_exception={type(exc).__name__}: {exc}",
                "elapsed_min": round((time.monotonic() - t0) / 60, 2),
            }
        rows.append(row)
        print(f"[{'PASS' if row['pass'] else 'FAIL'}] {case_id} {row['reason']}", flush=True)

    n = len(rows)
    passed = sum(r["pass"] for r in rows)
    summary = {
        "n": n,
        "passes": int(passed),
        "pass_rate": (passed / n) if n else 0.0,
        "mean_elapsed_min": sum(r["elapsed_min"] for r in rows) / n if n else 0.0,
    }
    suite_prefixes = {r["id"].split("-", 1)[0].lower() for r in rows}
    name = suite_prefixes.pop() if len(suite_prefixes) == 1 else "sil_inf"
    print_summary(f"Degradation/infra {name.upper()}", summary)
    write_results(f"degradation_{name}", rows, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", help="Optional case IDs: SIL-01 SIL-02 INF-01 ...")
    args = parser.parse_args()
    asyncio.run(main(args.ids))
