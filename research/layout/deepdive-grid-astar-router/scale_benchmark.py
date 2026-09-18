"""Wall-clock scaling sweep for the round-2 grid-astar-router pipeline.

    uv run research/layout/deepdive-grid-astar-router/scale_benchmark.py

Round 1 measured one data point (14 components, 2 routes, 33ms) and flagged
performance as untested at real-cabinet scale, since search cost is
`O(routes x grid_cells)` and grid cell count scales with page *area*, not
component count. This runs the full build -> bridge -> route pipeline at
n_branches = 2, 8, 16, 25 (component counts 14, 50, 98, 152 -- the
`2 + 6*n_branches` formula from `large_cabinet.py`, landing close to the
requested 14/50/100/150 checkpoints) and reports each phase separately, plus
the actual, not asymptotic, degradation between checkpoints.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from large_cabinet import build_large_cabinet
from route_all import route_all
from topology_bridge import derive_routing_input

BRANCH_COUNTS = (2, 8, 16, 25)


def main() -> None:
    print(
        f"{'n_branches':>10} {'components':>10} {'pairs':>6} {'build_ms':>9} {'bridge_ms':>10} {'route_ms':>9} {'total_ms':>9} {'ms/pair':>8}"
    )
    for n in BRANCH_COUNTS:
        t0 = time.perf_counter()
        cabinet = build_large_cabinet(n)
        t_build = time.perf_counter()

        routing_input = derive_routing_input(
            cabinet.result, extra_connections=cabinet.extra_connections
        )
        t_bridge = time.perf_counter()

        route_result = route_all(routing_input)
        t_route = time.perf_counter()

        n_pairs = len(routing_input.pairs)
        build_ms = (t_build - t0) * 1000
        bridge_ms = (t_bridge - t_build) * 1000
        route_ms = (t_route - t_bridge) * 1000
        total_ms = (t_route - t0) * 1000
        ms_per_pair = route_ms / n_pairs if n_pairs else 0.0

        print(
            f"{n:>10} {cabinet.n_components:>10} {n_pairs:>6} "
            f"{build_ms:>9.1f} {bridge_ms:>10.2f} {route_ms:>9.1f} {total_ms:>9.1f} {ms_per_pair:>8.2f}"
        )
        if route_result.fallback_pairs:
            print(f"    fallbacks: {route_result.fallback_pairs}")
        if routing_input.unresolved:
            print(f"    unresolved: {routing_input.unresolved}")


if __name__ == "__main__":
    main()
