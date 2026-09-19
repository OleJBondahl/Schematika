"""Grid A* auto-router: `BuildResult` -> orthogonal wire geometry.

Opt-in and additive. Nothing in `CircuitBuilder` or `Project` calls
`route_wires` -- it is a free function a caller invokes explicitly against an
already-built `BuildResult` to get auto-routed, obstacle-aware wire geometry
instead of (or in addition to) `draw_wire`'s x-alignment jogs. Everything
that doesn't call it keeps working exactly as before.

Pipeline, each stage independently testable:

    BuildResult.wire_connections + circuit.elements
        --[pin_resolver.build_pin_resolver]-->
    RoutingInput(pairs=[RoutePair(...)], symbols_by_port, unresolved)
        --[route_pure, one route at a time]-->
    LayoutResult(wires, unresolved, fallback_pairs)

State (the A* "cells consumed so far" set, used for the crossing-penalty
cost) is threaded explicitly through `route_pure`'s arguments and return
value rather than held on an object: a real multi-route pipeline needs a
*different* obstacle set per route (every route excludes its own two
endpoint symbols -- see `obstacles_excluding`), which a stateful router
class can't express without being reconstructed per route anyway. This
repo's `docs/ARCHITECTURE.md` caps mutable state at seven documented places;
this router is not an eighth.

Each route's A* search is bounded to a padded box around its own
`(start, end)` pair (`_scoped_route_bounds`), not the whole page. Searching
the whole page per route made routing time near-quadratic in component
count in practice (~7ms/pair at 14 components, ~104ms/pair at 152) even
though the search itself never failed -- the fix turns per-route cost into
something proportional to that route's own span instead of total page area.
"""

from __future__ import annotations

import dataclasses
import heapq
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from schematika.core.bbox import BoundingBox, compute_bounding_box
from schematika.core.exceptions import RoutingError
from schematika.core.geometry import Point
from schematika.core.parts import standard_style
from schematika.core.primitives import Line
from schematika.core.symbol import Symbol

from .pin_resolver import build_pin_resolver

if TYPE_CHECKING:
    from collections.abc import Sequence

    from schematika.core.geometry import Element
    from schematika.electrical.builder_models import BuildResult

__all__ = [
    "LayoutResult",
    "RouterConfig",
    "RoutingError",
    "route_wires",
]

Cell = tuple[int, int]
Direction = tuple[int, int]
WireConnection = tuple[str, str, str, str]
_AStarState = tuple[Cell, Direction | None]

