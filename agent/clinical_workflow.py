"""
Clinical workflow orchestrator.
Calls pipeline stages 2–5 sequentially and returns a TreatmentPlan.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field

from .models import PatientCase, TreatmentPlan, SafetyReport
from .clinical_stages import DDxResult, _build_symptom_text, stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize  # noqa: F401 (stage_2_ddx imported for test patching)
from .graph_clinical import clinical_graph_lookup, extract_candidate_drugs_from_chunks
from .routing import CPGDocRef, route_icd_to_cpgs

logger = logging.getLogger(__name__)


async def route_comorbidities(
    comorbidities: list[str],
    existing_cpgs: list[CPGDocRef],
    top_k: int = 2,
    patient_sex: str | None = None,
    emit=None,
) -> list[CPGDocRef]:
    """Map free-text comorbidity names to additional CPG documents.

    For each comorbidity, run a DDx lookup (top_k=3) to obtain an ICD-11 code,
    then route that code to CPGs. Skips matches below similarity 0.55 to prevent
    semantic-fallback drift (e.g. DM/CKD routing to Breast Cancer CPG).
    Deduplicated against existing_cpgs. Sex-incompatible CPGs (e.g. a pregnancy CPG
    for a male patient) are dropped and surfaced in the trace.
    """
    from ddx.search_ddx import search_ddx
    from .clinical_stages import sex_incompatible_reason
    additional: list[CPGDocRef] = []
    existing_names = {c.cpg_name for c in existing_cpgs}
    sex_excluded: set[str] = set()
    for condition in comorbidities[:4]:           # cap at 4 to limit latency
        if not condition.strip():
            continue
        try:
            hits = await search_ddx(condition, top_k=3)
            logger.info(
                "Comorbidity %r → DDx candidates: %s",
                condition,
                [(h.get("code"), h.get("title"), round(h.get("similarity", 0), 3)) for h in hits[:3]],
            )
            if not hits:
                continue

            top = hits[0]
            top_similarity = top.get("similarity", 0)
            if top_similarity < 0.55:
                logger.warning(
                    "Comorbidity %r — top DDx %s (%s) similarity %.3f below 0.55 threshold; skipping",
                    condition, top.get("code"), top.get("title"), top_similarity,
                )
                continue

            refs = await route_icd_to_cpgs(top.get("code"), top_k=top_k)
            logger.info(
                "Comorbidity %r → ICD %s → CPGs: %s (match_types=%s)",
                condition, top.get("code"),
                [r.cpg_name for r in refs],
                [r.match_type for r in refs],
            )

            for ref in refs:
                if ref.cpg_name in existing_names:
                    continue
                reason = sex_incompatible_reason(ref.cpg_name, patient_sex)
                if reason is not None:
                    if ref.cpg_name not in sex_excluded:
                        sex_excluded.add(ref.cpg_name)
                        logger.info(
                            "Comorbidity sex-filter excluded %s (via %r): %s",
                            ref.cpg_name, condition, reason,
                        )
                        if emit:
                            await emit("sub_step", {
                                "stage": 3,
                                "detail": f"Excluded {ref.cpg_name} — {reason}",
                                "badge": "excluded",
                                "status": "complete",
                            })
                    continue
                additional.append(ref)
                existing_names.add(ref.cpg_name)
        except Exception as exc:
            logger.warning("Comorbidity routing failed for %r: %s", condition, exc)
    return additional


@dataclass
class WorkflowResult:
    treatment_plan: TreatmentPlan
    ddx: list[DDxResult]
    cpgs: list[CPGDocRef]
    elapsed_ms: float
    stage_errors: list[str] = field(default_factory=list)
    safety_report: SafetyReport | None = None


async def run_clinical_workflow(case: PatientCase) -> WorkflowResult:
    """
    Run the full clinical workflow for a patient case.

    Stages:
        2 — DDx: symptoms → ICD-11 candidates (vector + Gemini 2.5 Flash thinking re-rank)
        3 — Route: ICD codes → CPG document IDs
        4 — Retrieve: scoped vector search with LLM-generated queries
        5 — Synthesize: TreatmentPlan structured output

    Raises:
        RuntimeError if Stage 5 synthesis fails (unrecoverable).
        All other stage failures are caught, logged, and the pipeline continues
        with degraded output rather than crashing.
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # Stage 2 — DDx
    try:
        ddx = await stage_2_ddx(case, top_k=5)
        logger.info("Stage 2 DDx: %d candidates. Top: %s",
                    len(ddx), ddx[0].code if ddx else "none")
    except Exception as e:
        logger.error("Stage 2 DDx failed: %s", e)
        errors.append(f"Stage 2 DDx: {e}")
        ddx = []

    # Stage 3 — Route
    try:
        cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3,
                                   clinical_context=_build_symptom_text(case),
                                   patient_sex=case.sex)
        extra_cpgs = await route_comorbidities(case.comorbidities, cpgs, patient_sex=case.sex)
        if extra_cpgs:
            cpgs = cpgs + extra_cpgs
        logger.info("Stage 3 Routing: %d CPGs matched: %s",
                    len(cpgs), [c.cpg_name for c in cpgs])
    except Exception as e:
        logger.error("Stage 3 Routing failed: %s", e)
        errors.append(f"Stage 3 Routing: {e}")
        cpgs = []

    # Stage 4 — Retrieve
    try:
        evidence = await stage_4_retrieve(case, ddx, cpgs)
        logger.info("Stage 4 Retrieval: %d evidence chunks", len(evidence))
    except Exception as e:
        logger.error("Stage 4 Retrieval failed: %s", e)
        errors.append(f"Stage 4 Retrieval: {e}")
        evidence = []

    # KG lookup — runs between Stage 4 and Stage 5, fail-open
    try:
        _chunk_ids = [c.chunk_id for c in evidence]
        _candidate_drugs = await extract_candidate_drugs_from_chunks(_chunk_ids)
        kg_flags = await clinical_graph_lookup(
            patient_meds=case.current_medications,
            candidate_drugs=_candidate_drugs,
            comorbidities=case.comorbidities,
            allergies=case.allergies,
        )
        logger.info("KG lookup: %d flags", len(kg_flags))
    except Exception as e:
        logger.warning("KG lookup failed (non-fatal): %s", e)
        kg_flags = []

    # Stage 5 — Synthesize (unrecoverable if it fails)
    treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence, flags=kg_flags)

    # Stage 6 — Safety review (fail-open, never raises)
    from .safety_critic import run_safety_critic
    safety_report = await run_safety_critic(case, treatment_plan)

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info("Workflow complete in %.0f ms. ICD primary: %s",
                elapsed_ms, treatment_plan.icd_primary)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
        safety_report=safety_report,
    )


