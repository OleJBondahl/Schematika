"""Advisory gate: flag top-level functions in core/ missing @pure.

Walks every `.py` under `src/schematika/core/` and checks each module-level
`def`/`async def` for a `@pure` decorator (whether via `from schematika._purity
import pure; @pure` or `@deal.pure`). Reports missing decorators.

Default behaviour: report-only (exit 0) — the baseline is expected to be
~100% missing until the purity-rollout PR lands. Use `--strict` to exit 1 on
any missing decorator (useful once rollout starts).

Usage:
    uv run python scripts/fp_purity_gate.py            # report, exit 0
    uv run python scripts/fp_purity_gate.py --strict   # enforce
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT / "src" / "schematika" / "core"


def _decorator_name(dec: ast.expr) -> str:
    """Render a decorator AST node as a dotted name, best-effort."""
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        base = _decorator_name(dec.value)
        return f"{base}.{dec.attr}"
    if isinstance(dec, ast.Call):
        return _decorator_name(dec.func)
    return "<expr>"


def _is_pure(dec_names: list[str]) -> bool:
    """True if any decorator is @pure or @deal.pure."""
    return any(n in ("pure", "deal.pure") for n in dec_names)


def scan(path: Path) -> list[tuple[Path, int, str]]:
    """Return list of (file, lineno, func_name) for top-level funcs missing @pure."""
    missing: list[tuple[Path, int, str]] = []
    for py in sorted(path.rglob("*.py")):
        if py.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                decs = [_decorator_name(d) for d in node.decorator_list]
                if not _is_pure(decs):
                    missing.append((py, node.lineno, node.name))
    return missing


def main() -> int:
    """Report or enforce @pure on core/ module-level functions."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any core/ module-level def lacks @pure.",
    )
    args = p.parse_args()

    if not CORE_DIR.is_dir():
        print(f"skip: {CORE_DIR} not found", file=sys.stderr)
        return 0

    missing = scan(CORE_DIR)
    if not missing:
        print("fp-purity-gate: all core/ module-level functions decorated with @pure.")
        return 0

    print(f"fp-purity-gate: {len(missing)} function(s) in core/ missing @pure:")
    for path, lineno, name in missing:
        rel = path.relative_to(ROOT).as_posix()
        print(f"  {rel}:{lineno} {name}")

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
