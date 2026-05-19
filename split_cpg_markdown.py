"""
Split a raw monolithic CPG markdown into per-section files for ingestion.

Step 2 of the CPG pipeline (step 1 = convert_pdf.py). Ingestion
(ingestion/ingest.py) expects, per CPG, a folder of files named
`section-<N>-<slug>-<cpg-slug>.md` where:
  - line 1 is `# Section <N>: <Title>`
  - an optional `<!-- METADATA ... -->` block follows (clinical annotation)
  - `section_number` is parsed from the filename (ingest.py:810)
  - `cpg_name` is the parent folder name (ingest.py:806)

WHY ANCHORS, NOT HEADING-REGEX:
Docling does not preserve top-level CPG section headings reliably — numbered
`##` headings collide with in-body numbered lists (e.g. a treatment-option
list "## 1. Observation", "## 3. Surgery" inside the Nodules section). So a
generic "split on `^## N.`" rule mis-segments. Instead each CPG declares an
ordered list of SECTION anchors: a substring/regex that uniquely matches the
line where that section's content begins in the monolith. Building that list
is the irreducible clinical-judgement step; the splitting itself is mechanical
and shared. Add a new CPG by adding a CONFIGS entry.

Usage:
    python split_cpg_markdown.py --cpg thyroid-2019
    python split_cpg_markdown.py --cpg thyroid-2019 --dry-run   # preview only
    python split_cpg_markdown.py --list                          # list configs
"""
import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Section:
    """One output section."""
    number: int
    title: str          # human title -> "# Section N: <title>"
    slug: str            # filename slug, e.g. "hyperthyroidism"
    anchor: str          # regex matched against monolith lines (first hit wins)
    metadata: str = ""   # body of the <!-- METADATA --> block (no comment tags)


@dataclass
class CPGConfig:
    """Split configuration for one CPG."""
    key: str
    source: str          # path to raw_monolithic .md (relative to repo root)
    out_dir: str         # output folder (relative to repo root)
    cpg_slug: str         # trailing slug appended to every filename
    sections: list[Section] = field(default_factory=list)


# Metadata blocks below are clinical-use annotations consumed by ingest.py.
# Fields mirror the established Dyslipidaemia/Breast-Cancer convention:
#   category      : free-text clinical categories (comma list -> array in DB)
#   use_case      : when a clinician would consult this section
#   patient_input : what patient data feeds this section's decisions
#   output        : what the section yields (dx criteria, targets, drugs...)
# These are drafted from the section content and SHOULD be clinician-reviewed.

