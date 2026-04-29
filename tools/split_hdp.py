"""Split the Heart Disease in Pregnancy CPG markdown into section files.

This script:
- Splits the master markdown into section markdown files.
- Adds ED-style metadata blocks and H1 headings.
- Injects overlap blocks so each section stands alone.
- Mirrors the output into documents/ for ingestion.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD = WORKSPACE_ROOT / "markdown" / "CPG Heart Disease in Pregnancy.md"
OUT_MD_DIR = WORKSPACE_ROOT / "markdown" / "Heart-Disease-In-Pregnancy"
OUT_DOC_DIR = WORKSPACE_ROOT / "documents" / "Heart-Disease-In-Pregnancy"


NUMERIC_HEADING_RE = re.compile(
    r"^#{1,2}\s+(?P<num>\d+(?:\.\d+)*)(?:\s+|\.)\s*(?P<title>.+?)\s*$"
)
APPENDIX_HEADING_RE = re.compile(
    r"^#{1,2}\s+Appendix\s+(?P<num>\d+)(?:\s*[:\-]\s*|\s+)(?P<title>.+?)\s*$",
    re.IGNORECASE,
)
BACKMATTER_HEADING_RE = re.compile(
    r"^#{1,2}\s+(?P<title>REFERENCES|ACKNOWLEDGEMENT|ACKNOWLEDGMENTS|DISCLOSURE STATEMENT|SOURCES OF FUNDING|"
    r"LIST OF TABLES|LIST OF FIGURES|LIST OF APPENDICES|TABLE OF CONTENTS|KEY MESSAGES|SUMMARY OF RECOMMENDATIONS)\s*$",
    re.IGNORECASE,
)

TABLE_TITLE_RE = re.compile(r"^(?:##\s+)?Table\s+(?P<id>\d+(?:\.\d+)*)(?::|\s+)\s*(?P<title>.+?)\s*$", re.IGNORECASE)
FIGURE_TITLE_RE = re.compile(r"^(?:##\s+)?Figure\s+(?P<id>\d+(?:\.\d+)*)(?::|\s+)\s*(?P<title>.+?)\s*$", re.IGNORECASE)
ALGORITHM_TITLE_RE = re.compile(r"^(?:##\s+)?Algorithm\s+(?P<id>\d+(?:\.\d+)*)(?::|\s+)\s*(?P<title>.+?)\s*$", re.IGNORECASE)
BOX_TITLE_RE = re.compile(r"^(?:##\s+)?Box\s+(?P<id>\d+(?:\.\d+)*)(?::|\s+)\s*(?P<title>.+?)\s*$", re.IGNORECASE)

TABLE_REF_RE = re.compile(r"\bTable\s+(?P<id>\d+(?:\.\d+)*)\b", re.IGNORECASE)
FIGURE_REF_RE = re.compile(r"\bFigure\s+(?P<id>\d+(?:\.\d+)*)\b", re.IGNORECASE)
ALGORITHM_REF_RE = re.compile(r"\bAlgorithm\s+(?P<id>\d+(?:\.\d+)*)\b", re.IGNORECASE)
BOX_REF_RE = re.compile(r"\bBox\s+(?P<id>\d+(?:\.\d+)*)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Meta:
    """Metadata for a section file.

    Args:
        category: High-level content category.
        use_case: Intended RAG use case.
        patient_input: Typical patient inputs required.
        output: Expected output or guidance.
    """

    category: str
    use_case: str
    patient_input: str
    output: str


@dataclass(frozen=True)
class Segment:
    """A contiguous content segment extracted from the master markdown.

    Args:
        kind: Segment type (section, appendix, backmatter).
        key: Section key (e.g., 3.2) or appendix-1 or references.
        title: Section title.
        lines: Raw markdown lines for this segment.
    """

    kind: str
    key: str
    title: str
    lines: Tuple[str, ...]


def _read_text_lines(path: Path) -> List[str]:
    """Read a text file into a list of lines with normalized newlines.

    Args:
        path: Path to the markdown file.

    Returns:
        List of lines with normalized newlines.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _write_text(path: Path, text: str) -> None:
    """Write text to a file and ensure a trailing newline.

    Args:
        path: Output file path.
        text: File content.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _slugify(value: str, max_len: int = 80) -> str:
    """Create a filesystem-safe slug.

    Args:
        value: Input string.
        max_len: Maximum length for the slug.

    Returns:
        Slugified string.
    """

    cleaned = value.strip().lower()
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^a-z0-9\s\-()]+", "", cleaned)
    cleaned = re.sub(r"[\s\-]+", "-", cleaned).strip("-")
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip("-")
    return cleaned or "untitled"


def _render_metadata(meta: Meta) -> str:
    """Render an ED-style metadata block.

    Args:
        meta: Metadata values.

    Returns:
        Rendered metadata block.
    """

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


def _infer_metadata(title: str, kind: str) -> Meta:
    """Infer metadata for a section based on its title.

    Args:
        title: Section title.
        kind: Segment type.

    Returns:
        Metadata inferred from title keywords.
    """

    if kind == "appendix":
        return Meta(
            category="appendix",
            use_case="supporting_reference",
            patient_input="none",
            output="appendix_content",
        )

    if kind == "backmatter":
        return Meta(
            category=title.lower().replace(" ", "_"),
            use_case="supporting_reference",
            patient_input="none",
            output="section_reference",
        )

    title_lower = title.lower()
    if any(word in title_lower for word in ["introduction", "overview", "scope"]):
        return Meta("introduction", "scope_and_objectives", "none", "guideline_scope")
    if any(word in title_lower for word in ["epidemiology", "background"]):
        return Meta("background_knowledge", "epidemiology", "population_risk_factors", "epidemiology_context")
    if any(word in title_lower for word in ["risk", "stratification", "classification", "mwho"]):
        return Meta(
            "risk_stratification",
            "risk_assessment",
            "cardiac_lesion, symptoms, functional_class, ventricular_function",
            "risk_classification",
        )
    if any(word in title_lower for word in ["diagnosis", "assessment", "evaluation", "investigation"]):
        return Meta(
            "diagnosis",
            "diagnostic_workup",
            "symptoms, exam, imaging, labs",
            "diagnostic_plan",
        )
    if any(word in title_lower for word in ["management", "treatment", "therapy", "medication", "anticoagulation"]):
        return Meta(
            "treatment",
            "treatment_planning",
            "diagnosis, gestational_age, risk_class, comorbidities",
            "treatment_plan",
        )
    if any(word in title_lower for word in ["delivery", "labour", "labor", "intrapartum"]):
        return Meta(
            "delivery_planning",
            "delivery_management",
            "risk_class, gestational_age, maternal_status, fetal_status",
            "delivery_plan",
        )
    if any(word in title_lower for word in ["postpartum", "puerperium"]):
        return Meta(
            "postpartum_care",
            "postpartum_management",
            "delivery_outcome, maternal_status",
            "postpartum_plan",
        )
    if any(word in title_lower for word in ["contraception", "family planning"]):
        return Meta(
            "contraception",
            "family_planning",
            "cardiac_condition, risk_class",
            "contraception_recommendation",
        )
    if any(word in title_lower for word in ["follow-up", "follow up", "monitoring"]):
        return Meta(
            "followup",
            "monitoring_and_followup",
            "risk_class, symptoms, clinical_status",
            "followup_plan",
        )

    return Meta("general", "reference", "none", "section_content")


def _h1_for_segment(seg: Segment) -> str:
    """Create an H1 heading for a section.

    Args:
        seg: Section segment.

    Returns:
        H1 heading string.
    """

    if seg.kind == "section":
        key = seg.key
        if key.endswith(".0"):
            key = key.split(".")[0]
        return f"# SECTION {key}: {seg.title.upper()}"
    if seg.kind == "appendix":
        num = seg.key.split("-")[-1]
        return f"# APPENDIX {num}: {seg.title.upper()}"
    return f"# {seg.title.upper()}"


def _section_filename(key: str, title: str) -> str:
    """Build a filename for a numbered section.

    Args:
        key: Section key (e.g., 3.2.1).
        title: Section title.

    Returns:
        Filename for the section.
    """

    parts = key.split(".")
    prefix = "section-" + "-".join(parts)
    return f"{prefix}-{_slugify(title)}.md"


def _appendix_filename(num: str, title: str) -> str:
    """Build a filename for an appendix.

    Args:
        num: Appendix number.
        title: Appendix title.

    Returns:
        Appendix filename.
    """

    return f"appendix-{int(num)}-{_slugify(title)}.md"


def _collect_boundaries(lines: Sequence[str]) -> List[Tuple[int, str, str, str]]:
    """Collect section boundary markers from markdown lines.

    Args:
        lines: Markdown lines.

    Returns:
        List of tuples (index, kind, key, title).
    """

    boundaries: List[Tuple[int, str, str, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        numeric = NUMERIC_HEADING_RE.match(stripped)
        if numeric:
            num = numeric.group("num")
            title = numeric.group("title")
            boundaries.append((idx, "section", num, title))
            continue

        appendix = APPENDIX_HEADING_RE.match(stripped)
        if appendix:
            num = appendix.group("num")
            title = appendix.group("title")
            boundaries.append((idx, "appendix", f"appendix-{int(num)}", title))
            continue

        backmatter = BACKMATTER_HEADING_RE.match(stripped)
        if backmatter:
            title = backmatter.group("title")
            key = _slugify(title)
            boundaries.append((idx, "backmatter", key, title))

    boundaries.sort(key=lambda item: item[0])
    return boundaries


def _split_segments(lines: List[str]) -> List[Segment]:
    """Split the master markdown into segments based on headings.

    Args:
        lines: Full markdown lines.

    Returns:
        List of segments in document order.
    """

    boundaries = _collect_boundaries(lines)
    if not boundaries:
        return [Segment(kind="section", key="0.0", title="Preliminaries", lines=tuple(lines))]

    segments: List[Segment] = []
    first_idx = boundaries[0][0]
    prelim = lines[:first_idx]
    segments.append(Segment(kind="section", key="0.0", title="Preliminaries", lines=tuple(prelim)))

    for i, (start_idx, kind, key, title) in enumerate(boundaries):
        end_idx = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
        seg_lines = lines[start_idx:end_idx]
        segments.append(Segment(kind=kind, key=key, title=title, lines=tuple(seg_lines)))

    return segments


def _split_by_depth(segment: Segment, max_lines: int = 480) -> List[Segment]:
    """Split large numeric sections by deeper numeric headings.

    Args:
        segment: Segment to split.
        max_lines: Maximum lines allowed per segment.

    Returns:
        List of segments after splitting.
    """

    if segment.kind != "section":
        return [segment]

    if len(segment.lines) <= max_lines:
        return [segment]

    base_num = segment.key
    base_parts = base_num.split(".")
    child_depth = len(base_parts) + 1

    child_re = re.compile(
        r"^##\s+(?P<num>" + re.escape(base_num) + r"(?:\.\d+)+)\s+(?P<title>.+?)\s*$"
    )

    child_headings: List[Tuple[int, str, str]] = []
    for idx, line in enumerate(segment.lines):
        match = child_re.match(line.strip())
        if not match:
            continue
        num = match.group("num")
        if len(num.split(".")) != child_depth:
            continue
        child_headings.append((idx, num, match.group("title")))

    if len(child_headings) < 2:
        return [segment]

    out: List[Segment] = []
    first_child_idx = child_headings[0][0]
    parent_lines = segment.lines[:first_child_idx]
    if parent_lines:
        out.append(Segment(kind="section", key=segment.key, title=segment.title, lines=tuple(parent_lines)))

    for j, (rel_start, num, title) in enumerate(child_headings):
        rel_end = child_headings[j + 1][0] if j + 1 < len(child_headings) else len(segment.lines)
        child_lines = segment.lines[rel_start:rel_end]
        out.append(Segment(kind="section", key=num, title=title, lines=tuple(child_lines)))

    expanded: List[Segment] = []
    for seg in out:
        if seg is out[0]:
            expanded.append(seg)
            continue
        expanded.extend(_split_by_depth(seg, max_lines=max_lines))

    return expanded


def _extract_blocks_by_heading(
    lines: Sequence[str],
    title_re: re.Pattern[str],
    require_table: bool = False,
) -> Dict[str, str]:
    """Extract labeled blocks like tables, figures, algorithms, and boxes.

    Args:
        lines: Markdown lines.
        title_re: Regex for the title line.
        require_table: Whether to require table rows in the block.

    Returns:
        Mapping of label id to markdown block.
    """

    blocks: Dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = title_re.match(line)
        if not match:
            i += 1
            continue

        block_id = match.group("id")
        title_line = lines[i]

        j = i + 1
        if require_table:
            while j < len(lines) and not lines[j].lstrip().startswith("|"):
                if lines[j].strip().startswith("## "):
                    break
                j += 1
            if j >= len(lines) or not lines[j].lstrip().startswith("|"):
                i += 1
                continue

        k = j
        while k < len(lines):
            if lines[k].strip().startswith("## "):
                break
            k += 1

        block = "\n".join([title_line] + lines[j:k]).strip()
        blocks[block_id] = block
        i = max(i + 1, k)

    return blocks


def _extract_keyword_blocks(lines: Sequence[str], keywords: Iterable[str]) -> Dict[str, str]:
    """Extract blocks for headings containing given keywords.

    Args:
        lines: Markdown lines.
        keywords: Keywords to match in heading lines.

    Returns:
        Mapping of heading titles to their blocks.
    """

    blocks: Dict[str, str] = {}
    keyword_set = [kw.lower() for kw in keywords]

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("#"):
            i += 1
            continue

        heading = line.lstrip("#").strip()
        heading_lower = heading.lower()
        if not any(kw in heading_lower for kw in keyword_set):
            i += 1
            continue

        j = i + 1
        while j < len(lines):
            if lines[j].strip().startswith("#"):
                break
            j += 1

        blocks[heading] = "\n".join(lines[i:j]).strip()
        i = max(i + 1, j)

    return blocks


def _materialize_segments(segments: List[Segment], out_dir: Path) -> Dict[str, Path]:
    """Write segments to disk.

    Args:
        segments: Segment list.
        out_dir: Output directory.

    Returns:
        Mapping of segment key to output path.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    for path in out_dir.glob("*.md"):
        path.unlink()

    key_to_path: Dict[str, Path] = {}
    for seg in segments:
        if seg.kind == "section":
            filename = "section-0-preliminaries.md" if seg.key == "0.0" else _section_filename(seg.key, seg.title)
        elif seg.kind == "appendix":
            num = seg.key.split("-")[-1]
            filename = _appendix_filename(num, seg.title)
        else:
            filename = f"{_slugify(seg.title)}.md"

        meta = _render_metadata(_infer_metadata(seg.title, seg.kind))
        body = "\n".join(seg.lines).strip()
        content = "\n\n".join([_h1_for_segment(seg), meta, body]).strip() + "\n"
        path = out_dir / filename
        _write_text(path, content)
        key_to_path[seg.key] = path

    return key_to_path


