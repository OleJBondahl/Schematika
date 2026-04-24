"""Advisory gate: enforce Schematika API style rules on src/schematika/**.

Rules (see CODEBASE_AUDIT.md §5.2, future docs/API_STYLE.md):

1. Public `add_*` / `set_*` methods in `**/builder.py` must have exactly one
   positional-only arg (after `self`) before the `*` keyword-only marker.
2. Public methods named `build` must have a non-`None` return annotation.
3. Public functions taking both `x: float` and `y: float` positionally must
   also accept `position: Point` (or the scalars should be migrated).
4. Public functions that mix `label: str`, `name: str`, `tag: str` get a
   glossary warning — per the glossary, pick one.

Default: report-only (exit 0). Use `--strict` to enforce (exit 1).

Usage:
    uv run python scripts/api_style_gate.py
    uv run python scripts/api_style_gate.py --strict
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src" / "schematika"


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _annotation_src(node: ast.expr | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _has_none_return(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    ret = fn.returns
    if ret is None:
        return True
    src = _annotation_src(ret)
    return src in ("None", "typing.None")


def _param_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = fn.args
    out: list[str] = []
    out.extend(a.arg for a in args.posonlyargs)
    out.extend(a.arg for a in args.args)
    out.extend(a.arg for a in args.kwonlyargs)
    return out


def _param_ann(fn: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> str | None:
    args = fn.args
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        for a in group:
            if a.arg == name:
                return _annotation_src(a.annotation)
    return None


def _applies_add_set(fn: ast.FunctionDef | ast.AsyncFunctionDef, file: Path) -> bool:
    return (
        file.name == "builder.py"
        and _is_public(fn.name)
        and fn.name.startswith(("add_", "set_"))
    )


def check_add_set_positional(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, file: Path
) -> list[str]:
    """Rule 1: add_*/set_* should have exactly one positional-only arg."""
    if not _applies_add_set(fn, file):
        return []
    pos_only = [a for a in fn.args.posonlyargs if a.arg not in ("self", "cls")]
    pos_or_kw = [a for a in fn.args.args if a.arg not in ("self", "cls")]
    if pos_only and len(pos_only) != 1:
        return [f"{fn.name}: {len(pos_only)} positional-only args (expected exactly 1)"]
    if not pos_only and pos_or_kw:
        return [
            f"{fn.name}: missing `/` positional-only marker "
            f"(has {len(pos_or_kw)} positional-or-keyword args)"
        ]
    return []


def check_build_return(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, file: Path
) -> list[str]:
    """Rule 2: build() must have a non-None return annotation."""
    if fn.name != "build" or not _is_public(fn.name):
        return []
    if _has_none_return(fn):
        return [f"{fn.name}: returns None (expected a *BuildResult dataclass)"]
    return []


def check_xy_without_point(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, _file: Path
) -> list[str]:
    """Rule 3: x: float, y: float without position: Point."""
    if not _is_public(fn.name):
        return []
    names = _param_names(fn)
    if "x" in names and "y" in names:
        x_ann = _param_ann(fn, "x") or ""
        y_ann = _param_ann(fn, "y") or ""
        if "float" in x_ann and "float" in y_ann and "position" not in names:
            return [f"{fn.name}: takes x,y scalars but no position: Point alternative"]
    return []


def check_label_name_tag(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, _file: Path
) -> list[str]:
    """Rule 4: label + name + tag all in one signature — pick one (glossary)."""
    if not _is_public(fn.name):
        return []
    names = set(_param_names(fn))
    overlap = names & {"label", "name", "tag"}
    if len(overlap) >= 3:
        return [
            f"{fn.name}: takes {sorted(overlap)} together — "
            f"glossary says pick one (label=rendered, name=key, tag=autonumbered)"
        ]
    return []


CHECKS = (
    check_add_set_positional,
    check_build_return,
    check_xy_without_point,
    check_label_name_tag,
)


def scan(path: Path) -> list[tuple[Path, int, str]]:
    """Walk src/schematika/ and return (file, lineno, message) for violations."""
    violations: list[tuple[Path, int, str]] = []
    for py in sorted(path.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for check in CHECKS:
                    for msg in check(node, py):
                        violations.append((py, node.lineno, msg))
    return violations


def main() -> int:
    """Report or enforce API-style rules."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strict", action="store_true", help="Exit 1 on any violation.")
    args = p.parse_args()

    if not SRC_DIR.is_dir():
        print(f"skip: {SRC_DIR} not found", file=sys.stderr)
        return 0

    violations = scan(SRC_DIR)
    if not violations:
        print("api-style-gate: no violations.")
        return 0

    print(f"api-style-gate: {len(violations)} violation(s):")
    for path, lineno, msg in violations:
        rel = path.relative_to(ROOT).as_posix()
        print(f"  {rel}:{lineno} {msg}")

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
