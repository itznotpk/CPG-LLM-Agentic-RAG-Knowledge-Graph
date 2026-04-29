"""Apply ED-style METADATA blocks to guideline section markdown files.

Targets:
- Hypertension(5th Edition)
- Stable-Coronary-Artery-Disease(2nd Edition)
- Primary-Secondary-Prevention-of-CVD(2017)

This script inserts or replaces a `<!-- METADATA ... -->` block right after the
first H1 in each file (or at top if no H1 exists), using a per-file mapping that
is consistent with the Erectile Dysfunction metadata style.

It also writes a review report under `reports/` summarizing the assigned fields
for each file.

Usage (PowerShell):
  python tools/apply_section_metadata.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = WORKSPACE_ROOT / "reports"


META_START = "<!-- METADATA"
META_END = "-->"


@dataclass(frozen=True)
class Meta:
    category: str
    use_case: str
    patient_input: str
    output: str


def _first_h1_index(lines: List[str]) -> Optional[int]:
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return i
    return None


def _render_meta(meta: Meta) -> str:
    return "\n".join(
        [
            "<!-- METADATA",
            f"category: {meta.category}",
            f"use_case: {meta.use_case}",
            f"patient_input: {meta.patient_input}",
            f"output: {meta.output}",
            "-->",
        ]
    )


def _strip_legacy_frontmatter(text: str) -> str:
    """Remove a legacy top-of-file HTML comment block if present.

    Some converted guideline markdown files include a leading HTML comment like:

        <!--
        category: "internal medicine"
        use_case: "RAG"
        patient_input: "null"
        output: "..."
        -->

    This is not the Erectile Dysfunction style used in this repo. We strip it so
    each file has a single ED-style `<!-- METADATA ... -->` block.

    Args:
        text: Markdown contents.

    Returns:
        Markdown with the legacy frontmatter removed when detected.
    """

    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    # If it's already the ED metadata block, keep.
    first_line = stripped.splitlines()[0].strip()
    if first_line.startswith("<!-- METADATA"):
        return text

    end = stripped.find(META_END)
    if end == -1:
        return text
    block = stripped[: end + len(META_END)]
    lower = block.lower()
    # Heuristic: looks like the legacy metadata block.
    if "category:" in lower and "use_case:" in lower and "patient_input:" in lower and "output:" in lower:
        remainder = stripped[end + len(META_END) :].lstrip("\r\n ")
        return remainder.rstrip() + "\n"
    return text


def _upsert_metadata(text: str, meta: Meta) -> str:
    """Insert or replace the METADATA block in `text`.

    Args:
        text: Existing markdown.
        meta: Metadata to apply.

    Returns:
        Updated markdown.
    """

    text = _strip_legacy_frontmatter(text)
    new_block = _render_meta(meta)

    if META_START in text:
        start = text.find(META_START)
        end = text.find(META_END, start)
        if end != -1:
            end += len(META_END)
            return (text[:start].rstrip() + "\n\n" + new_block + "\n\n" + text[end:].lstrip()).rstrip() + "\n"

    lines = text.splitlines()
    h1_idx = _first_h1_index(lines)

    if h1_idx is None:
        # No H1: prepend metadata.
        return (new_block + "\n\n" + text.lstrip()).rstrip() + "\n"

    # Insert after H1.
    before = "\n".join(lines[: h1_idx + 1]).rstrip()
    after = "\n".join(lines[h1_idx + 1 :]).lstrip()
    return (before + "\n\n" + new_block + "\n\n" + after).rstrip() + "\n"


def _meta_map_hypertension() -> Dict[str, Meta]:
    return {
        "section-0-key-recommendations.md": Meta(
            category="key_recommendations",
            use_case="quick_reference, care_plan_generation",
            patient_input="blood_pressure, comorbidities, risk_factors",
            output="key_recommendations",
        ),
        "section-1-epidemiology-definition-classification.md": Meta(
            category="background_knowledge",
            use_case="epidemiology, definition_classification",
            patient_input="population_risk_factors",
            output="definitions, classification",
        ),
        "section-2-measurement-blood-pressure.md": Meta(
            category="diagnosis",
            use_case="blood_pressure_measurement, technique_selection",
            patient_input="bp_readings, device_type, measurement_setting",
            output="measurement_protocol",
        ),
        "section-3-diagnosis-initial-assessment.md": Meta(
            category="diagnosis",
            use_case="initial_assessment, diagnostic_workup",
            patient_input="bp_readings, history, exam, labs, comorbidities",
            output="diagnosis, baseline_workup",
        ),
        "section-4-non-pharmacological-management.md": Meta(
            category="treatment",
            use_case="lifestyle_intervention, nonpharmacological_management",
            patient_input="risk_factors, lifestyle, patient_preferences",
            output="nonpharmacological_plan",
        ),
        "section-5-pharmacological-management.md": Meta(
            category="treatment",
            use_case="antihypertensive_selection, treatment_titration",
            patient_input="bp_target, comorbidities, kidney_function, current_meds",
            output="medication_plan",
        ),
        "section-6-severe-hypertension.md": Meta(
            category="treatment",
            use_case="acute_management, hypertensive_crisis",
            patient_input="bp_level, symptoms, end_organ_damage_signs, labs",
            output="acute_management_plan",
        ),
        "section-7-special-groups.md": Meta(
            category="special_populations",
            use_case="population_specific_management",
            patient_input="population_type, comorbidities, pregnancy_status",
            output="tailored_management",
        ),
        "section-8-economic-impact.md": Meta(
            category="implementation",
            use_case="resource_planning, cost_considerations",
            patient_input="care_setting, available_resources",
            output="resource_implications",
        ),
        "section-9-types-of-agents.md": Meta(
            category="treatment_reference",
            use_case="drug_reference, adverse_effects_contraindications",
            patient_input="drug_class, comorbidities, interacting_meds",
            output="drug_comparison",
        ),
        "section-10-resistant-refractory.md": Meta(
            category="treatment",
            use_case="resistant_hypertension_management, secondary_cause_evaluation",
            patient_input="bp_on_therapy, adherence, secondary_causes, labs",
            output="step_up_plan",
        ),
        "section-11-aspirin.md": Meta(
            category="treatment",
            use_case="adjunct_therapy_risk_benefit",
            patient_input="cv_risk, bleeding_risk, comorbidities",
            output="aspirin_guidance",
        ),
        "section-12-device-procedure-therapy.md": Meta(
            category="treatment",
            use_case="device_procedure_selection",
            patient_input="refractory_hypertension, eligibility_criteria",
            output="procedure_options",
        ),
        "section-13-suggested-research.md": Meta(
            category="implementation",
            use_case="research_priorities",
            patient_input="knowledge_gaps",
            output="research_agenda",
        ),
        "appendix.md": Meta(
            category="appendix",
            use_case="supporting_reference",
            patient_input="reference_lookup",
            output="appendix_content",
        ),
        "references.md": Meta(
            category="references",
            use_case="citation_lookup",
            patient_input="citation_query",
            output="bibliography",
        ),
    }


def _meta_map_scad() -> Dict[str, Meta]:
    return {
        "section-0-summary.md": Meta(
            category="key_recommendations",
            use_case="quick_reference, navigation",
            patient_input="symptoms, risk_profile",
            output="summary, table_of_contents",
        ),
        "section-1-introduction.md": Meta(
            category="introduction",
            use_case="scope_and_objectives",
            patient_input="none",
            output="guideline_scope",
        ),
        "section-2-clinical-spectrum.md": Meta(
            category="diagnosis",
            use_case="clinical_presentation, differential_overview",
            patient_input="symptoms, signs, history",
            output="presentation_framework",
        ),
        "section-3-pathophysiology.md": Meta(
            category="background_knowledge",
            use_case="mechanism_understanding",
            patient_input="risk_factors",
            output="pathophysiology_summary",
        ),
        "section-4-natural-history.md": Meta(
            category="background_knowledge",
            use_case="prognosis, risk_overview",
            patient_input="risk_profile",
            output="prognostic_factors",
        ),
        "section-5-diagnosis-basic.md": Meta(
            category="diagnosis",
            use_case="initial_assessment, diagnostic_workup",
            patient_input="symptoms, exam, ecg, labs, risk_factors",
            output="baseline_diagnosis_workup",
        ),
        "section-6-diagnosis-non-invasive.md": Meta(
            category="diagnosis",
            use_case="noninvasive_testing, test_selection",
            patient_input="pretest_probability, functional_capacity, ecg",
            output="investigation_selection",
        ),
        "section-7-risk-stratification.md": Meta(
            category="diagnosis",
            use_case="risk_stratification",
            patient_input="test_results, symptoms, comorbidities",
            output="risk_category",
        ),
        "section-8-management.md": Meta(
            category="treatment",
            use_case="treatment_selection, care_plan_generation",
            patient_input="risk_category, comorbidities, current_meds",
            output="management_plan",
        ),
        "section-9-chronic-refractory-angina.md": Meta(
            category="treatment",
            use_case="advanced_management, refractory_symptom_control",
            patient_input="angina_severity, prior_therapy, comorbidities",
            output="advanced_options",
        ),
        "section-10-special-groups.md": Meta(
            category="special_populations",
            use_case="population_specific_management",
            patient_input="population_type, comorbidities",
            output="tailored_management",
        ),
        "section-11-follow-up.md": Meta(
            category="follow_up",
            use_case="treatment_monitoring, care_continuity",
            patient_input="symptoms, adherence, vitals, labs",
            output="followup_plan",
        ),
        "section-12-pre-operative.md": Meta(
            category="monitoring",
            use_case="perioperative_risk_assessment",
            patient_input="procedure_risk, functional_status, comorbidities",
            output="perioperative_plan",
        ),
        "section-13-monitoring.md": Meta(
            category="implementation",
            use_case="quality_improvement, clinical_audit",
            patient_input="service_metrics, outcomes",
            output="qa_framework",
        ),
        "appendix.md": Meta(
            category="appendix",
            use_case="supporting_reference",
            patient_input="reference_lookup",
            output="appendix_content",
        ),
        "references.md": Meta(
            category="references",
            use_case="citation_lookup",
            patient_input="citation_query",
            output="bibliography",
        ),
    }


def _meta_map_cvd2017() -> Dict[str, Meta]:
    return {
        "section-0-preliminaries.md": Meta(
            category="preliminaries",
            use_case="guideline_context",
            patient_input="none",
            output="guideline_metadata",
        ),
        "section-1-introduction.md": Meta(
            category="introduction",
            use_case="scope_and_objectives",
            patient_input="none",
            output="guideline_scope",
        ),
        "section-2-prevention-of-cvd.md": Meta(
            category="prevention",
            use_case="prevention_principles, risk_reduction",
            patient_input="risk_profile, comorbidities",
            output="prevention_framework",
        ),
        "section-3-estimation-of-global-cvd-risk.md": Meta(
            category="diagnosis",
            use_case="risk_assessment, risk_stratification",
            patient_input="age, sex, bp, lipids, diabetes, smoking",
            output="global_risk_category",
        ),
        "section-4-types-of-cvd.md": Meta(
            category="background_knowledge",
            use_case="condition_overview",
            patient_input="presentation, known_conditions",
            output="cvd_types_reference",
        ),
        "section-5-risk-factors-for-cvd.md": Meta(
            category="background_knowledge",
            use_case="risk_factor_identification",
            patient_input="risk_factors, lifestyle, family_history",
            output="risk_factor_list",
        ),
        "section-6-other-conditions-associated-with-increased-cv-risk.md": Meta(
            category="diagnosis",
            use_case="risk_modifier_assessment",
            patient_input="comorbidities, chronic_conditions",
            output="risk_modifier_guidance",
        ),
        "section-7-other-risk-markers-of-cvd.md": Meta(
            category="diagnosis",
            use_case="advanced_risk_assessment",
            patient_input="biomarkers, imaging, test_results",
            output="risk_refinement_guidance",
        ),
        "section-8-interventions-to-prevent-cvd.md": Meta(
            category="prevention",
            use_case="intervention_selection, care_plan_generation",
            patient_input="risk_category, comorbidities, patient_preferences",
            output="prevention_plan",
        ),
        "section-9-management-of-individual-risk-factors.md": Meta(
            category="treatment",
            use_case="risk_factor_management, prescribing_guidance",
            patient_input="risk_factors, labs, current_meds, comorbidities",
            output="management_plan",
        ),
        "section-10-adherence-to-therapy.md": Meta(
            category="follow_up",
            use_case="adherence_support, care_continuity",
            patient_input="barriers, adherence, side_effects",
            output="adherence_plan",
        ),
        "section-11-community-population-governmental-level.md": Meta(
            category="implementation",
            use_case="population_health_policy, program_design",
            patient_input="population_data, resources",
            output="policy_recommendations",
        ),
        "section-12-traditional-and-complementary-medicine.md": Meta(
            category="treatment_reference",
            use_case="safety_counselling, interaction_screening",
            patient_input="tcim_use, current_meds, comorbidities",
            output="safety_guidance",
        ),
        "section-13-miscellaneous-faqs-and-myths.md": Meta(
            category="background_knowledge",
            use_case="patient_education, myth_busting",
            patient_input="questions, misconceptions",
            output="answers",
        ),
        "references.md": Meta(
            category="references",
            use_case="citation_lookup",
            patient_input="citation_query",
            output="bibliography",
        ),
        "acknowledgments.md": Meta(
            category="appendix",
            use_case="acknowledgement_context",
            patient_input="none",
            output="acknowledgments",
        ),
        "disclosure-statement.md": Meta(
            category="appendix",
            use_case="disclosure_context",
            patient_input="none",
            output="disclosures",
        ),
        "sources-of-funding.md": Meta(
            category="appendix",
            use_case="funding_context",
            patient_input="none",
            output="funding_sources",
        ),
        # Master file inside folder (no H1 in current conversion)
        "8 Primary & Secondary Prevention of CVD 2017.md": Meta(
            category="document",
            use_case="full_document_reference",
            patient_input="query",
            output="document_text",
        ),
    }


def _targets() -> List[Tuple[str, Path, Dict[str, Meta]]]:
    return [
        (
            "Hypertension(5th Edition)",
            WORKSPACE_ROOT / "markdown" / "Hypertension(5th Edition)",
            _meta_map_hypertension(),
        ),
        (
            "Stable-Coronary-Artery-Disease(2nd Edition)",
            WORKSPACE_ROOT / "markdown" / "Stable-Coronary-Artery-Disease(2nd Edition)",
            _meta_map_scad(),
        ),
        (
            "Primary-Secondary-Prevention-of-CVD(2017)",
            WORKSPACE_ROOT / "markdown" / "Primary-Secondary-Prevention-of-CVD(2017)",
            _meta_map_cvd2017(),
        ),
    ]


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"metadata_review_{date.today().isoformat()}.md"

    report_lines: List[str] = []
    report_lines.append(f"# Metadata Review ({date.today().isoformat()})")
    report_lines.append("")
    report_lines.append(
        "This report lists the ED-style METADATA fields applied to each section file: `category`, `use_case`, `patient_input`, `output`."
    )
    report_lines.append("")

    total_updated = 0

    for label, folder, meta_map in _targets():
        if not folder.exists():
            report_lines.append(f"## {label}")
            report_lines.append("")
            report_lines.append("Folder not found.")
            report_lines.append("")
            continue

        report_lines.append(f"## {label}")
        report_lines.append("")

        for md_path in sorted(folder.glob("*.md")):
            meta = meta_map.get(md_path.name)
            if meta is None:
                # Conservative fallback.
                meta = Meta(
                    category="general",
                    use_case="reference",
                    patient_input="context",
                    output="guidance",
                )

            old_text = md_path.read_text(encoding="utf-8", errors="replace")
            new_text = _upsert_metadata(old_text, meta)
            if new_text != old_text:
                md_path.write_text(new_text, encoding="utf-8")
                total_updated += 1

            report_lines.append(f"- {md_path.name}")
            report_lines.append(f"  - category: {meta.category}")
            report_lines.append(f"  - use_case: {meta.use_case}")
            report_lines.append(f"  - patient_input: {meta.patient_input}")
            report_lines.append(f"  - output: {meta.output}")

        report_lines.append("")

    report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    print(f"Updated files: {total_updated}")
    print(f"Wrote report: {report_path}")


if __name__ == "__main__":
    main()
