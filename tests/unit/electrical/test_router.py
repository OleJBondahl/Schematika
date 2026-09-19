"""Tests for `electrical.layout.router` and `electrical.layout.pin_resolver`."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

import pytest

from schematika.core.bbox import BoundingBox
from schematika.core.geometry import Point
from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    PlacementOptions,
    SymbolConfig,
)
from schematika.electrical import (
    Circuit,
    CircuitBuilder,
    create_initial_state,
    render_system,
)
from schematika.electrical.layout.pin_resolver import build_pin_resolver
from schematika.electrical.layout.router import (
    RouterConfig,
    RoutingError,
    _obstacles_in_bounds,
    _scoped_route_bounds,
    all_symbols_bounds,
    derive_routing_input,
    obstacles_excluding,
    polyline_to_wires,
    rasterize_obstacles,
    route_pure,
    route_wires,
    route_with_fallback,
)
from schematika.electrical.model.constants import CIRCUIT_SPACING
from schematika.electrical.symbols import coil, contactor, estop, fuse, motor, ref

if TYPE_CHECKING:
    from schematika.electrical.builder_models import BuildResult


def _is_orthogonal(points: list[Point]) -> bool:
    return all(
        abs(a.x - b.x) < 1e-9 or abs(a.y - b.y) < 1e-9 for a, b in pairwise(points)
    )


# ---------------------------------------------------------------------------
# pin_resolver
# ---------------------------------------------------------------------------


def test_pin_resolver_exact_match_for_literal_port_id():
    f1 = fuse(label="F1")
    resolved, kind = build_pin_resolver(
        [f1], [("F1", "1", "source"), ("F1", "2", "target")]
    )
    assert resolved[("F1", "1", "source")] == "1"
    assert resolved[("F1", "2", "target")] == "2"
    assert kind[("F1", "1", "source")] == "exact"


def test_pin_resolver_heuristic_fallback_for_non_literal_label():
    k1 = contactor(label="K1")  # real ports: 1..6, no coil
    resolved, kind = build_pin_resolver([k1], [("K1", "L1", "source")])
    assert resolved[("K1", "L1", "source")] in k1.ports
    assert kind[("K1", "L1", "source")] == "heuristic"


def test_pin_resolver_exact_match_removes_coil_return_from_heuristic_pool():
    """Regression: a lazy order-only pool once assigned a power-contact query
    to the coil's A2 return, because A2 sorted left of the contact block in
    the unfiltered down-facing pool. Claiming A2 by exact match first (it IS
    a real port id) must remove it before any heuristic query runs.
    """
    k1 = contactor(label="K1", coil_pins=("A1", "A2"))
    queries = [
        ("K1", "A2", "target"),  # exact: coil return, wired first
        ("K1", "L1", "source"),  # heuristic: a power contact
    ]
    resolved, kind = build_pin_resolver([k1], queries)
    assert resolved[("K1", "A2", "target")] == "A2"
    assert kind[("K1", "A2", "target")] == "exact"
    assert resolved[("K1", "L1", "source")] != "A2"


def test_pin_resolver_reports_unresolved_when_pool_exhausted():
    f1 = fuse(label="F1")  # only one down-facing port ("2")
    queries = [("F1", "x", "source"), ("F1", "y", "source")]
    resolved, kind = build_pin_resolver([f1], queries)
    assert resolved[("F1", "x", "source")] is not None
    assert resolved[("F1", "y", "source")] is None
    assert ("F1", "y", "source") not in kind


def test_pin_resolver_merges_disjoint_ports_across_same_tag_instances():
    """A relay's coil and its SPDT contact are commonly drawn as two separate
    symbols sharing one tag (e.g. "K8") -- their ports are disjoint, so
    merging must resolve both, not silently keep only whichever instance was
    last in the element list."""
    k8_coil = coil(label="K8")  # ports: A1, A2
    k8_contact = contactor(label="K8")  # ports: 1..6, no coil
    queries = [("K8", "A1", "target"), ("K8", "1", "source")]
    resolved, kind = build_pin_resolver([k8_coil, k8_contact], queries)
    assert resolved[("K8", "A1", "target")] == "A1"
    assert resolved[("K8", "1", "source")] == "1"
    assert kind[("K8", "A1", "target")] == "exact"
    assert kind[("K8", "1", "source")] == "exact"


def test_pin_resolver_drops_port_id_claimed_by_two_instances_of_same_tag():
    """Regression: two symbols sharing both a tag AND a real port id (e.g. a
    fixed reference symbol repeated once per identical sub-circuit instance)
    must not silently resolve to whichever instance came last -- that
    specific port id becomes unresolvable, full stop."""
    ref_a = ref(tag="SHARED", direction="up")  # port "2"
    ref_b = ref(tag="SHARED", direction="up")  # port "2", same id
    resolved, kind = build_pin_resolver([ref_a, ref_b], [("SHARED", "2", "target")])
    assert resolved[("SHARED", "2", "target")] is None
    assert ("SHARED", "2", "target") not in kind


# ---------------------------------------------------------------------------
# bbox-scoped search
# ---------------------------------------------------------------------------


def test_scoped_route_bounds_pads_the_route_span():
    page = BoundingBox(min_x=-1000.0, max_x=1000.0, min_y=-1000.0, max_y=1000.0)
    bounds = _scoped_route_bounds(
        Point(0.0, 0.0), Point(100.0, 50.0), margin=10.0, page_bounds=page
    )
    assert bounds.min_x == -10.0
    assert bounds.max_x == 110.0
    assert bounds.min_y == -10.0
    assert bounds.max_y == 60.0


def test_scoped_route_bounds_clamped_to_page():
    page = BoundingBox(min_x=0.0, max_x=50.0, min_y=0.0, max_y=50.0)
    bounds = _scoped_route_bounds(
        Point(0.0, 0.0), Point(10.0, 10.0), margin=100.0, page_bounds=page
    )
    assert bounds.min_x == 0.0
    assert bounds.max_x == 50.0
    assert bounds.min_y == 0.0
    assert bounds.max_y == 50.0


def test_obstacles_in_bounds_drops_far_obstacles_keeps_near_ones():
    bounds = BoundingBox(min_x=0.0, max_x=20.0, min_y=0.0, max_y=20.0)
    near = BoundingBox(min_x=5.0, max_x=10.0, min_y=5.0, max_y=10.0)
    far = BoundingBox(min_x=1000.0, max_x=1010.0, min_y=1000.0, max_y=1010.0)
    kept = _obstacles_in_bounds([near, far], bounds, clearance=2.5)
    assert kept == [near]


# ---------------------------------------------------------------------------
# route_pure / route_with_fallback
# ---------------------------------------------------------------------------


def test_route_pure_off_grid_endpoints_stay_orthogonal():
    cfg = RouterConfig()
    bounds = BoundingBox(min_x=-50.0, min_y=-50.0, max_x=200.0, max_y=200.0)
    start = Point(0.0, 145.0)
    end = Point(-10.0, 142.67949192431124)
    poly, _used = route_pure(
        start, end, blocked=set(), used_cells=frozenset(), bounds=bounds, config=cfg
    )
    assert poly[0] == start
    assert poly[-1] == end
    assert _is_orthogonal(poly)


def test_route_pure_is_stateless_same_inputs_same_outputs():
    cfg = RouterConfig()
    bounds = BoundingBox(min_x=-50.0, min_y=-50.0, max_x=150.0, max_y=150.0)
    obstacles = [BoundingBox(min_x=40.0, min_y=-10.0, max_x=60.0, max_y=60.0)]
    blocked = rasterize_obstacles(obstacles, cfg)
    used_cells0: frozenset = frozenset()

    poly_a, used_a = route_pure(
        Point(0.0, 0.0),
        Point(100.0, 0.0),
        blocked=blocked,
        used_cells=used_cells0,
        bounds=bounds,
        config=cfg,
    )
    poly_b, used_b = route_pure(
        Point(0.0, 0.0),
        Point(100.0, 0.0),
        blocked=blocked,
        used_cells=used_cells0,
        bounds=bounds,
        config=cfg,
    )

    assert poly_a == poly_b
    assert used_a == used_b
    # the input used_cells was not mutated by the first call
    assert used_cells0 == frozenset()


def test_route_pure_detours_around_an_obstacle():
    """The core claim of the module: a routed wire never crosses a symbol."""
    cfg = RouterConfig()
    bounds = BoundingBox(min_x=-50.0, min_y=-50.0, max_x=150.0, max_y=150.0)
    wall = BoundingBox(min_x=40.0, min_y=-10.0, max_x=60.0, max_y=60.0)

    poly, _used = route_pure(
        Point(0.0, 0.0),
        Point(100.0, 0.0),
        blocked=rasterize_obstacles([wall], cfg),
        used_cells=frozenset(),
        bounds=bounds,
        config=cfg,
    )

    assert len(poly) > 2  # a straight run would cross the wall
    assert _is_orthogonal(poly)
    for a, b in pairwise(poly):
        for step in range(101):
            t = step / 100
            x, y = a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t
            inside = wall.min_x <= x <= wall.max_x and wall.min_y <= y <= wall.max_y
            assert not inside, f"segment {a} -> {b} crosses the obstacle at ({x}, {y})"


def test_route_with_fallback_never_raises_and_stays_orthogonal():
    cfg = RouterConfig(obstacle_clearance=0.0)
    wall = [
        BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=-5.0),
        BoundingBox(min_x=-100.0, min_y=5.0, max_x=100.0, max_y=100.0),
        BoundingBox(min_x=-100.0, min_y=-5.0, max_x=-5.0, max_y=5.0),
        BoundingBox(min_x=5.0, min_y=-5.0, max_x=100.0, max_y=5.0),
    ]
    bounds = BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=100.0)
    blocked = rasterize_obstacles(wall, cfg)
    start, end = Point(-50.0, 0.0), Point(0.0, 0.0)  # end sealed inside the box

    poly, _used, used_fallback = route_with_fallback(
        start, end, blocked=blocked, used_cells=frozenset(), bounds=bounds, config=cfg
    )
    assert used_fallback
    assert poly[0] == start
    assert poly[-1] == end
    assert _is_orthogonal(poly)


def test_route_pure_raises_routing_error_when_sealed_in():
    cfg = RouterConfig(obstacle_clearance=0.0)
    wall = [
        BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=-5.0),
        BoundingBox(min_x=-100.0, min_y=5.0, max_x=100.0, max_y=100.0),
        BoundingBox(min_x=-100.0, min_y=-5.0, max_x=-5.0, max_y=5.0),
        BoundingBox(min_x=5.0, min_y=-5.0, max_x=100.0, max_y=5.0),
    ]
    bounds = BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=100.0)
    blocked = rasterize_obstacles(wall, cfg)
    with pytest.raises(RoutingError):
        route_pure(
            Point(-50.0, 0.0),
            Point(0.0, 0.0),
            blocked=blocked,
            used_cells=frozenset(),
            bounds=bounds,
            config=cfg,
        )


def test_polyline_to_wires_chains_consecutive_segments():
    points = [Point(0.0, 0.0), Point(10.0, 0.0), Point(10.0, 10.0)]
    wires = polyline_to_wires(points)
    assert len(wires) == 2
    assert wires[0].start == points[0]
    assert wires[0].end == points[1]
    assert wires[1].start == points[1]
    assert wires[1].end == points[2]


# ---------------------------------------------------------------------------
# Integration: real CircuitBuilder -> route_wires -> SVG
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TestCabinet:
    result: BuildResult
    extra_connections: list[tuple[str, str, str, str]]


def _build_test_cabinet(n_branches: int) -> _TestCabinet:
    """A small real cabinet (2 + 3*n_branches components) built via CircuitBuilder.

    Mirrors the round-2 spike's large_cabinet.py shape at integration-test
    scale: one main row (e-stop + n fuses + a shared neutral terminal) and
    n independent contactor/motor branches, merged, with the cross-branch
    wiring (supply feed, e-stop chain, coil return) passed as
    `extra_connections` -- exactly the topology CircuitBuilder's single
    active chain can't express itself.
    """
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
        branch_cb.set_layout(x=i * CIRCUIT_SPACING, y=2 * CIRCUIT_SPACING)
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

    merged = CircuitBuilder.merge(main_cb, *branch_builders)
    return _TestCabinet(result=merged.result, extra_connections=extra_connections)


def test_route_wires_end_to_end_on_real_circuit(tmp_path):
    cabinet = _build_test_cabinet(n_branches=8)  # 2 + 3*8 = 26 components
    layout_result = route_wires(
        cabinet.result, extra_connections=cabinet.extra_connections
    )

    assert not layout_result.unresolved
    assert layout_result.wires
    for wire in layout_result.wires:
        assert (
            abs(wire.start.x - wire.end.x) < 1e-9
            or abs(wire.start.y - wire.end.y) < 1e-9
        ), f"non-orthogonal wire {wire.start} -> {wire.end}"

    circuit = Circuit(elements=[*cabinet.result.circuit.elements, *layout_result.wires])
    out_path = tmp_path / "cabinet.svg"
    render_system(circuit, str(out_path))

    assert out_path.exists()
    svg_text = out_path.read_text(encoding="utf-8")
    assert "<svg" in svg_text
    assert svg_text.count("<line") >= len(layout_result.wires)


def test_route_wires_is_opt_in_build_result_untouched():
    """route_wires must not mutate the BuildResult it's given."""
    cabinet = _build_test_cabinet(n_branches=2)
    before = list(cabinet.result.circuit.elements)
    route_wires(cabinet.result, extra_connections=cabinet.extra_connections)
    assert cabinet.result.circuit.elements == before