def _inject_overlaps(source_lines: List[str], out_paths: Dict[str, Path]) -> None:
    """Append overlap context blocks to sections that reference them.

    Args:
        source_lines: Full markdown lines.
        out_paths: Mapping of segment keys to output files.
    """

    tables = _extract_blocks_by_heading(source_lines, TABLE_TITLE_RE, require_table=True)
    figures = _extract_blocks_by_heading(source_lines, FIGURE_TITLE_RE)
    algorithms = _extract_blocks_by_heading(source_lines, ALGORITHM_TITLE_RE)
    boxes = _extract_blocks_by_heading(source_lines, BOX_TITLE_RE)
    keyword_blocks = _extract_keyword_blocks(source_lines, ["criteria", "dosage", "dose", "algorithm"])

    for path in out_paths.values():
        if path.name.startswith("appendix-"):
            continue

        text = path.read_text(encoding="utf-8")
        lower_text = text.lower()
        overlap_blocks: List[str] = []

        for table_id in sorted(set(TABLE_REF_RE.findall(text))):
            block = tables.get(table_id)
            if block and block not in text:
                overlap_blocks.append(block)

        for fig_id in sorted(set(FIGURE_REF_RE.findall(text))):
            block = figures.get(fig_id)
            if block and block not in text:
                overlap_blocks.append(block)

        for algo_id in sorted(set(ALGORITHM_REF_RE.findall(text))):
            block = algorithms.get(algo_id)
            if block and block not in text:
                overlap_blocks.append(block)

        for box_id in sorted(set(BOX_REF_RE.findall(text))):
            block = boxes.get(box_id)
            if block and block not in text:
                overlap_blocks.append(block)

        if "criteria" in lower_text:
            for block in keyword_blocks.values():
                if "criteria" in block.lower() and block not in text:
                    overlap_blocks.append(block)

        if "dosage" in lower_text or "dose" in lower_text:
            for block in keyword_blocks.values():
                if ("dosage" in block.lower() or "dose" in block.lower()) and block not in text:
                    overlap_blocks.append(block)

        if not overlap_blocks:
            continue

        overlap_text = "\n\n".join(
            [
                "## OVERLAP (DUPLICATED CONTEXT)",
                "The following content is duplicated from other sections referenced in this section so the file is standalone.",
                "---",
                "\n\n".join(overlap_blocks).strip(),
            ]
        ).strip()

        path.write_text(text.rstrip() + "\n\n" + overlap_text + "\n", encoding="utf-8")


def main() -> None:
    """Run the split-and-overlap workflow."""

    if not SOURCE_MD.exists():
        raise SystemExit(f"Source file not found: {SOURCE_MD}")

    source_lines = _read_text_lines(SOURCE_MD)
    segments = _split_segments(source_lines)

    expanded: List[Segment] = []
    for seg in segments:
        expanded.extend(_split_by_depth(seg))

    out_paths = _materialize_segments(expanded, OUT_MD_DIR)
    _inject_overlaps(source_lines, out_paths)

    OUT_DOC_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUT_DOC_DIR.glob("*.md"):
        path.unlink()
    for path in OUT_MD_DIR.glob("*.md"):
        shutil.copy2(path, OUT_DOC_DIR / path.name)

    print(f"Wrote {len(list(OUT_MD_DIR.glob('*.md')))} files to {OUT_MD_DIR}")
    print(f"Mirrored to {OUT_DOC_DIR}")


if __name__ == "__main__":
    main()