THYROID_2019 = CPGConfig(
    key="thyroid-2019",
    source="markdown/raw_monolithic/CPG Management of Thyroid Disorders (MEMS) 2019.md",
    out_dir="markdown/Thyroid-Disorders(2019)",
    cpg_slug="thyroid-disorders",
    sections=[
        Section(
            1, "Thyroid Disorders: The Disease", "introduction",
            r"^## 1\. THYROID DISORDERS: THE DISEASE",
            "category: Introduction, Epidemiology\n"
            "use_case: Disease burden and epidemiology of thyroid disorders in Malaysia\n"
            "patient_input: population_data, NHMS_survey\n"
            "output: disease_prevalence, iodine_status, thyroid_disorder_definition",
        ),
        Section(
            2, "Hyperthyroidism", "hyperthyroidism",
            r"^## 2\.1 OVERT HYPERTHYROIDISM",
            "category: Hyperthyroidism, Thyrotoxicosis, Graves Disease\n"
            "use_case: Diagnosis and treatment of overt and subclinical hyperthyroidism, including Graves' disease, toxic multinodular goitre and toxic adenoma\n"
            "patient_input: TSH, free_T4, free_T3, TRAb, symptoms, thyroid_scan\n"
            "output: hyperthyroidism_diagnosis, aetiology, antithyroid_drug_regimen, radioiodine_indication, monitoring_plan",
        ),
        Section(
            3, "Hypothyroidism", "hypothyroidism",
            r"^## 3\.1 OVERT HYPOTHYROIDISM",
            "category: Hypothyroidism, Levothyroxine Replacement\n"
            "use_case: Diagnosis, levothyroxine replacement and monitoring of overt and subclinical hypothyroidism\n"
            "patient_input: TSH, free_T4, symptoms, body_weight, age, pregnancy_status\n"
            "output: hypothyroidism_diagnosis, levothyroxine_dose, TSH_target, monitoring_interval, referral_criteria",
        ),
        Section(
            4, "Thyroid Nodules / Goitre", "thyroid-nodules-goitre",
            r"^## 4\.1 HOW COMMON ARE THYROID NODULES",
            "category: Thyroid Nodule, Goitre, Thyroid Cancer Workup\n"
            "use_case: Clinical, ultrasound, FNAB and laboratory evaluation and management of thyroid nodules and goitre\n"
            "patient_input: neck_examination, thyroid_ultrasound, FNAB_cytology, TSH, calcitonin\n"
            "output: nodule_risk_stratification, FNAB_indication, Bethesda_category, management_pathway",
        ),
        Section(
            5, "Thyroid Emergencies & Perioperative Management",
            "emergencies-perioperative",
            r"^## 5\. THYROID EMERGENCIES",
            "category: Thyroid Storm, Myxoedema Coma, Perioperative Management, Emergency\n"
            "use_case: Recognition and acute management of thyroid storm and myxoedema coma; pre-/perioperative management of hyper- and hypothyroidism\n"
            "patient_input: vital_signs, Burch-Wartofsky_score, conscious_level, free_T4, TSH, surgical_status\n"
            "output: thyroid_storm_diagnosis, emergency_treatment, perioperative_optimisation",
        ),
        Section(
            6, "Thyroiditis – Subacute & Acute", "thyroiditis",
            r"^## 6\. THYROIDITIS",
            "category: Thyroiditis, Subacute Thyroiditis, Acute Suppurative Thyroiditis\n"
            "use_case: Diagnosis and management of subacute (de Quervain's) and acute/suppurative thyroiditis\n"
            "patient_input: neck_pain, ESR, CRP, TSH, free_T4, radioiodine_uptake, ultrasound\n"
            "output: thyroiditis_diagnosis, NSAID_steroid_regimen, antibiotic_drainage_plan",
        ),
        Section(
            7, "Special Situations (Pregnancy, Children, Elderly)",
            "special-situations",
            r"^## 7\.1 HYPOTHYROIDISM AND PREGNANCY",
            "category: Pregnancy, Postpartum Thyroiditis, Paediatric, Elderly\n"
            "use_case: Management of hypo-/hyperthyroidism in pregnancy, postpartum thyroiditis, thyroid disorders in children/adolescents and the elderly\n"
            "patient_input: trimester, TSH, free_T4, TRAb, age, pregnancy_status, postpartum_status\n"
            "output: trimester_specific_TSH_target, antithyroid_drug_choice_in_pregnancy, paediatric_dosing, elderly_treatment_threshold",
        ),
        Section(
            8, "Drug-Induced Thyroid Disorders", "drug-induced",
            r"^## 8\. DRUG-INDUCED THYROID DISORDERS",
            "category: Drug-Induced Thyroid Disease, Amiodarone, Lithium\n"
            "use_case: Recognition and management of amiodarone-induced thyroid disease and other drug-induced thyroid dysfunction\n"
            "patient_input: drug_history, amiodarone_exposure, TSH, free_T4, free_T3, thyroid_ultrasound\n"
            "output: AIT_AIH_diagnosis, drug_specific_management, monitoring_schedule",
        ),
        Section(
            9, "Graves' Ophthalmopathy", "graves-ophthalmopathy",
            r"^## 9\.1 WHAT IS THE INCIDENCE OF GRAVES",
            "category: Graves Ophthalmopathy, Thyroid Eye Disease\n"
            "use_case: Definition, activity/severity assessment, referral and treatment of Graves' ophthalmopathy\n"
            "patient_input: eye_symptoms, NOSPECS, EUGOGO_severity, clinical_activity_score, smoking_status\n"
            "output: GO_severity_grade, ophthalmology_referral_criteria, treatment_plan",
        ),
        Section(
            10, "Implementing the Guidelines", "implementation",
            r"^## 10\. IMPLEMENTING THE GUIDELINES",
            "category: Implementation, Quality Indicators\n"
            "use_case: Facilitating/limiting factors and resource implications for guideline implementation\n"
            "patient_input: none\n"
            "output: implementation_barriers, resource_implications",
        ),
        Section(
            11, "References", "references",
            r"^## REFERENCES",
            "category: References\n"
            "use_case: Source citations for the guideline recommendations\n"
            "patient_input: none\n"
            "output: bibliographic_references",
        ),
        Section(
            12, "Appendices", "appendices",
            r"^## Appendix 1",
            "category: Appendix, Clinical Questions, Abbreviations\n"
            "use_case: Clinical questions, update addendum and list of abbreviations\n"
            "patient_input: none\n"
            "output: clinical_questions, abbreviations, update_addendum",
        ),
    ],
)