def test_derive_routing_input_reports_heuristic_fraction():
    cabinet = _build_test_cabinet(n_branches=2)
    routing_input = derive_routing_input(
        cabinet.result, extra_connections=cabinet.extra_connections
    )
    assert routing_input.pairs
    # The cabinet mixes literal port ids (fuse "2", coil "A1") with semantic
    # contactor labels ("L1"), so neither extreme is the right answer.
    assert 0.0 < routing_input.heuristic_fraction < 1.0


def test_obstacles_excluding_and_all_symbols_bounds_cover_every_symbol():
    cabinet = _build_test_cabinet(n_branches=2)
    routing_input = derive_routing_input(
        cabinet.result, extra_connections=cabinet.extra_connections
    )
    bounds = all_symbols_bounds(routing_input.all_symbols)
    assert bounds.width > 0
    assert bounds.height > 0

    any_sym = routing_input.all_symbols[0]
    excluded = obstacles_excluding(routing_input.all_symbols, {id(any_sym)})
    assert len(excluded) == len(routing_input.all_symbols) - 1


def test_derive_routing_input_excludes_ambiguous_duplicate_labels():
    """Regression: two placed symbols sharing one label *and* the same real
    port id (a real pattern -- a fixed PLC reference tag repeated once per
    identical sub-circuit instance, e.g. `add_reference("PLC:DI")` called
    once per branch) must never resolve a connection to whichever instance
    happened to be placed last. That specific `(tag, port_id)` must be
    excluded from `symbols_by_port`; any connection naming it lands in
    `unresolved`, and both instances still count as routing obstacles.
    """
    state = create_initial_state()
    cb = CircuitBuilder(state=state)
    cb.set_layout(x=0, y=0)
    f1 = cb.add_symbol(fuse, config=SymbolConfig(tag_prefix="F"))
    ref1 = cb.add_reference(
        "SHARED",
        placement=PlacementOptions(relative_to=f1, position="right", x_offset=50),
        connection=ConnectionOptions(
            connect_from_previous=False, connect_to_next=False
        ),
    )
    cb.add_reference(
        "SHARED",
        placement=PlacementOptions(relative_to=ref1, position="right", x_offset=50),
        connection=ConnectionOptions(
            connect_from_previous=False, connect_to_next=False
        ),
    )
    result = cb.build(options=BuildOptions(state=state))

    routing_input = derive_routing_input(
        result, extra_connections=[("F1", "2", "SHARED", "2")]
    )

    assert ("SHARED", "2") not in routing_input.symbols_by_port
    assert ("F1", "2", "SHARED", "2") in routing_input.unresolved
    assert not any(
        p.to_tag == "SHARED" or p.from_tag == "SHARED" for p in routing_input.pairs
    )
    # Both duplicate-labeled instances still occupy space as obstacles.
    assert sum(1 for s in routing_input.all_symbols if s.label == "SHARED") == 2