async def run_ddx_only_streaming(
    case: PatientCase,
    emit,                           # async callable: emit(event_type: str, data: dict) -> None
) -> list[DDxResult]:
    """
    Stop-and-confirm phase 1: run ONLY Stage 2 (DDx) and stream it, then stop.

    The clinician reviews the ranked top-k, confirms or overrides, and the UI then
    calls the resynthesize path (Stages 3–5) on the agreed diagnosis. This keeps the
    expensive, authoritative care plan from ever being generated against an
    unvalidated diagnosis.

    Emits the same Stage-2 events as the full workflow, plus a terminal `ddx_ready`
    event carrying the candidate list so the caller can render the confirmation gate.
    Never raises — on Stage-2 failure it emits an error stage_update and returns [].
    """
    await emit("stage_update", {
        "stage": 2, "name": "DDx Analysis",
        "status": "running", "detail": "Analyzing symptoms and history…"
    })
    try:
        ddx = await stage_2_ddx(case, top_k=5, emit=emit)
        top = ddx[0].code if ddx else "none"
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "complete",
            "detail": f"{len(ddx)} candidates · top: {top}",
            "data": [d.model_dump() for d in ddx],
        })
        logger.info("DDx-only Stage 2: %d candidates. Top: %s", len(ddx), top)
    except Exception as e:
        logger.error("DDx-only Stage 2 failed: %s", e)
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "error", "detail": str(e),
        })
        ddx = []

    # Terminal event: hand the candidates to the UI gate. Pipeline pauses here.
    await emit("ddx_ready", {"ddx": [d.model_dump() for d in ddx]})
    return ddx


