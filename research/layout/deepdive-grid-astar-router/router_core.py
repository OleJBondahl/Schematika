"""OrthogonalRouter: hardened for round 2 of the grid-astar-router spike.

Carries forward round 1's `research/layout/grid-astar-router/astar_router.py`
unchanged in its core search (that file's `_compress_to_turns` fix -- logging
the turn vertex at `cells[i - 1]`, not `cells[i]` -- is already correct there
and is preserved here verbatim; re-verified in `test_router_core.py`).

Round 2 adds the two things round 1 flagged as missing:

1. `route_with_fallback` -- round 1 had no answer for "what happens when
   `route()` raises `RoutingError`". A hard crash mid-build is not
   acceptable in a real `electrical.layout` module. The fallback here is a
   straight 1-turn Manhattan polyline (ignores obstacles, matches what
   `draw_wire` already does today for the common case), with the caller
   told a fallback was used so it can log/count it.
2. `route_pure` -- a stateless sibling of `OrthogonalRouter.route()` that
   threads `used_cells` explicitly instead of mutating `self._used_cells`,
   prototyping the "functional state" alternative to adding `OrthogonalRouter`
   as an 8th documented mutable place. See the deep-dive doc's mutable-state
   section for the equivalence check and recommendation.

Not production code. Throwaway research spike, not imported by `src/schematika`.
"""

from __future__ import annotations

import heapq
import warnings
from dataclasses import dataclass

from schematika.core.bbox import BoundingBox
from schematika.core.geometry import Point
from schematika.core.parts import standard_style
from schematika.core.primitives import Line

Cell = tuple[int, int]
Direction = tuple[int, int]

_NEIGHBORS: tuple[Direction, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True)
class RouterConfig:
    """Tunables for the A* cost model, all in "cells" or mm."""

    cell_size: float = 5.0  # mm; matches core.constants.GRID_SIZE
    turn_penalty: float = 15.0  # cost units; favors long straight runs
    crossing_penalty: float = 5.0  # cost units; discourages overlapping runs
    obstacle_clearance: float = 2.5  # mm padding added around each obstacle bbox


class RoutingError(Exception):
    """Raised when the A* search exhausts the open set without reaching goal."""


def _to_cell(p: Point, cell_size: float) -> Cell:
    return (round(p.x / cell_size), round(p.y / cell_size))


def _to_point(c: Cell, cell_size: float) -> Point:
    return Point(c[0] * cell_size, c[1] * cell_size)


def _rasterize(
    obstacles: list[BoundingBox], cell_size: float, clearance: float
) -> set[Cell]:
    blocked: set[Cell] = set()
    for box in obstacles:
        min_c = _to_cell(Point(box.min_x - clearance, box.min_y - clearance), cell_size)
        max_c = _to_cell(Point(box.max_x + clearance, box.max_y + clearance), cell_size)
        for gx in range(min_c[0], max_c[0] + 1):
            for gy in range(min_c[1], max_c[1] + 1):
                blocked.add((gx, gy))
    return blocked


def _orthogonalize_ends(points: list[Point]) -> list[Point]:
    """Insert a corner wherever a consecutive pair isn't axis-aligned.

    Round 2 found this the hard way: at real cabinet scale, `motor`'s port
    positions come from `-math.sqrt(radius**2 - x_pos**2)` and land a few mm
    off any 5mm grid line. The A* search only ever moves in axis-aligned
    single-cell steps, but `_compress_to_turns` below substitutes the raw,
    off-grid `start`/`end` port position for the search's own grid-snapped
    endpoint -- so the *segment* connecting the last snapped grid point to
    the true (off-grid) port can be diagonal even though the cell path
    itself was perfectly orthogonal. Round 1's demo circuit never hit this
    because its hand-picked coordinates were already grid-aligned; round 2's
    geometry-linter pass on the 98-component cabinet caught 16 of these in
    one run (see the deep-dive doc's quality section) -- exactly the kind of
    defect a visual read of one wire, or even round 1's by-hand
    re-derivation, would not reliably catch across a whole cabinet.
    """
    if len(points) < 2:
        return points
    result = [points[0]]
    for p in points[1:]:
        prev = result[-1]
        if abs(p.x - prev.x) > 1e-9 and abs(p.y - prev.y) > 1e-9:
            result.append(Point(prev.x, p.y))
        result.append(p)
    return result


