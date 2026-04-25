"""Wave A1 audit: report docstring gaps on tier-1 public API symbols.

For each curated tier-1 package, walk `__all__` and check:
- Does every name resolve?
- Does every callable have a docstring?
- Does every callable have an `Examples` block (Google style or doctest)?
- Does every callable have `Args:` / `Returns:` sections matching its signature?

Always exits 0 in default mode — this is A1's *report* mode. A2 will gate
to --strict.

Usage:
    uv run python scripts/api_docs_audit.py             # human-readable report
    uv run python scripts/api_docs_audit.py --markdown  # write docs/api-audit/baseline.md
    uv run python scripts/api_docs_audit.py --strict    # exit 1 on any gap
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Order matches the tiered API proposal: top, then per-domain.
PACKAGES: tuple[str, ...] = (
    "schematika",
    "schematika.electrical",
    "schematika.electrical.symbols",
    "schematika.pid",
    "schematika.pid.symbols",
    "schematika.pcb",
    "schematika.cable",
    "schematika.catalog",
)


def _has_examples(doc: str) -> bool:
    """Google `Examples:` block or doctest `>>>` line."""
    return "Examples:" in doc or "Example:" in doc or ">>>" in doc


def _is_callable_symbol(obj: Any) -> bool:
    """A function / method / class — anything we'd document with Args/Returns."""
    return callable(obj) and not isinstance(obj, type(sys))  # exclude modules


def _audit_symbol(sym: str, obj: Any) -> list[str]:
    """Return human-readable issue strings for one public symbol."""
    issues: list[str] = []

    if obj is None:
        return [f"{sym}: in __all__ but not resolvable"]

    # Modules (e.g. `electrical.symbols`) — only check module docstring.
    if inspect.ismodule(obj):
        if not (inspect.getdoc(obj) or ""):
            issues.append(f"{sym}: submodule missing module docstring")
        return issues

    # Constants / values — skip per-symbol audit (their module docstring covers them).
    if not _is_callable_symbol(obj):
        return issues

    doc = inspect.getdoc(obj) or ""
    if not doc:
        return [f"{sym}: missing docstring"]

    if not _has_examples(doc):
        issues.append(f"{sym}: no Examples block")

    # Args / Returns checks only for functions / methods, not classes.
    if inspect.isclass(obj):
        return issues

    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return issues

    params = [
        n
        for n, p in sig.parameters.items()
        if n not in ("self", "cls")
        and p.kind is not inspect.Parameter.VAR_POSITIONAL
        and p.kind is not inspect.Parameter.VAR_KEYWORD
    ]
    if params and "Args:" not in doc:
        issues.append(f"{sym}: missing Args: section ({len(params)} params)")

    has_return = (
        sig.return_annotation is not inspect.Signature.empty
        and sig.return_annotation is not type(None)
    )
    if has_return and "Returns:" not in doc and "Yields:" not in doc:
        issues.append(f"{sym}: missing Returns: section")

    return issues


def audit_package(name: str) -> tuple[int, list[str]]:
    """Return (total_in_all, list_of_issue_strings)."""
    mod = importlib.import_module(name)
    public = getattr(mod, "__all__", None)
    if public is None:
        return 0, [f"<package>: {name} has no __all__"]

    issues: list[str] = []
    for sym in public:
        obj = getattr(mod, sym, None)
        issues.extend(_audit_symbol(sym, obj))
    return len(public), issues


def render_report(rows: list[tuple[str, int, list[str]]]) -> str:
    """Human-readable report (also used for --markdown output)."""
    lines: list[str] = []
    total_syms = 0
    total_issues = 0
    for name, count, issues in rows:
        total_syms += count
        total_issues += len(issues)
        status = "OK" if not issues else f"{len(issues)} gap(s)"
        lines.append(f"## {name} — {count} public symbols, {status}")
        lines.append("")
        if issues:
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")
        else:
            lines.append("_All tier-1 symbols pass docstring + Examples checks._")
            lines.append("")
    lines.insert(
        0, f"# API docstring audit — {total_issues} gap(s) across {total_syms} symbols"
    )
    lines.insert(1, "")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any gap.")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write docs/api-audit/baseline.md instead of stdout.",
    )
    args = parser.parse_args()

    rows: list[tuple[str, int, list[str]]] = []
    for pkg in PACKAGES:
        count, issues = audit_package(pkg)
        rows.append((pkg, count, issues))

    report = render_report(rows)

    if args.markdown:
        out = ROOT / "docs" / "api-audit" / "baseline.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT).as_posix()}")
    else:
        print(report)

    total_issues = sum(len(issues) for _, _, issues in rows)
    return 1 if (args.strict and total_issues) else 0


if __name__ == "__main__":
    sys.exit(main())
