"""Runnable entry point for the grid-astar-router spike.

    uv run python research/layout/grid-astar-router/build_demo.py

Builds the synthetic cabinet ladder (synthetic_circuit.build_ladder),
renders it with Schematika's real SVG renderer (schematika.rendering.svg),
and prints a few stats used in the findings doc.
"""

import sys
import time
from pathlib import Path

# Make the prototype importable when run as a script (not an installed package).
sys.path.insert(0, str(Path(__file__).parent))

from synthetic_circuit import build_ladder

from schematika.rendering.svg import render_to_svg

OUTPUT_PATH = Path(__file__).parent / "output" / "cabinet_ladder.svg"


def main() -> None:
    t0 = time.perf_counter()
    result = build_ladder()
    elapsed = time.perf_counter() - t0

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    render_to_svg(result.elements, str(OUTPUT_PATH), width="auto", height="auto")

    print(f"Placed {len(result.placed_symbols)} symbols")
    print(f"Total drawable elements: {len(result.elements)}")
    print(f"A* route K1_aux -> Q1: {len(result.routed_wire_points)} points ->")
    for p in result.routed_wire_points:
        print(f"    ({p.x:.1f}, {p.y:.1f})")
    print(f"A* route K1_aux -> Q2: {len(result.route_to_q2_points)} points ->")
    for p in result.route_to_q2_points:
        print(f"    ({p.x:.1f}, {p.y:.1f})")
    print(f"A* grid cells consumed by both routed wires: {result.astar_cells_explored}")
    print(f"Build + route time: {elapsed * 1000:.2f} ms")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
