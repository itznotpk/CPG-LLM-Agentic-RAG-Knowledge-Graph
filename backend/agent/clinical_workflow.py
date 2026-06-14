"""
Clinical workflow orchestrator.
Calls pipeline stages 2–5 sequentially and returns a TreatmentPlan.
"""
from __future__ import annotations
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from .models import PatientCase, TreatmentPlan, SafetyReport, StagedComorbidity, ChunkResult, StageError
from .clinical_stages import (  # noqa: F401 (stage_2_ddx imported for test patching)
    DDxResult,
    STAGE3_HEADLESS_GAP,
    _auto_select_codes,
    _build_symptom_text,
    stage_2_ddx,
    stage_3_route,
    stage_4_retrieve,
    stage_5_synthesize,
)
from .graph_clinical import clinical_graph_lookup, extract_candidate_drugs_from_chunks, build_patient_params
from .graph_navigator import get_graph_constraints
from .routing import CPGDocRef, route_icd_to_cpgs

logger = logging.getLogger(__name__)

# High-trust routes for COMORBIDITY mapping only. A comorbidity is a bare term
# routed without an LLM rerank safety net, so we accept tight structural matches
# (≤1 hop) plus the calibrated semantic_scope (SEMANTIC_SCOPE_THRESHOLD floor, currently 0.32 — gives clinically sound
# cross-maps like IHD→Stable-CAD), but DROP the broad multi-hop structural
# fallbacks (ancestor_d1_sibling, ancestor_d1_sibling_child, ancestor_d2) that
# otherwise drift — e.g. "Depression"/"Osteoarthritis" symptom codes reaching
# Cancer-Pain via ancestor_d1_sibling_child. Primary DDx routing keeps all methods.
_COMORBIDITY_TRUSTED_ROUTES = {"exact", "sibling", "ancestor_d1", "semantic_scope"}


