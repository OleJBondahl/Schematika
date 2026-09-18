"""Route every RoutePair in a RoutingInput, threading router state functionally.

Deliberately does NOT use the stateful `OrthogonalRouter` class for the main
pipeline. Building the large cabinet exposed a real limitation of that class:
its obstacle set is fixed at construction, but a router integrated with real
topology needs a *different* obstacle set per route (every route must exclude
its own two endpoint symbols, which differ per route -- see
`topology_bridge.obstacles_excluding`). Reusing one `OrthogonalRouter`
instance across routes with varying obstacles isn't possible; reconstructing
it per route would still need the previous route's `_used_cells` re-plumbed
in by hand, which is exactly what `route_pure`'s explicit `used_cells`
argument already does, with less ceremony. See the deep-dive doc's
mutable-state section for the full argument.

Not production code. Throwaway research spike, not imported by `src/schematika`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from router_core import (
    RouterConfig,
    RoutingError,
    polyline_to_wires,
    rasterize_obstacles,
    route_pure,
)
from topology_bridge import RoutingInput, all_symbols_bounds, obstacles_excluding

from schematika.core.geometry import Point
from schematika.core.primitives import Line


@dataclass(frozen=True)
class RouteAllResult:
    """Every routed wire, plus how many routes needed the no-path fallback."""

    wires: list[Line]
    fallback_pairs: list[tuple[str, str]] = field(default_factory=list)
    used_cell_count: int = 0


def route_all(
    routing_input: RoutingInput, config: RouterConfig | None = None
) -> RouteAllResult:
    """Route every pair in `routing_input.pairs`, in order, sharing crossing-penalty state.

    Args:
        routing_input: Output of `topology_bridge.derive_routing_input`.
        config: Router cost-model tunables. `None` uses `RouterConfig()` defaults.

    Returns:
        `RouteAllResult` with one `Line` chain per pair (routed if possible,
        a straight 1-turn fallback jog otherwise) and the list of
        `(from_tag, to_tag)` pairs that needed the fallback.
    """
    cfg = config or RouterConfig()
    bounds = all_symbols_bounds(routing_input.symbols)
    used_cells: frozenset = frozenset()
    wires: list[Line] = []
    fallback_pairs: list[tuple[str, str]] = []

    for pair in routing_input.pairs:
        obstacles = obstacles_excluding(
            routing_input.symbols, {pair.from_tag, pair.to_tag}
        )
        blocked = rasterize_obstacles(obstacles, cfg)
        try:
            polyline, used_cells = route_pure(
                pair.from_point,
                pair.to_point,
                blocked=blocked,
                used_cells=used_cells,
                bounds=bounds,
                config=cfg,
            )
        except RoutingError:
            fallback_pairs.append((pair.from_tag, pair.to_tag))
            mid = Point(pair.from_point.x, pair.to_point.y)
            polyline = [pair.from_point, mid, pair.to_point]
        wires.extend(polyline_to_wires(polyline))

    return RouteAllResult(
        wires=wires, fallback_pairs=fallback_pairs, used_cell_count=len(used_cells)
    )
