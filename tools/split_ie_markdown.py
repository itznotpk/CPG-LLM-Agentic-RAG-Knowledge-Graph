"""Split the Infective Endocarditis CPG master markdown into section files.

This script is intentionally dependency-free (stdlib only). It:
- Reads the converted master markdown under `markdown/`.
- Splits into smaller markdown files (one H1 per file) following the repo's
  Erectile Dysfunction formatting style (H1 `SECTION ...` + `<!-- METADATA ... -->`).
- Preserves ALL source text by distributing lines across output files.
- Adds overlap blocks by duplicating referenced tables/figures/appendices so each
  section stands alone.
- Mirrors the results into `documents/` for ingestion.

Usage (PowerShell):
  python tools/split_ie_markdown.py

If you want a clean re-run, just run it again; it overwrites files in the target
folders.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD = WORKSPACE_ROOT / "markdown" / "CPG Prevention, Diagnosis & Management of IE.md"
OUT_MD_DIR = WORKSPACE_ROOT / "markdown" / "Infective-Endocarditis(2017)"
OUT_DOC_DIR = WORKSPACE_ROOT / "documents" / "Infective-Endocarditis(2017)"


H2_NUMERIC_RE = re.compile(r"^##\s+(?P<num>\d+(?:\.\d+)+)\s+(?P<title>.+?)\s*$")
H2_APPENDIX_RE = re.compile(r"^##\s+Appendix\s+(?P<num>\d+):\s*(?P<title>.+?)\s*$", re.IGNORECASE)
H2_APPENDICES_RE = re.compile(r"^##\s+10\.0\s+APPENDICES\s*$", re.IGNORECASE)
H2_GLOBAL_REFS_RE = re.compile(r"^##\s+REFERENCES\s*$")
H2_ACK_RE = re.compile(r"^##\s+ACKNOWLEDGEMENT\s*$", re.IGNORECASE)
H2_DISCLOSURE_RE = re.compile(r"^##\s+DISCLOSURE\s+STATEMENT\s*$", re.IGNORECASE)
H2_FUNDING_RE = re.compile(r"^##\s+SOURCES\s+OF\s+FUNDING\s*$", re.IGNORECASE)

TABLE_TITLE_RE = re.compile(r"^(?:##\s+)?Table\s+(?P<id>\d+(?:\.\d+)*):\s*(?P<title>.+?)\s*$", re.IGNORECASE)
FIGURE_TITLE_RE = re.compile(r"^(?:##\s+)?Figure\s+(?P<id>[0-9]+[a-zA-Z]?):\s*(?P<title>.+?)\s*$", re.IGNORECASE)

TABLE_REF_RE = re.compile(r"\bTable\s+(?P<id>\d+(?:\.\d+)*)\b")
FIGURE_REF_RE = re.compile(r"\bFigure\s+(?P<id>[0-9]+[a-zA-Z]?)\b")
APPENDIX_REF_RE = re.compile(r"\bAppendix\s+(?P<num>\d+)\b")

# Matches sequences like: "Table 4.5 & 4.6", "Table 3.1, 3.2 and 3.3"
TABLE_MULTI_REF_RE = re.compile(
    r"\bTable\s+(?P<seq>\d+(?:\.\d+)*(?:\s*(?:,|&|and)\s*\d+(?:\.\d+)*)+)\b",
    re.IGNORECASE,
)

# Matches sequences like: "Appendices 8 and 9" or "Appendix 8, 9 and 10"
APPENDIX_MULTI_REF_RE = re.compile(
    r"\bAppendix(?:es)?\s+(?P<seq>\d+(?:\s*(?:,|&|and)\s*\d+)*)\b",
    re.IGNORECASE,
)

# Some converted pages represent "Appendix 7" as a markdown table header row rather
# than a normal H2 appendix heading.
APPENDIX_TABLE_HEADING_RE = re.compile(
    r"^\|\s*Appendix\s+(?P<num>\d+):\s*(?P<title>.+?)\s*\|\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Segment:
    kind: str  # section | appendix | backmatter
    key: str  # e.g. 3.2.1 or appendix-3 or references
    title: str
    lines: Tuple[str, ...]


def _read_text_lines(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Normalize newlines but keep content identical otherwise.
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _slugify(value: str, max_len: int = 80) -> str:
    value = value.strip().lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9\s\-()]+", "", value)
    value = re.sub(r"[\s\-]+", "-", value).strip("-")
    if len(value) > max_len:
        value = value[:max_len].rstrip("-")
    return value or "untitled"


def _components(num: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in num.split("."))


def _section_filename(num: str, title: str) -> str:
    parts = _components(num)
    major = parts[0]
    minor = parts[1] if len(parts) >= 2 else 0
    rest = parts[2:]

    if minor == 0:
        prefix = f"section-{major}"
    else:
        prefix = f"section-{major}-{minor}"

    if rest:
        prefix += "-" + "-".join(str(p) for p in rest)

    return f"{prefix}-{_slugify(title)}.md"


def _appendix_filename(num: str, title: str) -> str:
    return f"appendix-{int(num)}-{_slugify(title)}.md"


def _h1_for_segment(seg: Segment) -> str:
    if seg.kind == "section":
        return f"# SECTION {seg.key}: {seg.title.upper()}"
    if seg.kind == "appendix":
        # key is appendix-<n>
        n = seg.key.split("-")[-1]
        return f"# APPENDIX {n}: {seg.title.upper()}"
    # backmatter
    return f"# {seg.title.upper()}"


def _metadata_for_segment(seg: Segment) -> str:
    # Keep metadata lightweight but consistent with ED style.
    category = "general"
    use_case = "reference"
    patient_input = "none"
    output = "section_content"
    critical: Optional[str] = None

    if seg.kind == "appendix":
        category = "appendix"
        use_case = "supporting_reference"
        output = "appendix_content"
    elif seg.kind == "backmatter":
        category = seg.key
        use_case = "supporting_reference"
        output = seg.key
    elif seg.kind == "section":
        # Heuristic mapping based on section numbering.
        major = int(seg.key.split(".")[0])
        if major == 0:
            category = "preliminaries"
            use_case = "guideline_context"
            output = "guideline_metadata"
        if major == 1:
            category = "introduction"
            use_case = "scope_and_objectives"
            output = "guideline_scope"
        elif major == 2:
            category = "epidemiology"
            use_case = "risk_context"
            output = "epidemiology_context"
        elif major == 3:
            category = "diagnosis"
            use_case = "diagnostic_workup"
            patient_input = "symptoms, signs, labs, imaging"
            output = "diagnosis_criteria, diagnostic_pathway"
            critical = "true" if seg.key.startswith("3.4") else None
        elif major == 4:
            category = "management"
            use_case = "treatment_planning"
            patient_input = "diagnosis, severity, comorbidities, microbiology"
            output = "treatment_plan, monitoring_plan"
            critical = "true" if seg.key.startswith("4.2") else None
        elif major == 5:
            category = "surgery"
            use_case = "surgical_decision"
            patient_input = "diagnosis, complications, imaging"
            output = "surgical_indications, timing"
        elif major == 6:
            category = "followup"
            use_case = "outcomes_and_followup"
            output = "followup_plan"
        elif major == 7:
            category = "special_situations"
            use_case = "special_population_management"
            output = "modified_management"
        elif major == 8:
            category = "prophylaxis"
            use_case = "procedure_prophylaxis"
            patient_input = "cardiac_risk_category, planned_procedure"
            output = "prophylaxis_regimen"
            critical = "true"
        elif major == 9:
            category = "implementation"
            use_case = "implementation_guidance"
            output = "resource_implications"
        elif major == 10:
            category = "appendices"
            use_case = "supporting_reference"
            output = "appendix_index"

    lines = [
        "<!-- METADATA",
        f"category: {category}",
        f"use_case: {use_case}",
        f"patient_input: {patient_input}",
        f"output: {output}",
    ]
    if critical is not None:
        lines.append(f"critical: {critical}")
    lines.append("-->")
    return "\n".join(lines)


def _find_index(lines: Sequence[str], start: int, pattern: re.Pattern[str]) -> Optional[int]:
    for i in range(start, len(lines)):
        if pattern.match(lines[i].strip()):
            return i
    return None


def _collect_numeric_headings(lines: Sequence[str], start: int, end: int) -> List[Tuple[int, str, str]]:
    found: List[Tuple[int, str, str]] = []
    for i in range(start, min(end, len(lines))):
        m = H2_NUMERIC_RE.match(lines[i].strip())
        if not m:
            continue
        found.append((i, m.group("num"), m.group("title")))
    return found


def _split_by_depth(
    segment: Segment,
    max_lines: int = 480,
) -> List[Segment]:
    """Split a numeric section segment into smaller child segments when too large.

    The parent segment is kept, but only contains content before the first child heading.
    """

    if segment.kind != "section":
        return [segment]

    if len(segment.lines) <= max_lines:
        return [segment]

    base_num = segment.key
    base_parts = base_num.split(".")
    base_depth = len(base_parts)
    child_depth = base_depth + 1

    # Find child headings like "4.2.1 ..." inside this segment.
    child_re = re.compile(
        r"^##\s+(?P<num>" + re.escape(base_num) + r"(?:\.\d+)+)\s+(?P<title>.+?)\s*$"
    )

    child_headings: List[Tuple[int, str, str]] = []
    for idx, line in enumerate(segment.lines):
        m = child_re.match(line.strip())
        if not m:
            continue
        num = m.group("num")
        if len(num.split(".")) != child_depth:
            continue
        child_headings.append((idx, num, m.group("title")))

    if len(child_headings) < 2:
        # Nothing reasonable to split by.
        return [segment]

    # Build parent intro segment (same key).
    first_child_idx = child_headings[0][0]
    parent_lines = segment.lines[:first_child_idx]
    out: List[Segment] = []
    out.append(Segment(kind=segment.kind, key=segment.key, title=segment.title, lines=tuple(parent_lines)))

    # Build children.
    for j, (rel_start, num, title) in enumerate(child_headings):
        rel_end = child_headings[j + 1][0] if j + 1 < len(child_headings) else len(segment.lines)
        child_lines = segment.lines[rel_start:rel_end]
        out.append(Segment(kind="section", key=num, title=title, lines=tuple(child_lines)))

    # Recursively split children if still too large.
    final: List[Segment] = []
    for seg in out:
        if seg is out[0]:
            final.append(seg)
            continue
        final.extend(_split_by_depth(seg, max_lines=max_lines))

    return final


def _extract_tables_and_figures(lines: Sequence[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return maps of Table/ Figure IDs to markdown blocks (title + table/figure body)."""

    tables: Dict[str, str] = {}
    figures: Dict[str, str] = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        tm = TABLE_TITLE_RE.match(line)
        if tm:
            table_id = tm.group("id")
            title_line = lines[i]
            # Find the first markdown table row line.
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("|"):
                # stop if we hit a new H2 heading before any table
                if lines[j].strip().startswith("## "):
                    break
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("|"):
                k = j
                while k < len(lines) and (lines[k].lstrip().startswith("|") or lines[k].strip() == ""):
                    # stop on a new H2 heading
                    if lines[k].strip().startswith("## ") and not lines[k].lstrip().startswith("|"):
                        break
                    k += 1
                block = "\n".join([title_line] + lines[j:k]).strip()
                tables[table_id] = block
                i = max(i + 1, k)
                continue

        fm = FIGURE_TITLE_RE.match(line)
        if fm:
            fig_id = fm.group("id")
            title_line = lines[i]
            # Figure bodies are typically just an image placeholder plus maybe some text.
            j = i + 1
            body: List[str] = []
            while j < len(lines):
                nxt = lines[j]
                if nxt.strip().startswith("## "):
                    break
                body.append(nxt)
                j += 1
            block = "\n".join([title_line] + body).strip()
            figures[fig_id] = block
            i = max(i + 1, j)
            continue

        i += 1

    return tables, figures