def _compress_to_turns(
    cells: list[Cell], start: Point, end: Point, cell_size: float
) -> list[Point]:
    if len(cells) < 2:
        return _orthogonalize_ends([start, end])

    # A turn vertex is the cell *shared* by the outgoing segment and the
    # next one, i.e. cells[i - 1] when the direction changes between
    # segment (i-2 -> i-1) and segment (i-1 -> i). Logging cells[i]
    # instead (an earlier, buggy version of this loop did, see round 1's
    # findings doc) yields a point that is diagonal from the previous turn,
    # not orthogonal.
    turns: list[Point] = [start]
    prev_dir: Direction | None = None
    for i in range(1, len(cells) - 1):
        d = (cells[i][0] - cells[i - 1][0], cells[i][1] - cells[i - 1][1])
        if prev_dir is not None and d != prev_dir:
            turns.append(_to_point(cells[i - 1], cell_size))
        prev_dir = d
    turns.append(end)
    return _orthogonalize_ends(turns)


def _astar(
    start: Point,
    end: Point,
    *,
    blocked: set[Cell],
    used_cells: frozenset[Cell],
    bounds: BoundingBox,
    config: RouterConfig,
) -> list[Cell]:
    """Pure A* search over the grid; returns the cell path or raises RoutingError."""
    cs = config.cell_size
    start_cell = _to_cell(start, cs)
    end_cell = _to_cell(end, cs)

    def in_bounds(c: Cell) -> bool:
        p = _to_point(c, cs)
        margin = cs
        return (
            bounds.min_x - margin <= p.x <= bounds.max_x + margin
            and bounds.min_y - margin <= p.y <= bounds.max_y + margin
        )

    StateT = tuple[Cell, Direction | None]
    start_state: StateT = (start_cell, None)

    open_set: list[tuple[float, int, StateT]] = []
    counter = 0
    heapq.heappush(open_set, (0.0, counter, start_state))

    g_score: dict[StateT, float] = {start_state: 0.0}
    came_from: dict[StateT, StateT] = {}

    def heuristic(c: Cell) -> float:
        return abs(c[0] - end_cell[0]) + abs(c[1] - end_cell[1])

    goal_state: StateT | None = None
    while open_set:
        _, _, current = heapq.heappop(open_set)
        cell, direction = current

        if cell == end_cell:
            goal_state = current
            break

        for d in _NEIGHBORS:
            neighbor_cell = (cell[0] + d[0], cell[1] + d[1])

            if neighbor_cell in blocked and neighbor_cell != end_cell:
                continue
            if not in_bounds(neighbor_cell):
                continue

            step_cost = 1.0
            if direction is not None and d != direction:
                step_cost += config.turn_penalty
            if neighbor_cell in used_cells:
                step_cost += config.crossing_penalty

            neighbor_state: StateT = (neighbor_cell, d)
            tentative_g = g_score[current] + step_cost

            if tentative_g < g_score.get(neighbor_state, float("inf")):
                g_score[neighbor_state] = tentative_g
                came_from[neighbor_state] = current
                f = tentative_g + heuristic(neighbor_cell)
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor_state))

    if goal_state is None:
        msg = f"No orthogonal route found from {start} to {end}"
        raise RoutingError(msg)

    path_states = [goal_state]
    state = goal_state
    while state in came_from:
        state = came_from[state]
        path_states.append(state)
    path_states.reverse()
    return [s[0] for s in path_states]


def route_pure(
    start: Point,
    end: Point,
    *,
    blocked: set[Cell],
    used_cells: frozenset[Cell],
    bounds: BoundingBox,
    config: RouterConfig,
) -> tuple[list[Point], frozenset[Cell]]:
    """Stateless A* route: takes/returns `used_cells` instead of mutating an object.

    This is the "thread state functionally" alternative to `OrthogonalRouter`'s
    mutable `_used_cells` accumulator, prototyped to answer the round-1
    mutable-state question. Produces byte-identical polylines to
    `OrthogonalRouter.route()` given the same inputs (verified in
    `test_router_core.py::test_pure_and_stateful_agree`).

    Args:
        start: Route start point (mm), e.g. a source port position.
        end: Route end point (mm), e.g. a target port position.
        blocked: Rasterized obstacle cells (from `rasterize_obstacles`).
        used_cells: Cells consumed by routes so far; threaded in and out
            instead of accumulated on `self`.
        bounds: Page bounds the search may not leave (with one cell margin).
        config: Cost-model tunables.

    Returns:
        `(polyline, new_used_cells)` -- the turn-point polyline and the
        updated used-cells set (a new frozenset; the input is untouched).

    Raises:
        RoutingError: If the search exhausts the open set without reaching
            `end`.
    """
    cells = _astar(
        start, end, blocked=blocked, used_cells=used_cells, bounds=bounds, config=config
    )
    polyline = _compress_to_turns(cells, start, end, config.cell_size)
    return polyline, used_cells | frozenset(cells)


