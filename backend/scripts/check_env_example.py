"""Check that runtime environment variables are represented in `.env.example`."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable


PLATFORM_ALLOWLIST = {
    "CI", "HOME", "PATH", "PYTHONPATH", "TEMP", "TMP", "USERPROFILE",
    "AWS_EXECUTION_ENV", "AWS_LAMBDA_FUNCTION_NAME", "K_SERVICE", "PORT",
}


def _string_arg(call: ast.Call) -> str | None:
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    value = call.args[0].value
    return value if isinstance(value, str) else None


def discover_env_names(paths: Iterable[Path]) -> set[str]:
    names: set[str] = set()
    for path in paths:
        candidates = path.rglob("*.py") if path.is_dir() else [path]
        for candidate in candidates:
            try:
                tree = ast.parse(candidate.read_text(encoding="utf-8"), filename=str(candidate))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                name = _string_arg(node)
                if not name:
                    continue
                func = node.func
                if (
                    func.attr == "getenv"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "os"
                ) or (
                    func.attr == "get"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "environ"
                    and isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "os"
                ):
                    names.add(name)
    return names


def documented_env_names(example_text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s*([A-Z][A-Z0-9_]*)\s*=", example_text))


def missing_env_names(
    paths: Iterable[Path], documented: set[str], *, allowlist: set[str] | None = None
) -> list[str]:
    allowed = PLATFORM_ALLOWLIST if allowlist is None else allowlist
    return sorted(discover_env_names(paths) - documented - allowed)


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    sources = [project_root / "backend" / name for name in ("agent", "ingestion", "scripts")]
    example = project_root / ".env.example"
    documented = documented_env_names(example.read_text(encoding="utf-8"))
    missing = missing_env_names(sources, documented)
    if missing:
        print("Undocumented runtime environment variables:")
        for name in missing:
            print(name)
        return 1
    print(f"Environment inventory synchronized ({len(documented)} documented variables).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