async def route_comorbidities(
    comorbidities: list[str],
    existing_cpgs: list[CPGDocRef],
    top_k: int = 4,
    patient_sex: str | None = None,
    emit=None,
    staged_comorbidities: list[StagedComorbidity] | None = None,
    clinical_context: str | None = None,
) -> list[CPGDocRef]:
    """Map free-text and structured comorbidities to additional CPG documents.

    If a comorbidity has a confirmed ICD-11 code from staged_comorbidities,
    we bypass search_ddx entirely (short-circuit). Free-text comorbidities
    fall back to vector similarity search (search_ddx) with a 0.55 threshold.
    Deduplicated against existing_cpgs. Sex-incompatible CPGs are dropped.
    Pregnancy CPGs are also dropped when neither clinical_context nor the
    comorbidity list contains pregnancy/obstetric keywords — mirrors the
    filter applied in stage_3_route so the two paths can't disagree.
    """
    from ddx.search_ddx import search_ddx
    from .clinical_stages import sex_incompatible_reason, pregnancy_context_missing_reason
    additional: list[CPGDocRef] = []
    existing_names = {c.cpg_name for c in existing_cpgs}
    sex_excluded: set[str] = set()
    # Combined pregnancy-context text: stage_3 only sees the symptom text,
    # but pregnancy may be named in the structured comorbidity list itself
    # (e.g. "Pregnancy 30 weeks"). Merge both sources so a CPG is only blocked
    # when the patient is genuinely non-obstetric.
    _preg_context_text = " ".join(
        [clinical_context or ""]
        + [c for c in (comorbidities or []) if c]
        + [(sc.label or "") for sc in (staged_comorbidities or []) if sc and sc.label]
    )

    # Merge staged and legacy comorbidities, deduplicating by normalized label name
    items_to_process: list[tuple[str, str | None]] = []
    seen_labels: set[str] = set()

    if staged_comorbidities:
        for sc in staged_comorbidities:
            if sc.label and sc.label.strip():
                lbl_normalized = sc.label.strip().lower()
                if lbl_normalized not in seen_labels:
                    seen_labels.add(lbl_normalized)
                    items_to_process.append((sc.label.strip(), sc.icd_code))

    for c in comorbidities:
        if c and c.strip():
            lbl_normalized = c.strip().lower()
            if lbl_normalized not in seen_labels:
                seen_labels.add(lbl_normalized)
                items_to_process.append((c.strip(), None))

    for condition, icd_code in items_to_process[:4]:           # cap at 4 to limit latency
        try:
            if icd_code and icd_code.strip():
                # SHORT-CIRCUIT: Direct confirmed code routing
                code_to_route = icd_code.strip()
                logger.info(
                    "Comorbidity %r has confirmed ICD code %s — skipping search_ddx",
                    condition, code_to_route,
                )
            else:
                # Legacy free-text path: run search_ddx
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
                code_to_route = top.get("code")

            refs = await route_icd_to_cpgs(code_to_route, top_k=top_k)
            logger.info(
                "Comorbidity %r → ICD %s → CPGs: %s (match_types=%s)",
                condition, code_to_route,
                [r.cpg_name for r in refs],
                [r.match_type for r in refs],
            )

            for ref in refs:
                if ref.cpg_name in existing_names:
                    continue
                # Comorbidities are secondary context with no LLM rerank to catch a
                # bad map, so only trust HIGH-confidence structural routes. The broad
                # fallbacks (ancestor_d1_sibling[_child], ancestor_d2, procedure_scope,
                # semantic_scope) cast too wide for a bare comorbidity name and cause
                # drift — e.g. "Depression"/"Osteoarthritis" reaching Cancer-Pain via
                # ancestor_d1_sibling_child. Primary DDx routing keeps all methods.
                if ref.match_type not in _COMORBIDITY_TRUSTED_ROUTES:
                    logger.info(
                        "Comorbidity %r → %s skipped: low-trust route_method=%s",
                        condition, ref.cpg_name, ref.match_type,
                    )
                    continue
                reason = sex_incompatible_reason(ref.cpg_name, patient_sex)
                if reason is None:
                    reason = pregnancy_context_missing_reason(ref.cpg_name, _preg_context_text)
                if reason is not None:
                    if ref.cpg_name not in sex_excluded:
                        sex_excluded.add(ref.cpg_name)
                        logger.info(
                            "Comorbidity sex/preg-filter excluded %s (via %r): %s",
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


def _nav_flag_to_dict(f) -> dict:
    """Serialise a graph-navigator ClinicalFlag (PREFER) for transport.
    Trims fields the clinician UI needs; drops bulky chunk_ids list."""
    return {
        "drug": f.subject,
        "condition": f.object,
        "relation": f.relation,                      # FIRST_LINE_FOR / SECOND_LINE_FOR / RECOMMENDED_FOR
        "evidence": (f.evidence or "")[:240],
        "source_document": f.source_document,
        "cpg_chunk_id": f.cpg_chunk_id,
    }


def _build_ddx_suggestion(ddx: list[DDxResult]) -> dict:
    """Build the `ddx_suggestion` SSE payload — top-5 DDx with the headless
    default Major/Minor tagging so the UI can show a "system suggests" hint."""
    selected, major = _auto_select_codes(ddx)
    suggested = {code: ("major" if code == major else "minor") for code in selected}
    return {
        "candidates": [
            {
                "rank": i + 1,
                "code": d.code,
                "title": d.title,
                "probability": float(d.similarity or 0.0),
                "reasoning": list(d.reasoning or []),
                "suggested_tier": suggested.get(d.code),
            }
            for i, d in enumerate(ddx[:5])
        ],
        "headless_default_major": major,
        "headless_default_minors": [c for c in selected if c != major],
        "headless_gap_threshold": STAGE3_HEADLESS_GAP,
    }


@contextmanager
def _time_stage(name: str, timings: dict[str, float]):
    start = time.monotonic()
    try:
        yield
    finally:
        timings[name] = (time.monotonic() - start) * 1000


def _log_stage_breakdown(timings: dict[str, float], total_ms: float) -> None:
    ordered = sorted(timings.items(), key=lambda kv: kv[1], reverse=True)
    parts = [f"{name}={ms:.0f}ms ({ms / total_ms * 100:.0f}%)" for name, ms in ordered] if total_ms else []
    logger.info("Stage timing breakdown (total %.0f ms): %s", total_ms, " | ".join(parts))


@dataclass
class WorkflowResult:
    treatment_plan: TreatmentPlan
    ddx: list[DDxResult]
    cpgs: list[CPGDocRef]
    elapsed_ms: float
    stage_errors: list[StageError] = field(default_factory=list)
    safety_report: SafetyReport | None = None
    graph_navigator_rules: list[dict] = field(default_factory=list)
    stage_timings: dict[str, float] = field(default_factory=dict)
    evidence: list[ChunkResult] = field(default_factory=list)


def _derive_bmi(case: PatientCase) -> None:
    """Derive BMI from weight (kg) + height (cm) when missing, in-place on vitals."""
    v = case.vitals or {}
    if "bmi" in v or not v.get("weight") or not v.get("height"):
        return
    try:
        w = float(v["weight"])
        h_m = float(v["height"]) / 100
        if h_m > 0:
            v["bmi"] = round(w / (h_m * h_m), 1)
            case.vitals = v
    except (TypeError, ValueError):
        pass


_EMPTY_EVIDENCE_QUESTION = (
    "No CPG evidence was retrieved for this case — recommendations below are not "
    "grounded in guideline text and must be verified manually."
)


def _degraded_no_evidence_plan(ddx: list[DDxResult], reason: str) -> TreatmentPlan:
    """A safe, explicitly-degraded stand-in plan when retrieval failed outright.

    We refuse to spend a synthesis call (and present a confident-looking plan) on
    absent evidence; the clinician gets a clear 'pipeline degraded' signal instead.
    """
    return TreatmentPlan(
        icd_primary=(ddx[0].code if ddx else "unknown"),
        summary=f"Plan not generated — {reason}",
        recommendations=[],
        confidence=0.0,
        unresolved_questions=[reason],
    )


def _flag_empty_evidence(plan: TreatmentPlan) -> None:
    """Stamp a healthy-pipeline-but-no-chunks plan as low-confidence + unresolved.

    Stage 4 returned zero chunks without erroring, so synthesis ran on no grounding.
    Cap confidence and surface a question so the plan can never read as confident
    from empty evidence (SIL-02)."""
    if plan.confidence is None or plan.confidence > 0.25:
        plan.confidence = 0.25
    if _EMPTY_EVIDENCE_QUESTION not in (plan.unresolved_questions or []):
        plan.unresolved_questions = list(plan.unresolved_questions or []) + [_EMPTY_EVIDENCE_QUESTION]


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
    errors: list[StageError] = []
    timings: dict[str, float] = {}

    _derive_bmi(case)

    # Stage 2 — DDx
    try:
        with _time_stage("stage_2_ddx", timings):
            ddx = await stage_2_ddx(case, top_k=5)
        logger.info("Stage 2 DDx: %d candidates. Top: %s",
                    len(ddx), ddx[0].code if ddx else "none")
    except Exception as e:
        logger.error("Stage 2 DDx failed: %s", e)
        errors.append(StageError.from_exc("Stage 2 DDx", e, recoverable=True))
        ddx = []

    # Stage 3 — Route (headless: auto-select Major / Minor from rank-1/2 gap)
    try:
        auto_selected, auto_major = _auto_select_codes(ddx)
        with _time_stage("stage_3_route", timings):
            cpgs = await stage_3_route(
                ddx,
                selected_codes=auto_selected or None,
                major_code=auto_major,
                clinical_context=_build_symptom_text(case),
                patient_sex=case.sex,
            )
        with _time_stage("stage_3_route_comorbidities", timings):
            extra_cpgs = await route_comorbidities(case.comorbidities, cpgs, patient_sex=case.sex, staged_comorbidities=case.staged_comorbidities, clinical_context=_build_symptom_text(case))
        if extra_cpgs:
            cpgs = cpgs + extra_cpgs
        logger.info("Stage 3 Routing: %d CPGs matched: %s",
                    len(cpgs), [c.cpg_name for c in cpgs])
    except Exception as e:
        logger.error("Stage 3 Routing failed: %s", e)
        errors.append(StageError.from_exc("Stage 3 Routing", e, recoverable=True))
        cpgs = []

    # Stage 4 — Retrieve
    stage4_failed = False
    try:
        with _time_stage("stage_4_retrieve", timings):
            evidence = await stage_4_retrieve(case, ddx, cpgs)
        logger.info("Stage 4 Retrieval: %d evidence chunks", len(evidence))
    except Exception as e:
        logger.error("Stage 4 Retrieval failed: %s", e)
        errors.append(StageError.from_exc("Stage 4 Retrieval", e, recoverable=True))
        evidence = []
        stage4_failed = True

    # KG lookup — runs between Stage 4 and Stage 5, fail-open
    try:
        with _time_stage("kg_lookup", timings):
            _chunk_ids = [c.chunk_id for c in evidence]
            _candidate_drugs = await extract_candidate_drugs_from_chunks(_chunk_ids)
            kg_flags = await clinical_graph_lookup(
                patient_meds=case.current_medications,
                candidate_drugs=_candidate_drugs,
                comorbidities=case.comorbidities,
                allergies=case.allergies,
                patient_params=build_patient_params(case),
                patient_age=case.age,
            )
        logger.info("KG lookup: %d flags", len(kg_flags))
    except Exception as e:
        logger.warning("KG lookup failed (non-fatal): %s", e)
        kg_flags = []

    # Graph Navigator (Agent 2 v1) — preferred-agent rules, fail-open
    nav_flags = []
    try:
        with _time_stage("graph_navigator", timings):
            nav_flags = await get_graph_constraints(case, ddx, cpgs=cpgs)
        logger.info("Graph navigator: %d preferred-agent rules", len(nav_flags))
        kg_flags = list(kg_flags) + list(nav_flags)
    except Exception as e:
        logger.warning("Graph navigator failed (non-fatal): %s", e)

    # Stage 5 — Synthesize (unrecoverable if it fails)
    if stage4_failed:
        # Retrieval errored out (infra failure): refuse to synthesize a plan on
        # absent evidence — return an explicitly-degraded plan instead of a
        # confident-looking one built from nothing (INF-02).
        logger.warning("Skipping Stage 5: retrieval failed, no evidence to ground synthesis")
        treatment_plan = _degraded_no_evidence_plan(
            ddx, "Stage 4 retrieval failed; re-run when the retrieval service recovers."
        )
    else:
        with _time_stage("stage_5_synthesize", timings):
            treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence, flags=kg_flags)
        if not evidence:
            _flag_empty_evidence(treatment_plan)

    # Stage 6 — Safety review (fail-open, never raises)
    from .safety_critic import run_safety_critic
    with _time_stage("stage_6_safety", timings):
        safety_report = await run_safety_critic(case, treatment_plan)

    elapsed_ms = (time.monotonic() - t0) * 1000
    _log_stage_breakdown(timings, elapsed_ms)
    logger.info("Workflow complete in %.0f ms. ICD primary: %s",
                elapsed_ms, treatment_plan.icd_primary)

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
        safety_report=safety_report,
        graph_navigator_rules=[_nav_flag_to_dict(f) for f in nav_flags],
        stage_timings=timings,
        evidence=evidence,
    )


