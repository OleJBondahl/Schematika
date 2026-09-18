"""Runnable entry point for the round-2 grid-astar-router deep dive.

    uv run research/layout/deepdive-grid-astar-router/build_demo.py [n_branches]

Builds the large synthetic cabinet (`large_cabinet.build_large_cabinet`),
derives the router's input from its real `BuildResult` (`topology_bridge`),
routes every pair (`route_all`), renders the result with Schematika's real
SVG renderer, and prints the stats used in the deep-dive doc.

Default `n_branches=16` (97 components) -- see `scale_benchmark.py` for the
14/50/100/150-component timing sweep.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from large_cabinet import build_large_cabinet
from route_all import route_all
from topology_bridge import derive_routing_input

from schematika.rendering.svg import render_to_svg

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    n_branches = int(sys.argv[1]) if len(sys.argv) > 1 else 16

    t0 = time.perf_counter()
    cabinet = build_large_cabinet(n_branches)
    t_build = time.perf_counter()

    routing_input = derive_routing_input(
        cabinet.result, extra_connections=cabinet.extra_connections
    )
    t_bridge = time.perf_counter()

    route_result = route_all(routing_input)
    t_route = time.perf_counter()

    elements = (
        list(cabinet.symbols) + list(cabinet.bus_elements) + list(route_result.wires)
    )

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"large_cabinet_{n_branches}branches.svg"
    render_to_svg(elements, str(out_path), width="auto", height="auto")
    t_render = time.perf_counter()

    print(f"n_branches: {n_branches}")
    print(f"components placed: {cabinet.n_components}")
    print(f"route pairs derived: {len(routing_input.pairs)}")
    print(
        f"unresolved connections: {len(routing_input.unresolved)}  {routing_input.unresolved}"
    )
    print(f"heuristic-dependent pairs: {routing_input.heuristic_fraction:.0%}")
    print(f"routing fallbacks (no A* path found): {len(route_result.fallback_pairs)}")
    print(f"total wire segments drawn: {len(route_result.wires)}")
    print(f"grid cells consumed across all routes: {route_result.used_cell_count}")
    print()
    print(f"build (CircuitBuilder):     {(t_build - t0) * 1000:8.2f} ms")
    print(f"bridge (derive_routing_input): {(t_bridge - t_build) * 1000:8.2f} ms")
    print(f"route (route_all):          {(t_route - t_bridge) * 1000:8.2f} ms")
    print(f"render (render_to_svg):     {(t_render - t_route) * 1000:8.2f} ms")
    print(f"TOTAL:                      {(t_render - t0) * 1000:8.2f} ms")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