def rasterize_obstacles(
    obstacles: list[BoundingBox], config: RouterConfig
) -> set[Cell]:
    """Expose `_rasterize` for `route_pure` callers that manage their own state."""
    return _rasterize(obstacles, config.cell_size, config.obstacle_clearance)


class OrthogonalRouter:
    """Grid-based A* router for orthogonal wires between two Schematika ports.

    `obstacles` should be the bounding boxes of every *other* placed symbol
    on the page (never the two symbols being connected -- their own bboxes
    would otherwise block the very pins the route starts/ends at). Successive
    `route()` calls accumulate a "used cells" set so later wires pay the
    `crossing_penalty` for reusing a cell an earlier wire already occupied,
    which nudges the router toward parallel, non-overlapping runs.

    This class is a thin, page-scoped, short-lived wrapper around `route_pure`
    for callers that don't want to thread `used_cells` by hand -- `route()`
    below calls `route_pure` directly and reassigns `self._used_cells` from
    its return value, so the two forms are equivalent *by construction*, not
    merely by testing (there is only one search implementation, `_astar`).
    See the deep-dive doc for why round 2 recommends keeping this stateful
    wrapper as an 8th documented mutable place (matching `CircuitBuilder`'s
    own lifecycle) rather than forcing every caller onto `route_pure` directly.
    """

    def __init__(
        self,
        obstacles: list[BoundingBox],
        bounds: BoundingBox,
        config: RouterConfig | None = None,
    ) -> None:
        self.config = config or RouterConfig()
        self.bounds = bounds
        self._blocked: set[Cell] = _rasterize(
            obstacles, self.config.cell_size, self.config.obstacle_clearance
        )
        self._used_cells: frozenset[Cell] = frozenset()

    @property
    def used_cell_count(self) -> int:
        """Total grid cells consumed by routes so far (for reporting/debugging)."""
        return len(self._used_cells)

    def route(self, start: Point, end: Point) -> list[Point]:
        """A* search from `start` to `end`; returns turn-point polyline (mm).

        Raises:
            RoutingError: If the search exhausts the open set without
                reaching `end`. Callers that need a guaranteed result should
                use `route_with_fallback` instead.
        """
        polyline, new_used = route_pure(
            start,
            end,
            blocked=self._blocked,
            used_cells=self._used_cells,
            bounds=self.bounds,
            config=self.config,
        )
        self._used_cells = new_used
        return polyline

    def route_with_fallback(self, start: Point, end: Point) -> tuple[list[Point], bool]:
        """Like `route`, but never raises: falls back to a straight 1-turn polyline.

        Round 1 flagged this as a real gap -- a mid-`build()` `RoutingError`
        crash is not acceptable for a production layout module, and the
        obvious alternatives (relax clearance and retry, or fall back to a
        naive Manhattan jog) trade search quality for guaranteed output. This
        picks the naive-jog fallback: cheapest to reason about, matches what
        `draw_wire` already produces for the common case, and never blocks a
        build on a routing failure in a page dense enough to have none.

        Returns:
            `(polyline, used_fallback)`. `used_fallback` is `True` when the
            A* search failed and the naive fallback was used instead --
            callers should log/count this, since a fallback wire is not
            obstacle-aware and may visually overlap something.
        """
        try:
            return self.route(start, end), False
        except RoutingError:
            warnings.warn(
                f"OrthogonalRouter: no A* path from {start} to {end}; "
                "falling back to a naive 1-turn Manhattan jog (not obstacle-aware).",
                stacklevel=2,
            )
            mid = Point(start.x, end.y)
            return [start, mid, end], True


def polyline_to_wires(points: list[Point]) -> list[Line]:
    """Convert an A*-produced polyline into consecutive Line segments.

    This is the "polyline format Schematika's renderer expects": the
    existing `draw_wire` helper already returns `list[Line]`, so a
    multi-turn A* route is just N-1 Lines chained end to end.
    """
    style = standard_style()
    return [Line(points[i], points[i + 1], style=style) for i in range(len(points) - 1)]
