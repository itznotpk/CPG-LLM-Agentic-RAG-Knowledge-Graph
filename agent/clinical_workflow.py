"""
Clinical workflow orchestrator.
Calls pipeline stages 2–5 sequentially and returns a TreatmentPlan.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field

from .models import PatientCase, TreatmentPlan
from .clinical_stages import DDxResult, stage_2_ddx, stage_3_route, stage_4_retrieve, stage_5_synthesize  # noqa: F401 (stage_2_ddx imported for test patching)
from .routing import CPGDocRef, route_icd_to_cpgs

logger = logging.getLogger(__name__)


async def route_comorbidities(
    comorbidities: list[str],
    existing_cpgs: list[CPGDocRef],
    top_k: int = 2,
) -> list[CPGDocRef]:
    """Map free-text comorbidity names to additional CPG documents.

    For each comorbidity, run a DDx lookup (top_k=3) to obtain an ICD-11 code,
    then route that code to CPGs. Skips matches below similarity 0.55 to prevent
    semantic-fallback drift (e.g. DM/CKD routing to Breast Cancer CPG).
    Deduplicated against existing_cpgs.
    """
    from ddx.search_ddx import search_ddx
    additional: list[CPGDocRef] = []
    existing_names = {c.cpg_name for c in existing_cpgs}
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
                if ref.cpg_name not in existing_names:
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
        cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3)
        extra_cpgs = await route_comorbidities(case.comorbidities, cpgs)
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

    # Stage 5 — Synthesize (unrecoverable if it fails)
    treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence)

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info("Workflow complete in %.0f ms. ICD primary: %s",
                elapsed_ms, treatment_plan.icd_primary)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
    )


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
        cpgs = await stage_3_route(ddx, top_k_codes=2, top_k_cpgs=3, emit=emit)
        extra_cpgs = await route_comorbidities(case.comorbidities, cpgs)
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

    # Stage 5 — Synthesize (unrecoverable if it fails)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan…"
    })
    treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms total",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, 'confidence') and treatment_plan.confidence else None,
    })
    logger.info("Workflow complete in %.0f ms", elapsed_ms)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
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
        cpgs = await stage_3_route(selected_ddx, top_k_codes=len(selected_ddx), top_k_cpgs=3, emit=emit)
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

    # Stage 5 — Synthesize (unrecoverable)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan for confirmed diagnosis…",
    })
    treatment_plan = await stage_5_synthesize(case, selected_ddx, cpgs, evidence)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, "confidence") and treatment_plan.confidence else None,
    })
    logger.info("Re-synthesis complete in %.0f ms", elapsed_ms)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=selected_ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
    )