CONFIGS: dict[str, CPGConfig] = {THYROID_2019.key: THYROID_2019}


# Docling emits typographic whitespace (EN SPACE U+2002, NBSP U+00A0, etc.)
# inside headings, so an ASCII-space anchor like "1. THYROID" never matches.
# Collapse all Unicode separators to a single ASCII space before matching.
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s).strip()


def find_anchor_line(lines: list[str], pattern: str, start: int) -> int | None:
    """Return index of first line at/after `start` whose normalized form
    matches `pattern` (anchors are written assuming single ASCII spaces)."""
    rx = re.compile(pattern)
    for i in range(start, len(lines)):
        if rx.search(_norm(lines[i])):
            return i
    return None


def split_cpg(cfg: CPGConfig, repo_root: Path, dry_run: bool) -> int:
    src = repo_root / cfg.source
    if not src.is_file():
        logger.error("Source not found: %s", src)
        return 1

    lines = src.read_text(encoding="utf-8").splitlines()
    n = len(lines)

    # Resolve every anchor to a line index, scanning forward so an earlier
    # section's anchor can never match text that belongs to a later one.
    bounds: list[tuple[Section, int]] = []
    cursor = 0
    for sec in cfg.sections:
        idx = find_anchor_line(lines, sec.anchor, cursor)
        if idx is None:
            logger.error(
                "Section %d (%s): anchor /%s/ not found after line %d. "
                "Check the monolith — docling output may have changed.",
                sec.number, sec.title, sec.anchor, cursor,
            )
            return 1
        bounds.append((sec, idx))
        cursor = idx + 1

    out_dir = repo_root / cfg.out_dir
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # A surviving next-section main heading (e.g. "## 3. HYPOTHYROIDISM")
    # can sit just before the next section's anchor (a subsection like
    # "## 3.1 ..."). Trim that orphan tail plus trailing blanks/image stubs
    # so it does not bleed into the previous section's file.
    orphan = re.compile(r"^#{1,3}\s+\d+\.\s+[A-Z][A-Z '/&,–-]+$")

    for i, (sec, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else n
        seg = lines[start:end]
        while seg:
            tail = seg[-1].strip()
            if not tail or tail == "<!-- image -->":
                seg.pop()
                continue
            if orphan.match(_norm(seg[-1])):
                seg.pop()  # remove the single orphan heading, then stop
            break
        body = "\n".join(seg).strip()

        header = f"# Section {sec.number}: {sec.title}\n"
        meta = f"<!-- METADATA\n{sec.metadata}\n-->\n" if sec.metadata else ""
        content = f"{header}{meta}\n{body}\n"

        fname = f"section-{sec.number}-{sec.slug}-{cfg.cpg_slug}.md"
        dest = out_dir / fname

        if dry_run:
            logger.info(
                "[dry-run] %s  <- lines %d-%d (%d lines)",
                fname, start + 1, end, end - start,
            )
        else:
            dest.write_text(content, encoding="utf-8")
            logger.info("Wrote %s (%d lines)", dest, end - start)

    logger.info(
        "%s %d sections for '%s'",
        "Would write" if dry_run else "Done:", len(bounds), cfg.key,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Split raw CPG markdown into sections")
    p.add_argument("--cpg", help="CPG config key (see --list)")
    p.add_argument("--list", action="store_true", help="List available configs")
    p.add_argument("--dry-run", action="store_true",
                   help="Show planned splits without writing files")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent

    if args.list or not args.cpg:
        print("Available CPG configs:")
        for k, c in CONFIGS.items():
            print(f"  {k:16s} -> {c.out_dir} ({len(c.sections)} sections)")
        return 0

    cfg = CONFIGS.get(args.cpg)
    if cfg is None:
        logger.error("Unknown --cpg '%s'. Use --list.", args.cpg)
        return 1

    return split_cpg(cfg, repo_root, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
