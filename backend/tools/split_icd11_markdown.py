"""Split an ICD-11 markdown source file into one file per code entry.

This repo stores ICD-11 concepts (code/title/definition/inclusions/exclusions) in markdown
sources under ddx/data. For RAG ingestion and section-level metadata alignment, it's useful
to have one concept per markdown file.

Output format matches the project's CPG section style by adding an HTML comment metadata
block at the top of each generated file.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IcdEntry:
	code: str
	title: str
	body: str
	chapter: str | None = None
	parent_code: str | None = None


HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
CODE_TITLE_RE = re.compile(r"^(?P<code>[A-Z]{2}[0-9A-Z.]+)\s+(?P<title>.+)$")


def _extract_section_label(source_text: str) -> str:
	# Prefer the explicit "Section:" line if present.
	for line in source_text.splitlines():
		if line.strip().lower().startswith("# section:"):
			return line.split(":", 1)[1].strip()
	return "ICD-11"


def parse_entries(source_text: str) -> list[IcdEntry]:
	matches = list(HEADER_RE.finditer(source_text))
	entries: list[IcdEntry] = []
	for idx, m in enumerate(matches):
		start = m.start()
		end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source_text)
		chunk = source_text[start:end].strip("\n")

		lines = chunk.splitlines()
		header_line = lines[0].lstrip("#").strip()  # remove leading '##'
		header_line = header_line.replace("##", "").strip()
		code_title = CODE_TITLE_RE.match(header_line)
		if not code_title:
			continue

		code = code_title.group("code").strip()
		title = code_title.group("title").strip()

		chapter = None
		parent = None
		# Keep the body as the remainder (preserve exact field lines)
		body_lines = lines[1:]
		for line in body_lines:
			stripped = line.strip()
			if stripped.startswith("Chapter:"):
				chapter = stripped.split(":", 1)[1].strip() or None
			elif stripped.startswith("Parent:"):
				parent = stripped.split(":", 1)[1].strip() or None

		body = "\n".join(body_lines).strip() + "\n"
		entries.append(IcdEntry(code=code, title=title, body=body, chapter=chapter, parent_code=parent))

	return entries


def render_entry_md(
	entry: IcdEntry,
	*,
	section_label: str,
	source_rel: str,
	linked_cpg: str | None = None,
) -> str:
	meta_lines: list[str] = [
		"<!-- METADATA",
		"category: icd11",
		f"icd11_code: {entry.code}",
		f"icd11_title: {entry.title}",
		f"icd11_section: {section_label}",
		f"source: {source_rel}",
	]
	if entry.chapter:
		meta_lines.append(f"chapter: {entry.chapter}")
	if entry.parent_code:
		meta_lines.append(f"parent_code: {entry.parent_code}")
	if linked_cpg:
		meta_lines.append(f"linked_cpg: {linked_cpg}")
	meta_lines.append("-->")

	meta_block = "\n".join(meta_lines)

	return (
		f"# ICD-11: {entry.code} {entry.title}\n\n"
		f"{meta_block}\n\n"
		f"{entry.body}"
	)


def main() -> int:
	parser = argparse.ArgumentParser(description="Split ICD-11 markdown into one file per code entry")
	parser.add_argument(
		"--input",
		default="ddx/data/ha00_sexual_dysfunctions.md",
		help="Path to ICD-11 markdown source file",
	)
	parser.add_argument(
		"--output-dir",
		default="test-chunk/Erectile-Dysfunction/icd11",
		help="Directory to write per-code markdown files",
	)
	parser.add_argument(
		"--linked-cpg",
		default="Erectile-Dysfunction",
		help="Optional CPG identifier to store in metadata for traceability",
	)
	parser.add_argument(
		"--overwrite",
		action="store_true",
		help="Overwrite existing output files",
	)
	args = parser.parse_args()

	input_path = Path(args.input)
	if not input_path.exists():
		raise SystemExit(f"Input file not found: {input_path}")

	out_dir = Path(args.output_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	source_text = input_path.read_text(encoding="utf-8")
	section_label = _extract_section_label(source_text)
	entries = parse_entries(source_text)

	if not entries:
		print("No entries found (expected '## CODE Title' headers).")
		return 1

	created = 0
	skipped = 0
	source_rel = input_path.as_posix()

	for entry in entries:
		out_path = out_dir / f"{entry.code}.md"
		if out_path.exists() and not args.overwrite:
			skipped += 1
			continue
		out_path.write_text(
			render_entry_md(
				entry,
				section_label=section_label,
				source_rel=source_rel,
				linked_cpg=args.linked_cpg or None,
			),
			encoding="utf-8",
		)
		created += 1

	print(f"Wrote {created} ICD-11 entry files to {out_dir} (skipped {skipped}).")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())