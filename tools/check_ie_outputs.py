"""Quick sanity checks for generated IE markdown section files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


APPENDIX_REF_RE = re.compile(r"\bAppendix\s+(?P<num>\d+)\b", re.IGNORECASE)
APPENDIX_MULTI_REF_RE = re.compile(
    r"\bAppendix(?:es)?\s+(?P<seq>\d+(?:\s*(?:,|&|and)\s*\d+)*)\b",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_appendix_nums(text: str) -> list[str]:
    nums = {m.group("num") for m in APPENDIX_REF_RE.finditer(text)}
    for m in APPENDIX_MULTI_REF_RE.finditer(text):
        nums.update(re.findall(r"\d+", m.group("seq")))
    return sorted(nums, key=lambda x: int(x))


def main() -> None:
    root = Path("markdown/Infective-Endocarditis(2017)")
    doc_root = Path("documents/Infective-Endocarditis(2017)")
    files = sorted(root.glob("*.md"))
    doc_files = sorted(doc_root.glob("*.md"))

    max_lines = 0
    max_file: Path | None = None
    h1_violations: list[tuple[str, int, int]] = []
    too_long: list[tuple[str, int]] = []
    metadata_missing: list[str] = []
    mirror_missing: list[str] = []
    mirror_hash_mismatch: list[str] = []
    appendix_overlap_missing: list[tuple[str, str]] = []

    doc_names = {p.name for p in doc_files}

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        n = len(lines)
        if n > max_lines:
            max_lines = n
            max_file = path
        h1 = sum(1 for l in lines if re.match(r"^#\s+\S", l))
        if h1 != 1:
            h1_violations.append((path.name, n, h1))
        if n > 500:
            too_long.append((path.name, n))

        if "<!-- METADATA" not in text:
            metadata_missing.append(path.name)

        if path.name not in doc_names:
            mirror_missing.append(path.name)
        else:
            doc_path = doc_root / path.name
            if _sha256(path) != _sha256(doc_path):
                mirror_hash_mismatch.append(path.name)

        # Overlap sanity check: if a section references an Appendix N, ensure that
        # Appendix N content appears somewhere in the file (either as H2 appendix
        # heading or as the Appendix 7-style table heading).
        if not path.name.startswith("appendix-"):
            for app_num in _extract_appendix_nums(text):
                has_h2 = re.search(rf"^##\s+Appendix\s+{app_num}:", text, flags=re.IGNORECASE | re.MULTILINE)
                has_table = re.search(rf"^\|\s*Appendix\s+{app_num}:", text, flags=re.IGNORECASE | re.MULTILINE)
                if not has_h2 and not has_table:
                    appendix_overlap_missing.append((path.name, app_num))

    print("files", len(files))
    print("documents_files", len(doc_files))
    print("max_lines", max_lines, "max_file", str(max_file) if max_file else "<none>")
    print("too_long", len(too_long))
    for name, n in sorted(too_long, key=lambda x: x[1], reverse=True)[:25]:
        print("  ", n, name)
    print("h1_violations", len(h1_violations))
    for name, n, h1 in h1_violations[:25]:
        print("  ", name, "lines=", n, "h1=", h1)

    print("metadata_missing", len(metadata_missing))
    for name in metadata_missing[:25]:
        print("  ", name)

    print("mirror_missing", len(mirror_missing))
    for name in mirror_missing[:25]:
        print("  ", name)

    print("mirror_hash_mismatch", len(mirror_hash_mismatch))
    for name in mirror_hash_mismatch[:25]:
        print("  ", name)

    print("appendix_overlap_missing", len(appendix_overlap_missing))
    for name, app in appendix_overlap_missing[:25]:
        print("  ", name, "missing Appendix", app)


if __name__ == "__main__":
    main()
