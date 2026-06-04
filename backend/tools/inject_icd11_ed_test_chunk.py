"""Inject ICD-11 metadata into Erectile Dysfunction test-chunk markdown files.

Edits ONLY:
    test-chunk/Erectile-Dysfunction/*.md

For every <!-- METADATA ... --> block found, it ensures the following keys exist:
    icd11_primary
    icd11_related

Optionally, icd11_related can be constructed from an ICD-11 source markdown file
(e.g. ddx/data/ha00_sexual_dysfunctions.md) so the section metadata carries the
complete context code list.

This keeps existing formatting and does not touch the canonical markdown/ folder.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class IcdConfig:
    primary: str
    related: str  # comma-separated string to match existing metadata style


HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
CODE_RE = re.compile(r"^(?P<code>[A-Z]{2}[0-9A-Z.]+)\b")


START = "<!-- METADATA"
END = "-->"


def _set_or_insert_key(
    block_lines: list[str],
    *,
    key: str,
    value: str,
    insert_at: int,
    force_update: bool,
) -> tuple[list[str], bool]:
    changed = False
    prefix = f"{key}:"
    for i, line in enumerate(block_lines):
        if line.strip().startswith(prefix):
            if force_update:
                new_line = f"{key}: {value}"
                if block_lines[i] != new_line:
                    block_lines = block_lines[:i] + [new_line] + block_lines[i + 1 :]
                    changed = True
            return block_lines, changed

    # Not found: insert
    block_lines = block_lines[:insert_at] + [f"{key}: {value}"] + block_lines[insert_at:]
    return block_lines, True


def _inject_into_block(block_lines: list[str], cfg: IcdConfig, *, force_update: bool) -> tuple[list[str], bool]:
    """Return (new_lines, changed). block_lines includes START..END."""
    changed_any = False

    # Choose insertion point:
    # - Prefer after 'category:' line (common convention)
    # - Else after 'parent_section:'
    # - Else right before END
    insert_at = None
    for i, line in enumerate(block_lines):
        if line.strip().startswith("category:"):
            insert_at = i + 1
            break
    if insert_at is None:
        for i, line in enumerate(block_lines):
            if line.strip().startswith("parent_section:"):
                insert_at = i + 1
                break
    if insert_at is None:
        # Insert before END
        for i, line in enumerate(block_lines):
            if line.strip() == END:
                insert_at = i
                break
    if insert_at is None:
        # Malformed block; do nothing
        return block_lines, False

    block_lines, changed = _set_or_insert_key(
        block_lines,
        key="icd11_primary",
        value=cfg.primary,
        insert_at=insert_at,
        force_update=force_update,
    )
    changed_any = changed_any or changed

    # If primary was inserted, related should come after it for readability.
    # If primary already existed, we still insert related at the same anchor.
    related_insert_at = insert_at
    for i, line in enumerate(block_lines):
        if line.strip().startswith("icd11_primary:"):
            related_insert_at = i + 1
            break

    block_lines, changed = _set_or_insert_key(
        block_lines,
        key="icd11_related",
        value=cfg.related,
        insert_at=related_insert_at,
        force_update=force_update,
    )
    changed_any = changed_any or changed

    return block_lines, changed_any


def inject_into_text(text: str, cfg: IcdConfig, *, force_update: bool) -> tuple[str, int]:
    """Inject into all metadata blocks. Returns (new_text, blocks_changed)."""
    lines = text.splitlines()
    out: list[str] = []

    i = 0
    changed_blocks = 0

    while i < len(lines):
        line = lines[i]
        if line.strip() == START:
            block = [line]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                if lines[i].strip() == END:
                    break
                i += 1

            new_block, changed = _inject_into_block(block, cfg, force_update=force_update)
            if changed:
                changed_blocks += 1
            out.extend(new_block)
            i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), changed_blocks


def build_related_from_source(source_path: Path) -> str:
    """Extract all codes from an ICD-11 source markdown with '## CODE Title' headers."""
    text = source_path.read_text(encoding="utf-8")
    codes: list[str] = []
    for header in HEADER_RE.findall(text):
        m = CODE_RE.match(header.strip())
        if m:
            codes.append(m.group("code"))
    # De-dup while preserving order
    seen: set[str] = set()
    ordered = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ", ".join(ordered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject ICD-11 metadata into ED test-chunk markdown")
    parser.add_argument(
        "--folder",
        default="test-chunk/Erectile-Dysfunction",
        help="Folder containing ED test-chunk markdown files",
    )
    parser.add_argument(
        "--primary",
        default="HA01.1",
        help="Primary ICD-11 code for Erectile Dysfunction",
    )
    parser.add_argument(
        "--related",
        default="HA01.10, HA01.11, HA01.12, HA01.13, HA01.1Z",
        help="Comma-separated related ICD-11 codes",
    )
    parser.add_argument(
        "--related-from",
        default="",
        help="Optional ICD-11 source markdown file; if set, builds icd11_related from all entries in that file",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="If set, updates existing icd11_primary/icd11_related lines (not just inserts when missing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )

    args = parser.parse_args()
    related = args.related
    if args.related_from:
        src = Path(args.related_from)
        if not src.exists():
            raise SystemExit(f"related-from file not found: {src}")
        related = build_related_from_source(src)

    cfg = IcdConfig(primary=args.primary, related=related)

    folder = Path(args.folder)
    if not folder.exists():
        raise SystemExit(f"Folder not found: {folder}")

    md_files = sorted(folder.glob("*.md"))
    if not md_files:
        print(f"No markdown files found in {folder}")
        return 1

    total_blocks_changed = 0
    files_changed = 0

    for path in md_files:
        original = path.read_text(encoding="utf-8")
        updated, blocks_changed = inject_into_text(original, cfg, force_update=args.force_update)
        if blocks_changed:
            files_changed += 1
            total_blocks_changed += blocks_changed
            if not args.dry_run:
                path.write_text(updated, encoding="utf-8")

    mode = "DRY RUN" if args.dry_run else "UPDATED"
    print(f"{mode}: {files_changed}/{len(md_files)} files changed; {total_blocks_changed} metadata blocks updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
