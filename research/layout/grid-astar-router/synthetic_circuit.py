"""A synthetic cabinet-ladder circuit for the grid-astar-router spike.

Shape (a realistic small control cabinet, not a toy):

    Col 0 (start rung):    F1(breaker) -> S0(e-stop, NC) -> K1(coil)
    Col 1 (seal-in feed):  F2(fuse)    -> K1(NO aux contact, tag reused)
    Col 2 (spare rung):    F3(fuse)    -> S2(NC contact)              [pure obstacle]
    Col 3 (remote coil):   Q1(coil)
    Col 4 (remote coil):   Q2(coil)

    K1's auxiliary NO contact (col 1) fans out to two remote coils, Q1
    (col 3) and Q2 (col 4) -- both physically drawn in different columns,
    so both wires must cross column 2 (which holds an unrelated F3/S2 rung
    acting as an obstacle). This is the case a manual `position: Point`
    layout handles by eyeballing a jog; it is also exactly the case that
    exercises CabinetGridAllocator + OrthogonalRouter together instead of
    the straight-line `draw_wire` helper. Routing both wires from the same
    starting pin also exercises the router's crossing-penalty: the second
    route (to Q2) starts by wanting the same cells the first route (to Q1)
    already claimed, and has to pay for every cell it reuses.

Every symbol comes from schematika.electrical.symbols (real IEC 60617
factories); every coordinate comes from CabinetGridAllocator (real mm).
"""

from dataclasses import dataclass
from typing import cast

from astar_router import OrthogonalRouter, RouterConfig, polyline_to_wires
from cabinet_grid import CabinetGridAllocator, GridZones

from schematika.core.bbox import BoundingBox, compute_bounding_box
from schematika.core.geometry import Element, Point
from schematika.core.parts import standard_style
from schematika.core.primitives import Line
from schematika.core.symbol import Symbol
from schematika.core.transform import translate
from schematika.electrical.layout.layout import draw_wire
from schematika.electrical.symbols import (
    breaker,
    coil,
    estop,
    fuse,
    nc_contact,
    no_contact,
    terminal,
)

N_COLUMNS = 5
BUS_STYLE = standard_style()


@dataclass(frozen=True)
class LadderResult:
    """Everything needed to render the demo circuit, plus stats for the writeup."""

    elements: list[Element]
    placed_symbols: list[Symbol]
    routed_wire_points: list[Point]
    route_to_q2_points: list[Point]
    astar_cells_explored: int


def _place(factory_symbol: Symbol, at: Point) -> Symbol:
    return translate(factory_symbol, at.x, at.y)


def build_ladder() -> LadderResult:
    """Build the synthetic cabinet ladder and return placed symbols + wires."""
    grid = CabinetGridAllocator(GridZones())
    elements: list[Element] = []
    placed: list[Symbol] = []

    def place_and_track(sym: Symbol, point: Point) -> Symbol:
        s = _place(sym, point)
        placed.append(s)
        elements.append(s)
        return s

    # --- Column 0: start rung -------------------------------------------
    slot = grid.slot(0, "protection")
    f1 = place_and_track(breaker(label="F1"), slot.point)
    s0 = place_and_track(estop(label="S0"), grid.slot(0, "control").point)
    k1 = place_and_track(coil(label="K1"), grid.slot(0, "coils").point)
    elements += draw_wire(f1, s0)
    elements += draw_wire(s0, k1)

    # --- Column 1: seal-in / interlock feed rung -------------------------
    f2 = place_and_track(fuse(label="F2"), grid.slot(1, "protection").point)
    k1_aux = place_and_track(no_contact(label="K1"), grid.slot(1, "control").point)
    elements += draw_wire(f2, k1_aux)

    # --- Column 2: spare rung (pure obstacle for the router) -------------
    f3 = place_and_track(fuse(label="F3"), grid.slot(2, "protection").point)
    s2 = place_and_track(nc_contact(label="S2"), grid.slot(2, "control").point)
    elements += draw_wire(f3, s2)

    # --- Columns 3-4: remotely-interlocked coils ---------------------------
    q1 = place_and_track(coil(label="Q1"), grid.slot(3, "coils").point)
    q2 = place_and_track(coil(label="Q2"), grid.slot(4, "coils").point)

    # --- Power rails (L top, N bottom) ------------------------------------
    l_bus_start, l_bus_end = grid.rail_span("power_rail_top", 0, N_COLUMNS - 1)
    elements.append(Line(l_bus_start, l_bus_end, style=BUS_STYLE))
    n_bus_start, n_bus_end = grid.rail_span("power_rail_bottom", 0, N_COLUMNS - 1)
    elements.append(Line(n_bus_start, n_bus_end, style=BUS_STYLE))

    top_zone_y = grid.zones.power_rail_top
    bottom_zone_y = grid.zones.power_rail_bottom
    for sym, top_port_id in ((f1, "1"), (f2, "1"), (f3, "1")):
        p = sym.ports[top_port_id].position
        elements.append(Line(Point(p.x, top_zone_y), p, style=BUS_STYLE))
    for sym, bottom_port_id in ((k1, "A2"), (s2, "12"), (q1, "A2"), (q2, "A2")):
        p = sym.ports[bottom_port_id].position
        elements.append(Line(p, Point(p.x, bottom_zone_y), style=BUS_STYLE))

    # --- Terminal strip (field-wiring zone) --------------------------------
    for col in range(N_COLUMNS):
        term_point = grid.slot(col, "terminals").point
        x_term = place_and_track(terminal(label=f"X{col + 1}"), term_point)
        top_port = x_term.ports["top"].position
        bus_stub = Line(Point(top_port.x, bottom_zone_y), top_port, style=BUS_STYLE)
        elements.append(bus_stub)

    # --- The interesting wires: K1 aux contact fans out to Q1 AND Q2,
    # both cross-column. Both routes share one OrthogonalRouter instance so
    # the second route pays the crossing_penalty for cells the first route
    # already claimed. ----------------------------------------------------
    cross_column_endpoints = (k1_aux, q1, q2)
    obstacles: list[BoundingBox] = [
        compute_bounding_box(sym)
        for sym in placed
        if all(sym is not endpoint for endpoint in cross_column_endpoints)
    ]
    page_bounds = compute_bounding_box(cast(list[Element], placed))
    router = OrthogonalRouter(obstacles, page_bounds, RouterConfig())

    start = k1_aux.ports["14"].position
    route_to_q1 = router.route(start, q1.ports["A1"].position)
    elements += polyline_to_wires(route_to_q1)

    route_to_q2 = router.route(start, q2.ports["A1"].position)
    elements += polyline_to_wires(route_to_q2)

    return LadderResult(
        elements=elements,
        placed_symbols=placed,
        routed_wire_points=route_to_q1,
        route_to_q2_points=route_to_q2,
        astar_cells_explored=router.used_cell_count,
    )
