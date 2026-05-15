"""Remove bold (**...**) formatting from the first column of markdown tables.

Usage:
    python remove_bold_first_col.py <file_or_directory> [--dry-run]

If a directory is given, all .md files within it are processed recursively.
"""

import argparse
import re
import sys
from pathlib import Path

# Matches a markdown table row starting with: | **value** |
FIRST_COL_BOLD = re.compile(r'^\|\s*\*\*([^|*\n]+?)\*\*\s*\|', re.MULTILINE)

# Matches bracketed bold tags anywhere in the text, e.g.:
#   **[Grade I, Level A]**, **[Grade I]**, **[Level B]**, **[Class IIa]**
# Only unwraps if the bracket content starts with Grade/Level/Class (case-insensitive).
BRACKET_BOLD = re.compile(
    r'\*\*(\[\s*(?:Grade|Level|Class)\b[^\]\n]*\])\*\*',
    re.IGNORECASE,
)


def strip_bold_first_column(text: str) -> tuple[str, int]:
    text, n1 = FIRST_COL_BOLD.subn(r'| \1 |', text)
    text, n2 = BRACKET_BOLD.subn(r'\1', text)
    return text, n1 + n2


def process_file(path: Path, dry_run: bool) -> int:
    original = path.read_text(encoding='utf-8')
    updated, count = strip_bold_first_column(original)
    if count == 0:
        print(f"  (no changes) {path}")
        return 0
    if dry_run:
        print(f"  [dry-run] would update {count} row(s) in {path}")
    else:
        path.write_text(updated, encoding='utf-8')
        print(f"  updated {count} row(s) in {path}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', help='Markdown file or directory to process')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"error: path not found: {target}", file=sys.stderr)
        return 1

    files = [target] if target.is_file() else sorted(target.rglob('*.md'))
    if not files:
        print("No .md files found.")
        return 0

    total = sum(process_file(f, args.dry_run) for f in files)
    print(f"\nDone. {total} row(s) {'would be ' if args.dry_run else ''}updated across {len(files)} file(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