async def run_clinical_workflow_streaming(
    case: PatientCase,
    emit,                           # async callable: emit(event_type: str, data: dict) -> None
) -> WorkflowResult:
    """
    Streaming variant of run_clinical_workflow.

    Calls emit() before and after each stage so callers can push SSE events.
    Also threads emit into stage_2_ddx so Gemini thinking tokens stream live.
    Same error-handling contract as run_clinical_workflow.
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # Stage 2 — DDx
    await emit("stage_update", {
        "stage": 2, "name": "DDx Analysis",
        "status": "running", "detail": "Analyzing symptoms and history…"
    })
    try:
        ddx = await stage_2_ddx(case, top_k=5, emit=emit)
        top = ddx[0].code if ddx else "none"
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "complete",
            "detail": f"{len(ddx)} candidates · top: {top}",
            "data": [d.model_dump() for d in ddx],
        })
        logger.info("Stage 2 DDx: %d candidates. Top: %s", len(ddx), top)
    except Exception as e:
        logger.error("Stage 2 DDx failed: %s", e)
        errors.append(f"Stage 2 DDx: {e}")
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "error", "detail": str(e),
        })
        ddx = []

    # Stage 3 — Route
    await emit("stage_update", {
        "stage": 3, "name": "CPG Routing",
        "status": "running", "detail": "Matching ICD codes to clinical guidelines…"
    })
    try:
        cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3, emit=emit,
                                   clinical_context=_build_symptom_text(case),
                                   patient_sex=case.sex)
        extra_cpgs = await route_comorbidities(case.comorbidities, cpgs, patient_sex=case.sex, emit=emit)
        if extra_cpgs:
            cpgs = cpgs + extra_cpgs
            for c in extra_cpgs:
                await emit("sub_step", {"stage": 3, "detail": c.cpg_name, "badge": "comorbidity"})
        names = [c.cpg_name for c in cpgs]
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "complete",
            "detail": f"{len(cpgs)} CPGs matched: {', '.join(names)}",
            "data": names,
        })
        logger.info("Stage 3 Routing: %d CPGs: %s", len(cpgs), names)
    except Exception as e:
        logger.error("Stage 3 Routing failed: %s", e)
        errors.append(f"Stage 3 Routing: {e}")
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "error", "detail": str(e),
        })
        cpgs = []

    # Stage 4 — Retrieve
    await emit("stage_update", {
        "stage": 4, "name": "Evidence Retrieval",
        "status": "running", "detail": "Retrieving relevant guideline chunks…"
    })
    try:
        evidence = await stage_4_retrieve(case, ddx, cpgs, emit=emit)
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "complete",
            "detail": f"{len(evidence)} evidence chunks retrieved",
        })
        logger.info("Stage 4 Retrieval: %d chunks", len(evidence))
    except Exception as e:
        logger.error("Stage 4 Retrieval failed: %s", e)
        errors.append(f"Stage 4 Retrieval: {e}")
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "error", "detail": str(e),
        })
        evidence = []

    # KG lookup — runs between Stage 4 and Stage 5, fail-open
    try:
        _chunk_ids = [c.chunk_id for c in evidence]
        _candidate_drugs = await extract_candidate_drugs_from_chunks(_chunk_ids)
        kg_flags = await clinical_graph_lookup(
            patient_meds=case.current_medications,
            candidate_drugs=_candidate_drugs,
            comorbidities=case.comorbidities,
            allergies=case.allergies,
        )
        logger.info("KG lookup: %d flags", len(kg_flags))
    except Exception as e:
        logger.warning("KG lookup failed (non-fatal): %s", e)
        kg_flags = []

    # Stage 5 — Synthesize (unrecoverable if it fails)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan…"
    })
    treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence, flags=kg_flags)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms total",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, 'confidence') and treatment_plan.confidence else None,
    })
    logger.info("Workflow complete in %.0f ms", elapsed_ms)

    # Stage 6 — Safety review (fail-open, never raises)
    from .safety_critic import run_safety_critic
    safety_report = await run_safety_critic(case, treatment_plan, emit=emit)
    await emit("safety_review", safety_report.model_dump())

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
        safety_report=safety_report,
    )


async def run_resynthesize_streaming(
    case: PatientCase,
    selected_ddx: list[DDxResult],
    emit,
) -> WorkflowResult:
    """
    Re-run Stages 3–5 with clinician-selected diagnoses.

    Stage 2 (DDx) is intentionally skipped — the clinician's selection overrides the AI.
    Emits a clinician_override event first so the UI can show what changed.
    Same fault-tolerance contract as run_clinical_workflow_streaming for stages 3–4.
    Stage 5 failure propagates (unrecoverable).
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # Signal the override to the UI — must be the first event
    await emit("clinician_override", {
        "codes": [f"{d.code} {d.title}" for d in selected_ddx],
    })

    # Stage 3 — Route using clinician codes
    await emit("stage_update", {
        "stage": 3, "name": "CPG Routing",
        "status": "running",
        "detail": f"Routing {len(selected_ddx)} clinician-selected code(s)…",
    })
    try:
        cpgs = await stage_3_route(selected_ddx, top_k_codes=len(selected_ddx), top_k_cpgs=3, emit=emit,
                                   clinical_context=_build_symptom_text(case),
                                   patient_sex=case.sex)
        names = [c.cpg_name for c in cpgs]
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "complete",
            "detail": f"{len(cpgs)} CPGs matched: {', '.join(names)}",
            "data": names,
        })
        logger.info("Re-synth Stage 3 Routing: %d CPGs: %s", len(cpgs), names)
    except Exception as e:
        logger.error("Re-synth Stage 3 failed: %s", e)
        errors.append(f"Stage 3 Routing: {e}")
        await emit("stage_update", {"stage": 3, "name": "CPG Routing", "status": "error", "detail": str(e)})
        cpgs = []

    # Stage 4 — Retrieve
    await emit("stage_update", {
        "stage": 4, "name": "Evidence Retrieval",
        "status": "running", "detail": "Retrieving guideline evidence for selected diagnosis…",
    })
    try:
        evidence = await stage_4_retrieve(case, selected_ddx, cpgs, emit=emit)
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "complete",
            "detail": f"{len(evidence)} evidence chunks retrieved",
        })
        logger.info("Re-synth Stage 4 Retrieval: %d chunks", len(evidence))
    except Exception as e:
        logger.error("Re-synth Stage 4 failed: %s", e)
        errors.append(f"Stage 4 Retrieval: {e}")
        await emit("stage_update", {"stage": 4, "name": "Evidence Retrieval", "status": "error", "detail": str(e)})
        evidence = []

    # KG lookup — runs between Stage 4 and Stage 5, fail-open
    try:
        _chunk_ids = [c.chunk_id for c in evidence]
        _candidate_drugs = await extract_candidate_drugs_from_chunks(_chunk_ids)
        kg_flags = await clinical_graph_lookup(
            patient_meds=case.current_medications,
            candidate_drugs=_candidate_drugs,
            comorbidities=case.comorbidities,
            allergies=case.allergies,
        )
        logger.info("KG lookup: %d flags", len(kg_flags))
    except Exception as e:
        logger.warning("KG lookup failed (non-fatal): %s", e)
        kg_flags = []

    # Stage 5 — Synthesize (unrecoverable)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan for confirmed diagnosis…",
    })
    treatment_plan = await stage_5_synthesize(case, selected_ddx, cpgs, evidence, flags=kg_flags)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, "confidence") and treatment_plan.confidence else None,
    })
    logger.info("Re-synthesis complete in %.0f ms", elapsed_ms)

    # Stage 6 — Safety review (fail-open, never raises)
    from .safety_critic import run_safety_critic
    safety_report = await run_safety_critic(case, treatment_plan, emit=emit)
    await emit("safety_review", safety_report.model_dump())

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=selected_ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
        safety_report=safety_report,
    )