def _build_segments(source_lines: List[str]) -> Tuple[List[Segment], Dict[str, Segment]]:
    """Split the source markdown into segments and return (segments, appendix_map)."""

    # Locate major boundaries.
    idx_appendices = _find_index(source_lines, 0, H2_APPENDICES_RE)
    if idx_appendices is None:
        raise RuntimeError("Could not find '10.0 APPENDICES' heading")

    idx_global_refs = _find_index(source_lines, idx_appendices + 1, H2_GLOBAL_REFS_RE)
    if idx_global_refs is None:
        raise RuntimeError("Could not find global 'REFERENCES' heading")

    idx_ack = _find_index(source_lines, idx_global_refs + 1, H2_ACK_RE)
    idx_disclosure = _find_index(source_lines, idx_global_refs + 1, H2_DISCLOSURE_RE)
    idx_funding = _find_index(source_lines, idx_global_refs + 1, H2_FUNDING_RE)

    # First numeric heading = beginning of main content.
    numeric_headings_all = _collect_numeric_headings(source_lines, 0, idx_appendices)
    if not numeric_headings_all:
        raise RuntimeError("Could not find any numeric headings")

    first_numeric_idx = numeric_headings_all[0][0]

    segments: List[Segment] = []

    # Preliminaries: split into multiple 0.x sections to keep files small.
    prelim_lines = source_lines[:first_numeric_idx]

    def _norm_heading(line: str) -> str:
        return re.sub(r"\s+", " ", line.strip()).upper()

    prel_targets: List[Tuple[str, str]] = [
        ("0.1", "TABLE OF CONTENTS"),
        ("0.2", "FOREWORD BY THE DIRECTOR GENERAL OF HEALTH"),
        ("0.3", "INFECTIVE ENDOCARDITIS CLINICAL PRACTICE GUIDELINES EXPERT PANEL"),
        ("0.4", "EXTERNAL REVIEWERS"),
        ("0.5", "GRADES OF RECOMMENDATION AND LEVELS OF EVIDENCE"),
        ("0.6", "RATIONALE AND PROCESS OF THE INFECTIVE ENDOCARDITIS GUIDELINES DEVELOPMENT"),
        (
            "0.7",
            "SUMMARY OF THE CLINICAL PRACTICE GUIDELINES FOR THE PREVENTION, DIAGNOSIS AND MANAGEMENT OF INFECTIVE ENDOCARDITIS",
        ),
    ]

    boundaries_prel: List[Tuple[int, str, str]] = []
    seen_keys: Set[str] = set()
    for i, line in enumerate(prelim_lines):
        norm = _norm_heading(line)
        for key, title in prel_targets:
            if key in seen_keys:
                continue
            if norm == _norm_heading(f"## {title}"):
                boundaries_prel.append((i, key, title))
                seen_keys.add(key)
                break

    if boundaries_prel:
        # 0.0 = everything before first major prelim heading.
        segments.append(
            Segment(kind="section", key="0.0", title="PRELIMINARIES", lines=tuple(prelim_lines[: boundaries_prel[0][0]]))
        )
        for j, (rel_start, key, title) in enumerate(boundaries_prel):
            rel_end = boundaries_prel[j + 1][0] if j + 1 < len(boundaries_prel) else len(prelim_lines)
            segments.append(Segment(kind="section", key=key, title=title, lines=tuple(prelim_lines[rel_start:rel_end])))
    else:
        segments.append(Segment(kind="section", key="0.0", title="PRELIMINARIES", lines=tuple(prelim_lines)))

    # Main numeric sections: split by depth-2 section keys (e.g. 3.2) but keep their
    # full content; we later split further if too large.
    main_lines = source_lines[first_numeric_idx:idx_appendices]

    # Find boundaries for depth-2 headings within main_lines.
    boundaries: List[Tuple[int, str, str]] = []
    last_key_tuple: Optional[Tuple[int, int]] = None
    for rel_i, line in enumerate(main_lines):
        m = H2_NUMERIC_RE.match(line.strip())
        if not m:
            continue
        num = m.group("num")
        parts = num.split(".")
        if len(parts) < 2:
            continue
        key = f"{parts[0]}.{parts[1]}"  # depth-2
        key_tuple = (int(parts[0]), int(parts[1]))
        # Docling output often repeats page-header H2s like "3.0 DIAGNOSIS" inside
        # deeper sections. Those headings look like *backwards jumps* at depth-2.
        # Treat only monotonic increases as true section starts.
        if last_key_tuple is not None and key_tuple <= last_key_tuple:
            continue
        last_key_tuple = key_tuple
        boundaries.append((rel_i, key, m.group("title")))

    for j, (rel_start, key, title) in enumerate(boundaries):
        rel_end = boundaries[j + 1][0] if j + 1 < len(boundaries) else len(main_lines)
        seg_lines = main_lines[rel_start:rel_end]
        segments.append(Segment(kind="section", key=key, title=title, lines=tuple(seg_lines)))

    # Appendices area: include a small Section 10 overview (content from the 10.0
    # heading until Appendix 1).
    appendices_lines = source_lines[idx_appendices:idx_global_refs]

    appendix_headings: List[Tuple[int, str, str]] = []
    for rel_i, line in enumerate(appendices_lines):
        stripped = line.strip()

        m = H2_APPENDIX_RE.match(stripped)
        if m:
            appendix_headings.append((rel_i, m.group("num"), m.group("title")))
            continue

        tm = APPENDIX_TABLE_HEADING_RE.match(stripped)
        if tm:
            appendix_headings.append((rel_i, tm.group("num"), tm.group("title")))

    if not appendix_headings:
        raise RuntimeError("Could not find any Appendix headings")

    # Section 10 overview.
    seg10_lines = appendices_lines[: appendix_headings[0][0]]
    segments.append(Segment(kind="section", key="10.0", title="APPENDICES", lines=tuple(seg10_lines)))

    appendix_map: Dict[str, Segment] = {}

    for j, (rel_start, num, title) in enumerate(appendix_headings):
        rel_end = appendix_headings[j + 1][0] if j + 1 < len(appendix_headings) else len(appendices_lines)
        seg_lines = appendices_lines[rel_start:rel_end]
        seg = Segment(kind="appendix", key=f"appendix-{int(num)}", title=title, lines=tuple(seg_lines))
        segments.append(seg)
        appendix_map[str(int(num))] = seg

    # Backmatter.
    end = len(source_lines)
    if idx_ack is not None:
        segments.append(Segment(kind="backmatter", key="references", title="References", lines=tuple(source_lines[idx_global_refs:idx_ack])))
        if idx_disclosure is not None:
            segments.append(Segment(kind="backmatter", key="acknowledgement", title="Acknowledgement", lines=tuple(source_lines[idx_ack:idx_disclosure])))
        else:
            segments.append(Segment(kind="backmatter", key="acknowledgement", title="Acknowledgement", lines=tuple(source_lines[idx_ack:end])))
    else:
        segments.append(Segment(kind="backmatter", key="references", title="References", lines=tuple(source_lines[idx_global_refs:end])))

    if idx_disclosure is not None and idx_funding is not None:
        segments.append(Segment(kind="backmatter", key="disclosure-statement", title="Disclosure Statement", lines=tuple(source_lines[idx_disclosure:idx_funding])))
        segments.append(Segment(kind="backmatter", key="sources-of-funding", title="Sources Of Funding", lines=tuple(source_lines[idx_funding:end])))
    elif idx_disclosure is not None:
        segments.append(Segment(kind="backmatter", key="disclosure-statement", title="Disclosure Statement", lines=tuple(source_lines[idx_disclosure:end])))

    return segments, appendix_map