_NEIGHBORS: tuple[Direction, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
_AXIS_TOL = 1e-9  # mm; floating-point tolerance for axis alignment
_MIN_PATH_CELLS = 2  # a path needs at least a start and an end cell


@dataclass(frozen=True)
class RouterConfig:
    """Tunables for the A* cost model and per-route search scoping.

    Examples:
        >>> from schematika.electrical import RouterConfig
        >>> RouterConfig().cell_size
        5.0
    """

    cell_size: float = 5.0  # mm; matches core.constants.GRID_SIZE
    turn_penalty: float = 15.0  # cost units; favors long straight runs
    crossing_penalty: float = 5.0  # cost units; discourages overlapping runs
    obstacle_clearance: float = 2.5  # mm padding added around each obstacle bbox
    search_margin: float = 30.0  # mm padding around each route's own (start, end) bbox


# ---------------------------------------------------------------------------
# A* search core
# ---------------------------------------------------------------------------


def _to_cell(p: Point, cell_size: float) -> Cell:
    return (round(p.x / cell_size), round(p.y / cell_size))


def _to_point(c: Cell, cell_size: float) -> Point:
    return Point(c[0] * cell_size, c[1] * cell_size)


def rasterize_obstacles(
    obstacles: list[BoundingBox], config: RouterConfig
) -> set[Cell]:
    """Grid cells covered by *obstacles*, padded by `config.obstacle_clearance`."""
    cell_size = config.cell_size
    clearance = config.obstacle_clearance
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

    A* only ever steps in axis-aligned single-cell moves, but the raw,
    off-grid `start`/`end` port position (e.g. `motor`'s ports, computed via
    `-math.sqrt(radius**2 - x_pos**2)` and essentially never on a 5mm grid
    line) replaces the search's own grid-snapped path endpoint -- so the
    segment connecting the last snapped grid point to the true port position
    can be diagonal even though the cell path itself was orthogonal.
    """
    if len(points) < _MIN_PATH_CELLS:
        return points
    result = [points[0]]
    for p in points[1:]:
        prev = result[-1]
        if abs(p.x - prev.x) > _AXIS_TOL and abs(p.y - prev.y) > _AXIS_TOL:
            result.append(Point(prev.x, p.y))
        result.append(p)
    return result


def _compress_to_turns(
    cells: list[Cell], start: Point, end: Point, cell_size: float
) -> list[Point]:
    if len(cells) < _MIN_PATH_CELLS:
        return _orthogonalize_ends([start, end])

    # A turn vertex is the cell *shared* by the outgoing segment and the
    # next one, i.e. cells[i - 1] when the direction changes between segment
    # (i-2 -> i-1) and segment (i-1 -> i). Logging cells[i] instead yields a
    # point diagonal from the previous turn, not orthogonal.
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
        return (
            bounds.min_x - cs <= p.x <= bounds.max_x + cs
            and bounds.min_y - cs <= p.y <= bounds.max_y + cs
        )

    start_state: _AStarState = (start_cell, None)

    open_set: list[tuple[float, int, _AStarState]] = []
    counter = 0
    heapq.heappush(open_set, (0.0, counter, start_state))

    g_score: dict[_AStarState, float] = {start_state: 0.0}
    came_from: dict[_AStarState, _AStarState] = {}

    def heuristic(c: Cell) -> float:
        return abs(c[0] - end_cell[0]) + abs(c[1] - end_cell[1])

    goal_state: _AStarState | None = None
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

            neighbor_state: _AStarState = (neighbor_cell, d)
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
    """Stateless A* route between two points; state is threaded, not mutated.

    Returns:
        `(polyline, new_used_cells)` -- the turn-point polyline and the
        updated used-cells set (a new frozenset; the input is untouched).

    Raises:
        RoutingError: If the search exhausts the open set without reaching
            `end` inside `bounds`.
    """
    cells = _astar(
        start, end, blocked=blocked, used_cells=used_cells, bounds=bounds, config=config
    )
    polyline = _compress_to_turns(cells, start, end, config.cell_size)
    return polyline, used_cells | frozenset(cells)


def route_with_fallback(
    start: Point,
    end: Point,
    *,
    blocked: set[Cell],
    used_cells: frozenset[Cell],
    bounds: BoundingBox,
    config: RouterConfig,
) -> tuple[list[Point], frozenset[Cell], bool]:
    """Like `route_pure`, but never raises: falls back to a straight 1-turn jog.

    A mid-`build()` `RoutingError` crash is not acceptable for a production
    layout module. The fallback (a naive Manhattan jog, ignoring obstacles)
    matches what `draw_wire` already produces for the common case.

    Returns:
        `(polyline, used_cells, used_fallback)`. `used_cells` is returned
        unchanged when the fallback was used, since a non-obstacle-aware jog
        shouldn't claim cells for the crossing penalty. `used_fallback` is
        `True` when the A* search failed and the caller should log/count it.
    """
    try:
        polyline, new_used = route_pure(
            start,
            end,
            blocked=blocked,
            used_cells=used_cells,
            bounds=bounds,
            config=config,
        )
    except RoutingError:
        warnings.warn(
            f"route_with_fallback: no A* path from {start} to {end}; "
            "falling back to a naive 1-turn Manhattan jog (not obstacle-aware).",
            stacklevel=2,
        )
        mid = Point(start.x, end.y)
        return _orthogonalize_ends([start, mid, end]), used_cells, True
    return polyline, new_used, False


def polyline_to_wires(points: list[Point]) -> list[Line]:
    """Convert an A*-produced polyline into consecutive Line segments."""
    style = standard_style()
    return [Line(points[i], points[i + 1], style=style) for i in range(len(points) - 1)]


# ---------------------------------------------------------------------------
# Per-route search scoping (the near-quadratic-time fix)
# ---------------------------------------------------------------------------


def _scoped_route_bounds(
    start: Point, end: Point, margin: float, page_bounds: BoundingBox
) -> BoundingBox:
    """Bound one route's A* search to its own span, clamped to the page.

    Whole-page bounds made every route's search cost proportional to total
    page area regardless of how close its two endpoints were -- root cause
    of the near-quadratic routing time at scale. A short local wire and a
    long fan-out wire now each pay for their own span, which is what
    actually varies per route.
    """
    return BoundingBox(
        min_x=max(page_bounds.min_x, min(start.x, end.x) - margin),
        max_x=min(page_bounds.max_x, max(start.x, end.x) + margin),
        min_y=max(page_bounds.min_y, min(start.y, end.y) - margin),
        max_y=min(page_bounds.max_y, max(start.y, end.y) + margin),
    )


def _obstacles_in_bounds(
    obstacles: list[BoundingBox], bounds: BoundingBox, clearance: float
) -> list[BoundingBox]:
    """Drop obstacles that can't possibly fall inside the scoped search bounds."""
    lo_x, hi_x = bounds.min_x - clearance, bounds.max_x + clearance
    lo_y, hi_y = bounds.min_y - clearance, bounds.max_y + clearance
    return [
        box
        for box in obstacles
        if box.max_x >= lo_x
        and box.min_x <= hi_x
        and box.max_y >= lo_y
        and box.min_y <= hi_y
    ]


# ---------------------------------------------------------------------------
# BuildResult -> routable pairs bridge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutePair:
    """One resolved (port, port) pair the router needs to connect.

    `from_symbol`/`to_symbol` are the exact placed `Symbol` objects, carried
    directly rather than re-derived from `(tag, port_id)` -- a connection
    resolved via `BuildResult.wire_connection_symbols` identity can name a
    `(tag, port_id)` that `RoutingInput.symbols_by_port` deliberately excludes
    as ambiguous (that's the whole point: identity resolves what the tag+port
    lookup alone can't), so a caller must use these fields for obstacle
    exclusion, not re-look-up through `symbols_by_port`.
    """

    from_tag: str
    from_port_id: str
    from_point: Point
    from_symbol: Symbol
    to_tag: str
    to_port_id: str
    to_point: Point
    to_symbol: Symbol
    resolution_kind: str  # "exact" | "heuristic" -- see pin_resolver.build_pin_resolver


@dataclass(frozen=True)
class RoutingInput:
    """Everything the router needs, derived from a real `BuildResult`.

    `symbols_by_port` maps each *unambiguous* `(tag, port_id)` to the specific
    symbol instance that owns it -- the granularity a real multi-part
    component needs (one tag, e.g. a relay's coil and its SPDT contact drawn
    as separate symbols sharing tag "K8", each contributing disjoint port
    ids). `all_symbols` is every placed labeled symbol, for obstacle/
    page-bounds purposes: a symbol excluded from `symbols_by_port` by an
    ambiguous port id still physically occupies space and must still block
    other wires.
    """

    symbols_by_port: dict[tuple[str, str], Symbol]
    all_symbols: list[Symbol] = field(default_factory=list)
    pairs: list[RoutePair] = field(default_factory=list)
    unresolved: list[WireConnection] = field(default_factory=list)

    @property
    def heuristic_fraction(self) -> float:
        """Share of pairs relying on the position heuristic for at least one end."""
        if not self.pairs:
            return 0.0
        exact = sum(1 for p in self.pairs if p.resolution_kind == "exact")
        return 1.0 - exact / len(self.pairs)


def _pad_connection_symbols(
    result: BuildResult, extra_count: int
) -> list[tuple[Symbol | None, Symbol | None]]:
    """Align `wire_connection_symbols` 1:1 with `wire_connections` + extras.

    Defensive, not speculative: a `BuildResult` built via `CircuitBuilder`
    always produces the two lists in lockstep, but nothing stops a
    hand-constructed `BuildResult` (a test fixture predating this field) from
    leaving `wire_connection_symbols` empty -- pad with "identity unknown"
    rather than let a length mismatch silently misalign the zip below.
    `extra_connections` (caller-supplied, cross-branch) never carry identity.
    """
    conn_symbols = list(result.wire_connection_symbols)
    n = len(result.wire_connections)
    if len(conn_symbols) < n:
        conn_symbols += [(None, None)] * (n - len(conn_symbols))
    elif len(conn_symbols) > n:
        conn_symbols = conn_symbols[:n]
    return conn_symbols + [(None, None)] * extra_count


def _collect_placed_symbols(
    elements: Sequence[object],
) -> tuple[list[Symbol], set[str], dict[tuple[str, str], Symbol]]:
    """All placed labeled symbols, their tags, and the ambiguity-safe port pool.

    `symbols_by_port` maps `(tag, port_id) -> Symbol`; a `(tag, port_id)`
    claimed by more than one instance under that tag is excluded, since it
    can't be resolved to a single position by tag+port alone -- see
    `derive_routing_input`.
    """
    all_symbols: list[Symbol] = []
    placed_tags: set[str] = set()
    symbols_by_port: dict[tuple[str, str], Symbol] = {}
    ambiguous_ports: set[tuple[str, str]] = set()
    for elem in elements:
        if not isinstance(elem, Symbol) or not elem.label:
            continue
        all_symbols.append(elem)
        placed_tags.add(elem.label)
        for port_id in elem.ports:
            key = (elem.label, port_id)
            if key in symbols_by_port:
                ambiguous_ports.add(key)
            else:
                symbols_by_port[key] = elem
    for key in ambiguous_ports:
        del symbols_by_port[key]
    return all_symbols, placed_tags, symbols_by_port


def _build_scoped_queries(
    known_connections: list[WireConnection],
    known_symbol_pairs: list[tuple[Symbol | None, Symbol | None]],
    all_symbols: list[Symbol],
) -> tuple[list[Symbol], list[tuple[str, str, str]], list[tuple[str, str]]]:
    """Build resolver-ready elements + queries with per-instance scoping.

    Scopes each known-identity endpoint to a synthetic per-object key so it
    resolves against *that instance's* ports alone, immune to any other
    same-tag sibling (see `derive_routing_input`). Returns
    `(resolver_elements, queries, scoped_tags)`, `scoped_tags` giving each
    connection's effective (from, to) query key in the same order as
    `known_connections`.
    """
    resolver_elements = list(all_symbols)
    scoped_keys: dict[int, str] = {}

    def _scope_tag(tag: str, sym: Symbol | None) -> str:
        if sym is None:
            return tag
        if id(sym) not in scoped_keys:
            key = f"{tag}\x00{id(sym)}"
            scoped_keys[id(sym)] = key
            resolver_elements.append(dataclasses.replace(sym, label=key))
        return scoped_keys[id(sym)]

    queries: list[tuple[str, str, str]] = []
    scoped_tags: list[tuple[str, str]] = []
    for (from_tag, from_pin, to_tag, to_pin), (from_sym, to_sym) in zip(
        known_connections, known_symbol_pairs, strict=True
    ):
        eff_from = _scope_tag(from_tag, from_sym)
        eff_to = _scope_tag(to_tag, to_sym)
        queries.append((eff_from, from_pin, "source"))
        queries.append((eff_to, to_pin, "target"))
        scoped_tags.append((eff_from, eff_to))
    return resolver_elements, queries, scoped_tags


def _build_route_pair(
    conn: WireConnection,
    scoped_tags: tuple[str, str],
    symbol_pair: tuple[Symbol | None, Symbol | None],
    resolved: dict[tuple[str, str, str], str | None],
    resolution_kind: dict[tuple[str, str, str], str],
    symbols_by_port: dict[tuple[str, str], Symbol],
) -> RoutePair | None:
    """Turn one connection into a `RoutePair`, or `None` if an end won't resolve.

    Each end takes its owning symbol from `symbol_pair` when `CircuitBuilder`
    recorded that identity, and falls back to the ambiguity-safe
    `symbols_by_port` pool otherwise -- see `derive_routing_input`.
    """
    from_tag, from_pin, to_tag, to_pin = conn
    from_query = (scoped_tags[0], from_pin, "source")
    to_query = (scoped_tags[1], to_pin, "target")

    real_from = resolved.get(from_query)
    real_to = resolved.get(to_query)
    if real_from is None or real_to is None:
        return None

    from_sym = symbol_pair[0] or symbols_by_port.get((from_tag, real_from))
    to_sym = symbol_pair[1] or symbols_by_port.get((to_tag, real_to))
    if from_sym is None or to_sym is None:
        return None

    both_exact = (
        resolution_kind.get(from_query) == "exact"
        and resolution_kind.get(to_query) == "exact"
    )
    return RoutePair(
        from_tag=from_tag,
        from_port_id=real_from,
        from_point=from_sym.ports[real_from].position,
        from_symbol=from_sym,
        to_tag=to_tag,
        to_port_id=real_to,
        to_point=to_sym.ports[real_to].position,
        to_symbol=to_sym,
        resolution_kind="exact" if both_exact else "heuristic",
    )


def derive_routing_input(
    result: BuildResult,
    *,
    extra_connections: Sequence[WireConnection] = (),
) -> RoutingInput:
    """Derive router-ready (port, port) pairs from a real `BuildResult`.

    Connections naming an unplaced tag, and those the pin resolver can't map
    to a real port, land in `RoutingInput.unresolved` instead of raising --
    the caller drops those wires rather than failing the whole layout. See
    `route_wires` for *extra_connections*.

    A connection whose exact placed endpoint `CircuitBuilder` used is known
    (`BuildResult.wire_connection_symbols`) resolves against *that specific
    instance's* ports alone, via a synthetic per-object key -- immune to any
    other same-tag sibling. One tag can legitimately name more than one
    physical symbol instance (a relay's coil and its SPDT contact are drawn
    as separate symbols both tagged "K8", each with disjoint ports), and a
    specific `(tag, port_id)` can even be claimed by more than one instance
    under that tag (a fixed PLC reference symbol repeated once per identical
    sub-circuit instance, each exposing the same port id) -- known identity
    resolves both cases correctly. Only a connection with *no* known identity
    (e.g. a cross-branch `extra_connections` tuple) falls back to the
    tag-merged `symbols_by_port` pool, which is ambiguity-safe but blind to
    which specific instance a semantic pin label belongs to -- exactly the
    case that pool's ambiguous-port exclusion protects against.
    """
    all_symbols, placed_tags, symbols_by_port = _collect_placed_symbols(
        result.circuit.elements
    )

    all_connections = list(result.wire_connections) + list(extra_connections)
    conn_symbols = _pad_connection_symbols(result, len(extra_connections))

    known_connections: list[WireConnection] = []
    known_symbol_pairs: list[tuple[Symbol | None, Symbol | None]] = []
    for conn, sym_pair in zip(all_connections, conn_symbols, strict=True):
        from_tag, _from_pin, to_tag, _to_pin = conn
        if from_tag in placed_tags and to_tag in placed_tags:
            known_connections.append(conn)
            known_symbol_pairs.append(sym_pair)

    resolver_elements, queries, scoped_tags = _build_scoped_queries(
        known_connections, known_symbol_pairs, all_symbols
    )
    resolved, resolution_kind = build_pin_resolver(resolver_elements, queries)

    pairs: list[RoutePair] = []
    unresolved: list[WireConnection] = [
        conn
        for conn in all_connections
        if conn[0] not in placed_tags or conn[2] not in placed_tags
    ]
    for conn, conn_scoped_tags, symbol_pair in zip(
        known_connections, scoped_tags, known_symbol_pairs, strict=True
    ):
        pair = _build_route_pair(
            conn,
            conn_scoped_tags,
            symbol_pair,
            resolved,
            resolution_kind,
            symbols_by_port,
        )
        if pair is None:
            unresolved.append(conn)
        else:
            pairs.append(pair)

    return RoutingInput(
        symbols_by_port=symbols_by_port,
        all_symbols=all_symbols,
        pairs=pairs,
        unresolved=unresolved,
    )


def obstacles_excluding(
    all_symbols: list[Symbol], exclude_ids: set[int]
) -> list[BoundingBox]:
    """Bounding boxes of every placed symbol except *exclude_ids* (a route's endpoints).

    Identity-based (`id(sym)`), not tag-based: an ambiguous, duplicate-labeled
    symbol has no single tag that safely names it, but it still occupies real
    space and must still block other routes.
    """
    return [
        compute_bounding_box(sym) for sym in all_symbols if id(sym) not in exclude_ids
    ]


def all_symbols_bounds(all_symbols: list[Symbol]) -> BoundingBox:
    """Bounding box enclosing every placed symbol -- the page bounds routes clamp to."""
    elements: list[Element] = list(all_symbols)
    return compute_bounding_box(elements)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LayoutResult:
    """Auto-routed wire geometry produced by `route_wires`.

    Examples:
        >>> from schematika.electrical import LayoutResult
        >>> LayoutResult(wires=[]).wires
        []
    """

    wires: list[Line]
    unresolved: list[WireConnection] = field(default_factory=list)
    fallback_pairs: list[tuple[str, str]] = field(default_factory=list)


def route_wires(
    result: BuildResult,
    /,
    *,
    extra_connections: Sequence[WireConnection] = (),
    config: RouterConfig | None = None,
) -> LayoutResult:
    """Auto-route every resolvable wire in *result* with a grid A* search.

    Opt-in: nothing in `CircuitBuilder`/`Project` calls this automatically.
    A caller invokes it explicitly after `build()` to get orthogonal,
    obstacle-aware wire geometry instead of (or alongside) `draw_wire`.

    Args:
        result: Output of one or more merged `CircuitBuilder.build()` calls.
        extra_connections: Cross-branch wire tuples in the same
            `(from_tag, from_pin, to_tag, to_pin)` shape as
            `result.wire_connections`, for topology spanning more than one
            builder.
        config: Router cost-model and search-scoping tunables. `None` uses
            `RouterConfig()` defaults.

    Returns:
        `LayoutResult` with one wire per resolvable connection (routed if
        possible, a straight 1-turn fallback jog otherwise), the connections
        the pin resolver couldn't map to a real port, and the
        `(from_tag, to_tag)` pairs that needed the fallback jog.

    Examples:
        >>> from schematika.core.options import SymbolConfig
        >>> from schematika.electrical import CircuitBuilder, create_initial_state
        >>> from schematika.electrical import route_wires
        >>> from schematika.electrical.symbols import fuse
        >>> cb = CircuitBuilder(state=create_initial_state())
        >>> _ = cb.add_symbol(fuse, config=SymbolConfig(tag_prefix="F"))
        >>> _ = cb.add_symbol(fuse, config=SymbolConfig(tag_prefix="F"))
        >>> layout = route_wires(cb.build())
        >>> isinstance(layout.wires, list)
        True
    """
    cfg = config or RouterConfig()
    routing_input = derive_routing_input(result, extra_connections=extra_connections)
    page_bounds = all_symbols_bounds(routing_input.all_symbols)
    used_cells: frozenset[Cell] = frozenset()
    wires: list[Line] = []
    fallback_pairs: list[tuple[str, str]] = []

    for pair in routing_input.pairs:
        bounds = _scoped_route_bounds(
            pair.from_point, pair.to_point, cfg.search_margin, page_bounds
        )
        obstacles = _obstacles_in_bounds(
            obstacles_excluding(
                routing_input.all_symbols, {id(pair.from_symbol), id(pair.to_symbol)}
            ),
            bounds,
            cfg.obstacle_clearance,
        )
        blocked = rasterize_obstacles(obstacles, cfg)
        polyline, used_cells, used_fallback = route_with_fallback(
            pair.from_point,
            pair.to_point,
            blocked=blocked,
            used_cells=used_cells,
            bounds=bounds,
            config=cfg,
        )
        if used_fallback:
            fallback_pairs.append((pair.from_tag, pair.to_tag))
        wires.extend(polyline_to_wires(polyline))

    return LayoutResult(
        wires=wires, unresolved=routing_input.unresolved, fallback_pairs=fallback_pairs
    )
