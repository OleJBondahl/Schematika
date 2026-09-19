"""Wall-clock scaling sweep for `electrical.layout.router.route_wires`.

    uv run python scripts/benchmark_router.py

Reproduces the round-2 grid-astar-router spike's benchmark
(`research/layout/deepdive-grid-astar-router/scale_benchmark.py`) against the
production module, at the same four scales (14/50/98/152 components), to
show the effect of bounding each route's A* search to a padded box around
its own (start, end) span instead of the whole page.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    PlacementOptions,
    SymbolConfig,
)
from schematika.electrical import CircuitBuilder, create_initial_state
from schematika.electrical.layout.router import (
    RouterConfig,
    all_symbols_bounds,
    derive_routing_input,
    obstacles_excluding,
    polyline_to_wires,
    rasterize_obstacles,
    route_wires,
    route_with_fallback,
)
from schematika.electrical.model.constants import CIRCUIT_SPACING, SPACING_STANDARD
from schematika.electrical.symbols import contactor, estop, fuse, motor

if TYPE_CHECKING:
    from schematika.electrical.builder_models import BuildResult

BRANCH_COUNTS = (2, 8, 16, 25)
CONTACTOR_Y = 2 * SPACING_STANDARD


@dataclass(frozen=True)
class _Cabinet:
    result: BuildResult
    extra_connections: list[tuple[str, str, str, str]]
    n_components: int


def build_cabinet(n_branches: int) -> _Cabinet:
    """An n_branches-branch cabinet (6*n_branches + 2 components) via CircuitBuilder."""
    state = create_initial_state()

    main_cb = CircuitBuilder(state=state)
    main_cb.set_layout(x=0, y=0)
    s0_ref = main_cb.add_symbol(
        estop,
        config=SymbolConfig(tag_prefix="S"),
        connection=ConnectionOptions(connect_to_next=False),
    )
    prev = s0_ref
    for _ in range(n_branches):
        prev = main_cb.add_symbol(
            fuse,
            config=SymbolConfig(tag_prefix="F"),
            placement=PlacementOptions(
                relative_to=prev, position="right", x_offset=CIRCUIT_SPACING
            ),
            connection=ConnectionOptions(
                connect_from_previous=False, connect_to_next=False
            ),
        )
    main_cb.add_terminal(
        "N1",
        placement=PlacementOptions(
            relative_to=prev, position="right", x_offset=CIRCUIT_SPACING
        ),
        connection=ConnectionOptions(
            connect_from_previous=False, connect_to_next=False
        ),
    )
    main_result = main_cb.build(options=BuildOptions(state=state))
    state = main_result.state

    fuse_tags = main_result.component_tags("F")
    s0_tag = main_result.component_tag("S")

    branch_builders: list[CircuitBuilder] = []
    extra_connections: list[tuple[str, str, str, str]] = []
    for i, f_tag in enumerate(fuse_tags):
        branch_cb = CircuitBuilder(state=state)
        branch_cb.set_layout(x=i * CIRCUIT_SPACING, y=CONTACTOR_Y)
        branch_cb.add_symbol(
            contactor,
            config=SymbolConfig(
                tag_prefix="K", poles=3, factory_kwargs={"coil_pins": ("A1", "A2")}
            ),
            connection=ConnectionOptions(connect_from_previous=False),
        )
        branch_cb.add_symbol(
            motor,
            config=SymbolConfig(tag_prefix="M", poles=3, factory_kwargs={"poles": 3}),
        )
        branch_result = branch_cb.build(options=BuildOptions(state=state))
        state = branch_result.state
        branch_builders.append(branch_cb)

        k_tag = branch_result.component_tag("K")
        extra_connections.append((f_tag, "2", k_tag, "L1"))
        extra_connections.append((s0_tag, "2", k_tag, "A1"))
        extra_connections.append((k_tag, "A2", "N1", "1"))

    term_cb = CircuitBuilder(state=state)
    term_cb.set_layout(x=0, y=6 * SPACING_STANDARD)
    prev_term = None
    for i in range(3 * n_branches):
        placement = (
            None
            if prev_term is None
            else PlacementOptions(
                relative_to=prev_term, position="right", x_offset=CIRCUIT_SPACING / 3
            )
        )
        connection = ConnectionOptions(
            connect_from_previous=False, connect_to_next=False
        )
        prev_term = term_cb.add_terminal(
            f"X{i + 1}", placement=placement, connection=connection
        )
    term_cb.build(options=BuildOptions(state=state))

    merged = CircuitBuilder.merge(main_cb, *branch_builders, term_cb)
    n_components = 2 + 6 * n_branches
    return _Cabinet(
        result=merged.result,
        extra_connections=extra_connections,
        n_components=n_components,
    )


def route_all_scoped(cabinet: _Cabinet, cfg: RouterConfig) -> int:
    """Route via the production entry point (each search scoped to its own span)."""
    layout = route_wires(
        cabinet.result, extra_connections=cabinet.extra_connections, config=cfg
    )
    return len(layout.fallback_pairs)


def route_all_whole_page(cabinet: _Cabinet, cfg: RouterConfig) -> int:
    """Route every pair against the *whole page* bounds (pre-fix baseline)."""
    routing_input = derive_routing_input(
        cabinet.result, extra_connections=cabinet.extra_connections
    )
    page_bounds = all_symbols_bounds(routing_input.all_symbols)
    used_cells: frozenset = frozenset()
    fallbacks = 0
    for pair in routing_input.pairs:
        obstacles = obstacles_excluding(
            routing_input.all_symbols, {id(pair.from_symbol), id(pair.to_symbol)}
        )
        blocked = rasterize_obstacles(obstacles, cfg)
        polyline, used_cells, used_fallback = route_with_fallback(
            pair.from_point,
            pair.to_point,
            blocked=blocked,
            used_cells=used_cells,
            bounds=page_bounds,
            config=cfg,
        )
        fallbacks += used_fallback
        polyline_to_wires(polyline)
    return fallbacks


def _bench(label: str, route_fn) -> None:
    cfg = RouterConfig()
    print(f"-- {label} --")
    print(
        f"{'n_branches':>10} {'components':>10} {'pairs':>6} {'route_ms':>9} {'ms/pair':>8} {'fallbacks':>9}"
    )
    for n in BRANCH_COUNTS:
        cabinet = build_cabinet(n)
        n_pairs = len(
            derive_routing_input(
                cabinet.result, extra_connections=cabinet.extra_connections
            ).pairs
        )
        t0 = time.perf_counter()
        fallbacks = route_fn(cabinet, cfg)
        route_ms = (time.perf_counter() - t0) * 1000
        ms_per_pair = route_ms / n_pairs if n_pairs else 0.0
        print(
            f"{n:>10} {cabinet.n_components:>10} {n_pairs:>6} "
            f"{route_ms:>9.1f} {ms_per_pair:>8.2f} {fallbacks:>9}"
        )


def main() -> None:
    _bench("whole-page search bounds (pre-fix baseline)", route_all_whole_page)
    print()
    _bench("bbox-scoped search bounds (production route_wires)", route_all_scoped)


if __name__ == "__main__":
    main()