def _materialize_segments(segments: List[Segment], out_dir: Path) -> Dict[str, Path]:
    """Write segments to disk and return mapping segment_key -> filepath."""

    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous .md outputs in this directory.
    for p in out_dir.glob("*.md"):
        p.unlink()

    key_to_path: Dict[str, Path] = {}

    for seg in segments:
        if seg.kind == "section":
            # Special-case 0.0 to keep a predictable filename.
            if seg.key == "0.0":
                filename = "section-0-preliminaries.md"
            else:
                filename = _section_filename(seg.key, seg.title)
        elif seg.kind == "appendix":
            n = seg.key.split("-")[-1]
            filename = _appendix_filename(n, seg.title)
        else:
            # backmatter
            filename = f"{seg.key}.md"

        path = out_dir / filename

        h1 = _h1_for_segment(seg)
        meta = _metadata_for_segment(seg)
        body = "\n".join(seg.lines).strip()

        # Ensure there's always a body; but keep empty segments valid.
        content = "\n\n".join([h1, meta, body]).strip() + "\n"
        _write_text(path, content)
        key_to_path[seg.key] = path

    return key_to_path


def _inject_overlaps(
    source_lines: List[str],
    out_paths: Dict[str, Path],
    appendix_map: Dict[str, Segment],
) -> None:
    tables, figures = _extract_tables_and_figures(source_lines)

    # Precompute appendix bodies (without their own H1/METADATA wrappers).
    appendix_num_to_body: Dict[str, str] = {}
    for num, seg in appendix_map.items():
        appendix_num_to_body[num] = "\n".join(seg.lines).strip()

    def _extract_table_ids(text: str) -> List[str]:
        ids: Set[str] = set(TABLE_REF_RE.findall(text))
        for m in TABLE_MULTI_REF_RE.finditer(text):
            ids.update(re.findall(r"\d+(?:\.\d+)*", m.group("seq")))
        return sorted(ids)

    def _extract_appendix_nums(text: str) -> List[str]:
        nums: Set[str] = set(APPENDIX_REF_RE.findall(text))
        for m in APPENDIX_MULTI_REF_RE.finditer(text):
            nums.update(re.findall(r"\d+", m.group("seq")))
        return sorted(nums, key=lambda x: int(x))

    for seg_key, path in out_paths.items():
        text = path.read_text(encoding="utf-8")
        existing = text

        # Skip overlap injection for appendices themselves.
        if path.name.startswith("appendix-"):
            continue

        refs_tables = _extract_table_ids(text)
        refs_figs = sorted(set(FIGURE_REF_RE.findall(text)))
        refs_apps = _extract_appendix_nums(text)

        overlap_blocks: List[str] = []

        # Tables.
        for table_id in refs_tables:
            if f"Table {table_id}:" in text or f"Table {table_id} :" in text:
                continue
            block = tables.get(table_id)
            if block:
                overlap_blocks.append(block)

        # Figures.
        for fig_id in refs_figs:
            if f"Figure {fig_id}:" in text:
                continue
            block = figures.get(fig_id)
            if block:
                overlap_blocks.append(block)

        # Appendices.
        for app_num in refs_apps:
            if f"Appendix {app_num}:" in text:
                continue
            body = appendix_num_to_body.get(app_num)
            if body:
                overlap_blocks.append(body)

        # Targeted implicit prerequisite: modified Duke criteria.
        if "duke" in text.lower() and "3.4" not in seg_key:
            # Include all tables that look like Duke criteria (Table 3.* with 'Duke').
            duke_tables = [tbl for tid, tbl in tables.items() if tid.startswith("3.") and "duke" in tbl.lower()]
            for blk in duke_tables:
                if blk not in overlap_blocks and blk not in existing:
                    overlap_blocks.append(blk)

        if not overlap_blocks:
            continue

        overlap_text = "\n\n".join([
            "## OVERLAP (DUPLICATED CONTEXT)",
            "The following content is duplicated from other sections/appendices referenced in this section so the file is standalone.",
            "---",
            "\n\n".join(overlap_blocks).strip(),
        ]).strip()

        new_text = (existing.rstrip() + "\n\n" + overlap_text + "\n")
        path.write_text(new_text, encoding="utf-8")


def main() -> None:
    if not SOURCE_MD.exists():
        raise SystemExit(f"Source file not found: {SOURCE_MD}")

    source_lines = _read_text_lines(SOURCE_MD)

    segments, appendix_map = _build_segments(source_lines)

    # Split large segments iteratively.
    expanded: List[Segment] = []
    for seg in segments:
        expanded.extend(_split_by_depth(seg))

    out_paths = _materialize_segments(expanded, OUT_MD_DIR)
    _inject_overlaps(source_lines, out_paths, appendix_map)

    # Mirror markdown outputs into documents/ for ingestion.
    OUT_DOC_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DOC_DIR.glob("*.md"):
        p.unlink()
    for p in OUT_MD_DIR.glob("*.md"):
        shutil.copy2(p, OUT_DOC_DIR / p.name)

    print(f"Wrote {len(list(OUT_MD_DIR.glob('*.md')))} files to {OUT_MD_DIR}")
    print(f"Mirrored to {OUT_DOC_DIR}")


if __name__ == "__main__":
    main()
