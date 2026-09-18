"""Objective quality check for the large-cabinet output, via the sibling linter.

    uv run research/layout/deepdive-grid-astar-router/quality_report.py [n_branches]

Round 1's `grid-astar-router` verdict was based on a single hand-verified
route ("re-deriving the geometry by hand ... is not something a casual visual
read would necessarily have caught either"). That doesn't scale to a
100+-component cabinet. This script runs the sibling `svg-geometry-linter`
track's model-level linter (`research/layout/svg-geometry-linter/linter.py`,
which hit 0 false positives on real circuits in round 1) against this track's
own large-cabinet output, giving an objective defect count instead of an
eyeball impression -- this is the primary evidence in the deep-dive doc for
whether the router's output is actually good.

Not production code. Throwaway research spike, not imported by `src/schematika`.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "svg-geometry-linter"))

from large_cabinet import build_large_cabinet
from linter import lint_elements  # from the sibling svg-geometry-linter track
from route_all import route_all
from topology_bridge import derive_routing_input

OUTPUT_DIR = _HERE / "output"


def main() -> None:
    n_branches = int(sys.argv[1]) if len(sys.argv) > 1 else 16

    cabinet = build_large_cabinet(n_branches)
    routing_input = derive_routing_input(
        cabinet.result, extra_connections=cabinet.extra_connections
    )
    route_result = route_all(routing_input)
    elements = (
        list(cabinet.symbols) + list(cabinet.bus_elements) + list(route_result.wires)
    )

    report = lint_elements(elements)

    lines = [
        f"Large-cabinet geometry lint -- n_branches={n_branches}, "
        f"{cabinet.n_components} components, {len(route_result.wires)} wire segments",
        f"total findings: {len(report.findings)}   cost: {report.cost:.2f}",
    ]
    for kind, count in sorted(report.by_kind().items()):
        lines.append(f"  {kind}: {count}")
    lines.append("")
    for f in report.findings:
        lines.append(f"  [{f.severity}] {f.kind} @ {f.location}: {f.message}")

    text = "\n".join(lines)
    print(text)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"quality_report_{n_branches}branches.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