async def run_ddx_only_streaming(
    case: PatientCase,
    emit,                           # async callable: emit(event_type: str, data: dict) -> None
    exclude_codes: list[str] | None = None,
    regen_feedback: str | None = None,
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

    Regeneration (Step-2 "Regenerate differentials"): `exclude_codes` drops
    already-shown ICD codes from the candidate pool so a re-run surfaces genuinely
    different candidates even under the deterministic pipeline; `regen_feedback`
    is optional free-text clinician guidance that steers retrieval + the rerank.
    """
    await emit("stage_update", {
        "stage": 2, "name": "DDx Analysis",
        "status": "running", "detail": "Analyzing symptoms and history…"
    })
    # Surface regeneration intent in the trace before the work starts.
    if exclude_codes:
        await emit("sub_step", {
            "stage": 2,
            "detail": f"Regenerating — excluding {len(exclude_codes)} previously-shown diagnoses",
            "badge": "regenerate",
        })
    if regen_feedback:
        await emit("sub_step", {
            "stage": 2,
            "detail": f"Clinician guidance: \"{regen_feedback}\"",
            "badge": "regenerate",
        })
    try:
        ddx = await stage_2_ddx(
            case, top_k=5, emit=emit,
            exclude_codes=exclude_codes, regen_feedback=regen_feedback,
        )
        top = ddx[0].code if ddx else "none"
        # Pool-exhaustion after exclusion is a legitimate (non-error) terminal state:
        # there are simply no further distinct candidates to suggest. Tell the
        # clinician plainly so the UI keeps the prior list instead of going blank.
        if not ddx and exclude_codes:
            detail = "No further distinct diagnoses remain"
        else:
            detail = f"{len(ddx)} candidates · top: {top}"
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "complete",
            "detail": detail,
            "data": [d.model_dump() for d in ddx],
        })
        logger.info("DDx-only Stage 2: %d candidates. Top: %s", len(ddx), top)
    except Exception as e:
        logger.error("DDx-only Stage 2 failed: %s", e)
        await emit("stage_update", {
            "stage": 2, "name": "DDx Analysis", "status": "error", "detail": str(e),
        })
        ddx = []

    # Surface the Major/Minor tier-selection scaffolding alongside the raw DDx.
    # `ddx_suggestion` is the structured payload the new Doctor UI listens for;
    # `ddx_ready` is kept for back-compat with the legacy override panel.
    if ddx:
        await emit("ddx_suggestion", _build_ddx_suggestion(ddx))
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
    errors: list[StageError] = []

    _derive_bmi(case)

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
        errors.append(StageError.from_exc("Stage 2 DDx", e, recoverable=True))
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
        auto_selected, auto_major = _auto_select_codes(ddx)
        cpgs = await stage_3_route(
            ddx,
            selected_codes=auto_selected or None,
            major_code=auto_major,
            emit=emit,
            clinical_context=_build_symptom_text(case),
            patient_sex=case.sex,
        )
        extra_cpgs = await route_comorbidities(case.comorbidities, cpgs, patient_sex=case.sex, emit=emit, staged_comorbidities=case.staged_comorbidities, clinical_context=_build_symptom_text(case))
        if extra_cpgs:
            cpgs = cpgs + extra_cpgs
            for c in extra_cpgs:
                await emit("sub_step", {"stage": 3, "detail": c.cpg_name, "badge": "comorbidity"})
        names = [c.cpg_name for c in cpgs]
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "complete",
            "detail": f"{len(cpgs)} CPGs matched",
            "data": names,
        })
        logger.info("Stage 3 Routing: %d CPGs: %s", len(cpgs), names)
    except Exception as e:
        logger.error("Stage 3 Routing failed: %s", e)
        errors.append(StageError.from_exc("Stage 3 Routing", e, recoverable=True))
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "error", "detail": str(e),
        })
        cpgs = []

    # Stage 4 — Retrieve
    await emit("stage_update", {
        "stage": 4, "name": "Evidence Retrieval",
        "status": "running", "detail": "Retrieving relevant guideline chunks…"
    })
    stage4_failed = False
    try:
        evidence = await stage_4_retrieve(case, ddx, cpgs, emit=emit)
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "complete",
            "detail": f"{len(evidence)} evidence chunks retrieved",
        })
        logger.info("Stage 4 Retrieval: %d chunks", len(evidence))
    except Exception as e:
        logger.error("Stage 4 Retrieval failed: %s", e)
        errors.append(StageError.from_exc("Stage 4 Retrieval", e, recoverable=True))
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "error", "detail": str(e),
        })
        evidence = []
        stage4_failed = True

    # KG lookup — runs between Stage 4 and Stage 5, fail-open
    try:
        _chunk_ids = [c.chunk_id for c in evidence]
        _candidate_drugs = await extract_candidate_drugs_from_chunks(_chunk_ids)
        kg_flags = await clinical_graph_lookup(
            patient_meds=case.current_medications,
            candidate_drugs=_candidate_drugs,
            comorbidities=case.comorbidities,
            allergies=case.allergies,
            patient_params=build_patient_params(case),
            patient_age=case.age,
        )
        logger.info("KG lookup: %d flags", len(kg_flags))
    except Exception as e:
        logger.warning("KG lookup failed (non-fatal): %s", e)
        kg_flags = []

    # Graph Navigator (Agent 2 v1) — preferred-agent rules, fail-open
    nav_flags = []
    try:
        nav_flags = await get_graph_constraints(case, ddx, cpgs=cpgs)
        logger.info("Graph navigator: %d preferred-agent rules", len(nav_flags))
        kg_flags = list(kg_flags) + list(nav_flags)
    except Exception as e:
        logger.warning("Graph navigator failed (non-fatal): %s", e)
    if nav_flags:
        try:
            await emit("graph_navigator", {"rules": [_nav_flag_to_dict(f) for f in nav_flags]})
        except Exception:
            pass

    # Stage 5 — Synthesize (unrecoverable if it fails)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan…"
    })
    if stage4_failed:
        # Retrieval outage: refuse to synthesise a confident-looking plan on absent
        # evidence — emit a degraded plan instead (INF-02, mirrored from non-streaming).
        logger.warning("Skipping Stage 5: retrieval failed, no evidence to ground synthesis")
        treatment_plan = _degraded_no_evidence_plan(
            ddx, "Stage 4 retrieval failed; re-run when the retrieval service recovers."
        )
    else:
        treatment_plan = await stage_5_synthesize(case, ddx, cpgs, evidence, flags=kg_flags)
        if not evidence:
            _flag_empty_evidence(treatment_plan)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms total",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, 'confidence') and treatment_plan.confidence else None,
    })
    logger.info("Workflow complete in %.0f ms", elapsed_ms)

    # Stage 6 — Safety review (fail-open, never raises)
    from .safety_critic import run_safety_critic
    await emit("stage_update", {
        "stage": 6, "name": "Safety Review",
        "status": "running", "detail": "Running independent medication safety review...",
    })
    safety_report = await run_safety_critic(case, treatment_plan, emit=emit)
    blocking_flags = [f for f in safety_report.flags if f.severity in ("CRITICAL", "MAJOR")]
    await emit("stage_update", {
        "stage": 6, "name": "Safety Review", "status": "complete",
        "detail": (
            f"{len(blocking_flags)} major safety concern(s) found"
            if blocking_flags else "Safety review complete"
        ),
        "badge": "review required" if blocking_flags else "passed",
    })
    await emit("safety_review", safety_report.model_dump())

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
        safety_report=safety_report,
        graph_navigator_rules=[_nav_flag_to_dict(f) for f in nav_flags],
        evidence=evidence,
    )


async def run_resynthesize_streaming(
    case: PatientCase,
    selected_ddx: list[DDxResult],
    emit,
    major_code: str | None = None,
) -> WorkflowResult:
    """
    Re-run Stages 3–5 with clinician-selected diagnoses.

    Stage 2 (DDx) is intentionally skipped — the clinician's selection overrides the AI.
    Emits a clinician_override event first so the UI can show what changed.
    Same fault-tolerance contract as run_clinical_workflow_streaming for stages 3–4.
    Stage 5 failure propagates (unrecoverable).

    `major_code` is the single primary diagnosis (must be in selected_ddx). When None,
    falls back to selected_ddx[0] for backward compatibility with older callers.
    `selected_ddx` is reordered so the Major code is index 0 — Stage 5 prompt then
    frames `icd_primary` correctly without any prompt edits.
    """
    t0 = time.monotonic()
    errors: list[StageError] = []
    timings: dict[str, float] = {}

    # Resolve Major and reorder selected_ddx so the Major code is index 0 — this
    # makes Stage 5's `icd_primary = ddx[0].code` automatically pick the right one.
    if major_code is None and selected_ddx:
        major_code = selected_ddx[0].code
    if major_code is not None:
        major_idx = next((i for i, d in enumerate(selected_ddx) if d.code == major_code), None)
        if major_idx is None:
            logger.warning(
                "Resynth: major_code %s not found in selected_ddx; defaulting to selected_ddx[0]",
                major_code,
            )
            major_code = selected_ddx[0].code if selected_ddx else None
        elif major_idx != 0:
            selected_ddx = [selected_ddx[major_idx]] + [d for i, d in enumerate(selected_ddx) if i != major_idx]

    selected_codes = [d.code for d in selected_ddx]

    # Signal the override to the UI — must be the first event
    await emit("clinician_override", {
        "codes": [f"{d.code} {d.title}" for d in selected_ddx],
        "major_code": major_code,
    })

    # Stage 3 — Route using clinician codes
    await emit("stage_update", {
        "stage": 3, "name": "CPG Routing",
        "status": "running",
        "detail": (
            f"Routing {len(selected_ddx)} clinician-selected code(s); "
            f"major={major_code}"
        ),
    })
    try:
        with _time_stage("stage_3_route", timings):
            cpgs = await stage_3_route(
                selected_ddx,
                selected_codes=selected_codes or None,
                major_code=major_code,
                emit=emit,
                clinical_context=_build_symptom_text(case),
                patient_sex=case.sex,
            )
        # Comorbidity routing — fan in any staged/free-text comorbidities so
        # CPGs like Obesity-Management(2023) don't drop on the resynth path.
        # Initial /clinical/plan/stream does this; resynth was missing it.
        try:
            with _time_stage("stage_3_route_comorbidities", timings):
                extra_cpgs = await route_comorbidities(
                    case.comorbidities,
                    cpgs,
                    patient_sex=case.sex,
                    emit=emit,
                    staged_comorbidities=case.staged_comorbidities,
                    clinical_context=_build_symptom_text(case),
                )
            if extra_cpgs:
                cpgs = list(cpgs) + list(extra_cpgs)
                logger.info(
                    "Re-synth Stage 3 comorbidity routing added %d CPG(s)",
                    len(extra_cpgs),
                )
        except Exception as e:
            logger.warning("Re-synth comorbidity routing failed (continuing): %s", e)
        names = [c.cpg_name for c in cpgs]
        await emit("stage_update", {
            "stage": 3, "name": "CPG Routing", "status": "complete",
            "detail": f"{len(cpgs)} CPGs matched",
            "data": names,
        })
        logger.info("Re-synth Stage 3 Routing: %d CPGs: %s", len(cpgs), names)
    except Exception as e:
        logger.error("Re-synth Stage 3 failed: %s", e)
        errors.append(StageError.from_exc("Stage 3 Routing", e, recoverable=True))
        await emit("stage_update", {"stage": 3, "name": "CPG Routing", "status": "error", "detail": str(e)})
        cpgs = []

    # Stage 4 — Retrieve
    await emit("stage_update", {
        "stage": 4, "name": "Evidence Retrieval",
        "status": "running", "detail": "Retrieving guideline evidence for selected diagnosis…",
    })
    stage4_failed = False
    try:
        with _time_stage("stage_4_retrieve", timings):
            evidence = await stage_4_retrieve(case, selected_ddx, cpgs, emit=emit)
        await emit("stage_update", {
            "stage": 4, "name": "Evidence Retrieval", "status": "complete",
            "detail": f"{len(evidence)} evidence chunks retrieved",
        })
        logger.info("Re-synth Stage 4 Retrieval: %d chunks", len(evidence))
    except Exception as e:
        logger.error("Re-synth Stage 4 failed: %s", e)
        errors.append(StageError.from_exc("Stage 4 Retrieval", e, recoverable=True))
        await emit("stage_update", {"stage": 4, "name": "Evidence Retrieval", "status": "error", "detail": str(e)})
        evidence = []
        stage4_failed = True

    # KG lookup — runs between Stage 4 and Stage 5, fail-open
    try:
        _chunk_ids = [c.chunk_id for c in evidence]
        _candidate_drugs = await extract_candidate_drugs_from_chunks(_chunk_ids)
        kg_flags = await clinical_graph_lookup(
            patient_meds=case.current_medications,
            candidate_drugs=_candidate_drugs,
            comorbidities=case.comorbidities,
            allergies=case.allergies,
            patient_params=build_patient_params(case),
            patient_age=case.age,
        )
        logger.info("KG lookup: %d flags", len(kg_flags))
    except Exception as e:
        logger.warning("KG lookup failed (non-fatal): %s", e)
        kg_flags = []

    # Graph Navigator (Agent 2 v1) — preferred-agent rules, fail-open
    nav_flags = []
    try:
        nav_flags = await get_graph_constraints(case, selected_ddx, cpgs=cpgs)
        logger.info("Graph navigator: %d preferred-agent rules", len(nav_flags))
        kg_flags = list(kg_flags) + list(nav_flags)
    except Exception as e:
        logger.warning("Graph navigator failed (non-fatal): %s", e)
    if nav_flags:
        try:
            await emit("graph_navigator", {"rules": [_nav_flag_to_dict(f) for f in nav_flags]})
        except Exception:
            pass

    # Stage 5 — Synthesize (unrecoverable)
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis",
        "status": "running", "detail": "Generating evidence-based care plan for confirmed diagnosis…",
    })
    if stage4_failed:
        # Retrieval outage: refuse to synthesise on absent evidence (INF-02, mirrored).
        logger.warning("Re-synth skipping Stage 5: retrieval failed, no evidence to ground synthesis")
        treatment_plan = _degraded_no_evidence_plan(
            selected_ddx, "Stage 4 retrieval failed; re-run when the retrieval service recovers."
        )
    else:
        with _time_stage("stage_5_synthesize", timings):
            treatment_plan = await stage_5_synthesize(case, selected_ddx, cpgs, evidence, flags=kg_flags)
        if not evidence:
            _flag_empty_evidence(treatment_plan)
    elapsed_ms = (time.monotonic() - t0) * 1000
    await emit("stage_update", {
        "stage": 5, "name": "Plan Synthesis", "status": "complete",
        "detail": f"Care plan ready · {elapsed_ms:.0f} ms",
        "badge": f"conf. {treatment_plan.confidence:.2f}" if hasattr(treatment_plan, "confidence") and treatment_plan.confidence else None,
    })
    logger.info("Re-synthesis complete in %.0f ms", elapsed_ms)

    # Stage 6 — Safety review (fail-open, never raises)
    from .safety_critic import run_safety_critic
    await emit("stage_update", {
        "stage": 6, "name": "Safety Review",
        "status": "running", "detail": "Running independent medication safety review...",
    })
    with _time_stage("stage_6_safety", timings):
        safety_report = await run_safety_critic(case, treatment_plan, emit=emit)
    blocking_flags = [f for f in safety_report.flags if f.severity in ("CRITICAL", "MAJOR")]
    await emit("stage_update", {
        "stage": 6, "name": "Safety Review", "status": "complete",
        "detail": (
            f"{len(blocking_flags)} major safety concern(s) found"
            if blocking_flags else "Safety review complete"
        ),
        "badge": "review required" if blocking_flags else "passed",
    })
    await emit("safety_review", safety_report.model_dump())

    return WorkflowResult(
        treatment_plan=treatment_plan,
        ddx=selected_ddx,
        cpgs=cpgs,
        elapsed_ms=elapsed_ms,
        stage_errors=errors,
        safety_report=safety_report,
        graph_navigator_rules=[_nav_flag_to_dict(f) for f in nav_flags],
        stage_timings=timings,
        evidence=evidence,
    )
