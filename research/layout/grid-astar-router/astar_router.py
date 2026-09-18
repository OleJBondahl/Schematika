"""OrthogonalRouter: A* grid pathfinder with turn/crossing penalties.

Operates directly in Schematika's real mm coordinate space (via
schematika.core.geometry.Point and schematika.core.bbox.BoundingBox), and
outputs schematika.core.primitives.Line segments — the same wire primitive
`schematika.electrical.layout.layout.draw_wire` already produces — so the
router's output drops straight into the existing renderer with no adapter.

Spike prototype for the `grid-astar-router` research track. Not production
code.
"""

import heapq
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


class OrthogonalRouter:
    """Grid-based A* router for orthogonal wires between two Schematika ports.

    `obstacles` should be the bounding boxes of every *other* placed symbol
    on the page (never the two symbols being connected — their own bboxes
    would otherwise block the very pins the route starts/ends at). Successive
    `route()` calls accumulate a "used cells" set so later wires pay the
    `crossing_penalty` for reusing a cell an earlier wire already occupied,
    which nudges the router toward parallel, non-overlapping runs.
    """

    def __init__(
        self,
        obstacles: list[BoundingBox],
        bounds: BoundingBox,
        config: RouterConfig | None = None,
    ) -> None:
        self.config = config or RouterConfig()
        self.bounds = bounds
        self._blocked: set[Cell] = self._rasterize(obstacles)
        self._used_cells: set[Cell] = set()

    @property
    def used_cell_count(self) -> int:
        """Total grid cells consumed by routes so far (for reporting/debugging)."""
        return len(self._used_cells)

    def _to_cell(self, p: Point) -> Cell:
        cs = self.config.cell_size
        return (round(p.x / cs), round(p.y / cs))

    def _to_point(self, c: Cell) -> Point:
        cs = self.config.cell_size
        return Point(c[0] * cs, c[1] * cs)

    def _rasterize(self, obstacles: list[BoundingBox]) -> set[Cell]:
        blocked: set[Cell] = set()
        cs = self.config.cell_size
        clr = self.config.obstacle_clearance
        for box in obstacles:
            min_c = self._to_cell(Point(box.min_x - clr, box.min_y - clr))
            max_c = self._to_cell(Point(box.max_x + clr, box.max_y + clr))
            for gx in range(min_c[0], max_c[0] + 1):
                for gy in range(min_c[1], max_c[1] + 1):
                    blocked.add((gx, gy))
        return blocked

    def _in_bounds(self, c: Cell) -> bool:
        p = self._to_point(c)
        margin = self.config.cell_size
        return (
            self.bounds.min_x - margin <= p.x <= self.bounds.max_x + margin
            and self.bounds.min_y - margin <= p.y <= self.bounds.max_y + margin
        )

    def route(self, start: Point, end: Point) -> list[Point]:
        """A* search from `start` to `end`; returns turn-point polyline (mm).

        The returned list contains only the start, the end, and every point
        where the path changes direction — a minimal polyline, not one point
        per grid cell — ready to be zipped into consecutive Line segments.
        """
        start_cell = self._to_cell(start)
        end_cell = self._to_cell(end)

        # State = (cell, incoming_direction). direction=None only for the
        # start node, which hasn't moved yet so no turn penalty applies.
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

                # Obstacles never block the goal cell itself (a pin can sit
                # flush against its own symbol's edge).
                if neighbor_cell in self._blocked and neighbor_cell != end_cell:
                    continue
                if not self._in_bounds(neighbor_cell):
                    continue

                step_cost = 1.0
                if direction is not None and d != direction:
                    step_cost += self.config.turn_penalty
                if neighbor_cell in self._used_cells:
                    step_cost += self.config.crossing_penalty

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

        cells = self._reconstruct(came_from, goal_state)
        for c in cells:
            self._used_cells.add(c)

        return self._compress_to_turns(cells, start, end)

    def _reconstruct(
        self,
        came_from: dict,
        goal_state: tuple,
    ) -> list[Cell]:
        path_states = [goal_state]
        state = goal_state
        while state in came_from:
            state = came_from[state]
            path_states.append(state)
        path_states.reverse()
        return [s[0] for s in path_states]

    def _compress_to_turns(
        self, cells: list[Cell], start: Point, end: Point
    ) -> list[Point]:
        if len(cells) < 2:
            return [start, end]

        # A turn vertex is the cell *shared* by the outgoing segment and the
        # next one, i.e. cells[i - 1] when the direction changes between
        # segment (i-2 -> i-1) and segment (i-1 -> i). Logging cells[i]
        # instead (an earlier, buggy version of this loop did) yields a
        # point that is diagonal from the previous turn, not orthogonal.
        turns: list[Point] = [start]
        prev_dir: Direction | None = None
        for i in range(1, len(cells) - 1):
            d = (cells[i][0] - cells[i - 1][0], cells[i][1] - cells[i - 1][1])
            if prev_dir is not None and d != prev_dir:
                turns.append(self._to_point(cells[i - 1]))
            prev_dir = d
        turns.append(end)
        return turns


def polyline_to_wires(points: list[Point]) -> list[Line]:
    """Convert an A*-produced polyline into consecutive Line segments.

    This is the "polyline format Schematika's renderer expects": the
    existing `draw_wire` helper already returns `list[Line]`, so a
    multi-turn A* route is just N-1 Lines chained end to end.
    """
    style = standard_style()
    return [
        Line(points[i], points[i + 1], style=style) for i in range(len(points) - 1)
    ]
