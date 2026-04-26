#!/usr/bin/env python3
"""CLI entry point for ``schematika.overview`` Tier-1 SVG validation.

Usage:
    uv run python scripts/system_diagram_review.py <svg_path>

Exit codes: 0 PASS, 2 structural FAIL, 4 render error (missing/malformed SVG).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from schematika.overview.validate import validate_svg

from _render import svg_to_png

EXIT_PASS = 0
EXIT_FAIL_STRUCTURAL = 2
EXIT_FAIL_RENDER = 4

_PNG_HASH_PREFIX = 8


def _structural_only(errors: list[str]) -> bool:
    """True iff every error line is a structural ``[FAIL ...]`` finding."""
    return all(e.startswith("[FAIL ") for e in errors)


def _print_findings(findings: list[str]) -> None:
    for line in findings:
        print(line)


def _render_png(svg_path: Path) -> tuple[Path, str] | tuple[None, str]:
    """Render SVG to PNG and return ``(png_path, sha8)`` or ``(None, reason)``."""
    try:
        png_str = svg_to_png(str(svg_path))
    except (ImportError, OSError) as exc:
        return None, f"renderer unavailable: {exc}"
    png = Path(png_str)
    digest = hashlib.sha256(png.read_bytes()).hexdigest()[:_PNG_HASH_PREFIX]
    return png, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg_path", help="path to the system overview SVG")
    args = parser.parse_args()

    svg_path = Path(args.svg_path)
    result = validate_svg(svg_path)

    _print_findings(result.warnings)

    if result.passed:
        verdict, exit_code = "PASS", EXIT_PASS
    elif _structural_only(result.errors):
        verdict, exit_code = "FAIL", EXIT_FAIL_STRUCTURAL
    else:
        # Surface render-side errors that aren't structural [FAIL ...] lines.
        for line in result.errors:
            if not line.startswith("[FAIL "):
                print(line)
        verdict, exit_code = "FAIL", EXIT_FAIL_RENDER

    print(f"RESULT: {verdict}")
    print(f"SVG:    {svg_path}")

    if exit_code == EXIT_FAIL_RENDER and not svg_path.exists():
        # No point trying to render a missing file.
        print("PNG:    <not rendered: svg path does not exist>")
        return exit_code

    png, info = _render_png(svg_path)
    if png is None:
        print(f"PNG:    <not rendered: {info}>")
    else:
        print(f"PNG:    {png}  (sha256 {info})")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
