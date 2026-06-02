"""
Shared adapters — convert gold-set rows into the project's domain models,
resolve CPG titles to document UUIDs, etc.
"""

from __future__ import annotations
from typing import Any

from agent.models import PatientCase


def to_patient_case(raw: dict[str, Any]) -> PatientCase:
    """
    Map a gold-set patient_case dict (loose schema for readability) into the
    strict PatientCase model the pipeline expects.

    Gold-set shape (clinical_qa_gold.jsonl):
        {age, sex, symptoms:[..], vitals:{..}, ecg?, echo?, history:[..]}
    PatientCase fields:
        chief_complaint (str, required), history (str), age, sex, comorbidities,
        current_medications, allergies, vitals (dict[str, float])
    """
    symptoms = raw.get("symptoms", [])
    chief_complaint = ", ".join(symptoms) if symptoms else raw.get("chief_complaint", "")

    history_bits: list[str] = []
    if isinstance(raw.get("history"), list):
        history_bits.extend(raw["history"])
    elif isinstance(raw.get("history"), str):
        history_bits.append(raw["history"])
    for k in ("ecg", "echo"):
        if raw.get(k):
            history_bits.append(f"{k.upper()}: {raw[k]}")
    history = ". ".join(history_bits) or None

    # Vitals: strip non-numeric (e.g. "150/95") into sbp/dbp; rest cast to float where possible
    vitals: dict[str, float] = {}
    for k, v in (raw.get("vitals") or {}).items():
        if isinstance(v, (int, float)):
            vitals[k] = float(v)
        elif isinstance(v, str) and "/" in v and k.lower() == "bp":
            try:
                sbp, dbp = v.split("/", 1)
                vitals["sbp"] = float(sbp); vitals["dbp"] = float(dbp)
            except ValueError:
                pass
        else:
            try:
                vitals[k] = float(v)
            except (TypeError, ValueError):
                pass

    return PatientCase(
        chief_complaint=chief_complaint or "unspecified",
        history=history,
        age=raw.get("age"),
        sex=raw.get("sex") if raw.get("sex") in ("M", "F", "other") else None,
        comorbidities=raw.get("comorbidities", []),
        current_medications=raw.get("current_medications", []),
        allergies=raw.get("allergies", []),
        vitals=vitals,
    )


# Maps gold-set document_filter labels → exact cpg_name slugs in the DB.
# Add entries here each time a new CPG is ingested.
_FILTER_TO_CPG_SLUG: dict[str, str] = {
    "Atrial Fibrillation":               "Atrial-Fibrillation(2012)",
    "Cancer Pain":                        "Cancer-Pain(2nd Edition)",
    "Patient Safety Minimal Monitoring":  "Patient-Safety-Minimal-Monitoring",
    "Pre-Anaesthetic Assessment":         "Pre-Anaesthetic-Assessment",
    "Anaesthesia Medication Safety":      "Anaesthesia-Medication-Safety",
    "Anaesthesia Safe Medication Use":    "Anaesthesia-Medication-Safety",
    "STEMI":                              "STEMI(4th Edition)",
    "NSTE-ACS":                           "NSTE-ACS(3rd Edition)",
    "NSTEMI":                             "NSTEMI(2011)",
    "Heart Failure":                      "Heart-Failure(5th Edition)",
    "Hypertension":                       "Hypertension(5th Edition)",
    "Dyslipidaemia":                      "Dyslipidaemia(6th-Edition)",
    "Stable Coronary Artery Disease":     "Stable-Coronary-Artery-Disease(2nd Edition)",
    "Percutaneous Coronary Intervention": "Percutaneous-Coronary-Intervention",
    "Pulmonary Arterial Hypertension":    "Pulmonary-Arterial-Hypertension(2011)",
    "Heart Disease in Pregnancy":         "Heart-Disease-in-Pregnancy(2nd Edition)",
    "Infective Endocarditis":             "Prevention-Diagnosis-Management-of-IE",
    "Ischaemic Stroke":                   "Ischaemic-Stroke(3rd Edition)",
    "Breast Cancer":                      "Breast-Cancer(3rd Edition)",
    "Colorectal Carcinoma":               "Colorectal-Carcinoma(2017)",
    "Nasopharyngeal Carcinoma":           "Nasopharyngeal-Carcinoma",
    "Erectile Dysfunction":               "Erectile-Dysfunction(2024)",
    "Primary Secondary Prevention of CVD": "Primary-Secondary-Prevention-of-CVD(2017)",
    "CVD Prevention in Women":            "CVD-Prevention-Women(2016)",
}


async def resolve_cpg_title_to_doc_ids(cpg_title_substring: str) -> list[str]:
    """Resolve a CPG title fragment (e.g. 'Atrial Fibrillation') to document UUIDs.

    Uses the explicit slug map first for known ingested CPGs; falls back to
    substring match on metadata->>'cpg_name' and title for anything not yet mapped.
    """
    from agent.db_utils import db_pool
    slug = _FILTER_TO_CPG_SLUG.get(cpg_title_substring)
    async with db_pool.acquire() as conn:
        if slug:
            rows = await conn.fetch(
                "SELECT id::text AS id FROM documents WHERE metadata->>'cpg_name' = $1",
                slug,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id::text AS id
                FROM documents
                WHERE metadata->>'cpg_name' ILIKE $1
                   OR title ILIKE $1
                """,
                f"%{cpg_title_substring}%",
            )
    return [r["id"] for r in rows]


def treatment_plan_to_text(plan) -> str:
    """Flatten a TreatmentPlan into a single string for keyword/contains scoring."""
    parts = [plan.summary or ""]
    for r in plan.recommendations:
        parts.append(f"{r.intervention} | {r.cpg_source} | {r.rationale}")
    parts.extend(plan.red_flags or [])
    parts.extend(plan.follow_up or [])
    return "\n".join(p for p in parts if p)


def treatment_plan_claims(plan) -> list[str]:
    """Atomic claims for faithfulness judging."""
    claims = []
    if plan.summary:
        claims.append(plan.summary)
    for r in plan.recommendations:
        claims.append(r.intervention)
        if r.rationale:
            claims.append(r.rationale)
    for m in plan.monitoring or []:
        claims.append(f"Monitor {m.parameter} ({m.schedule})")
    return [c for c in claims if c]
