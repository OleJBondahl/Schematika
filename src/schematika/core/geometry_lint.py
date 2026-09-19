"""Deterministic wire-geometry linter.

Five checks -- orthogonality, text/wire collision, wire/symbol collision,
near-miss alignment, redundant routing jogs -- operating only on
`core.primitives`/`core.symbol` shapes, zero domain knowledge, so
`lint_elements`/`lint_build_result` can lint any domain's element tree
without this module importing electrical/pcb/pid.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import deal

from schematika._purity import pure
from schematika.core.geometry import Element, Point
from schematika.core.primitives import Group, Line, Text
from schematika.core.renderer import calculate_bounds
from schematika.core.symbol import Symbol
from schematika.core.validation_geometry import segment_intersects_bbox_interior

Bbox = tuple[float, float, float, float]
Severity = Literal["error", "warn", "info"]

_ZERO_LENGTH_TOLERANCE = 1e-9
_PASS_THROUGH_DEGREE = 2
_MIN_RAIL_OCCUPANCY = 2


@deal.pure
def _midpoint(a: Point, b: Point) -> Point:
    return Point((a.x + b.x) / 2, (a.y + b.y) / 2)


@dataclass(frozen=True)
class Finding:
    """One lint finding; `weight` contributes to `LintReport.cost`."""

    kind: str
    severity: Severity
    message: str
    location: Point
    weight: float


@dataclass(frozen=True)
class LintReport:
    """All findings from one lint pass, plus the derived scalar cost."""

    findings: tuple[Finding, ...]

    @property
    def cost(self) -> float:
        """Sum of finding weights -- usable directly as a placement-search objective."""
        return sum(f.weight for f in self.findings)

    def by_kind(self) -> dict[str, int]:
        """Count findings per `Finding.kind`."""
        return dict(Counter(f.kind for f in self.findings))


# ---------------------------------------------------------------------------
# Text bbox estimation. `core/bbox.py` deliberately does not compute text
# extent (anchor position only); "text overlaps wire" needs an estimate.
# ---------------------------------------------------------------------------

TEXT_WIDTH_FACTOR = 0.6
TEXT_LINE_HEIGHT_FACTOR = 1.3


@deal.pure
def text_bbox(text: Text) -> Bbox:
    """Estimate a Text's axis-aligned bbox; handles multi-line content and rotation."""
    lines = text.content.split("\n")
    longest = max(lines, key=len)
    width = len(longest) * text.font_size * TEXT_WIDTH_FACTOR
    height = len(lines) * text.font_size * TEXT_LINE_HEIGHT_FACTOR
    x = text.position.x
    y = text.position.y - text.font_size

    if text.anchor == "middle":
        x -= width / 2
    elif text.anchor == "end":
        x -= width

    if text.rotation == 0.0:
        return (x, y, x + width, y + height)

    # Rotate all four corners of the unrotated bbox around text.position and
    # return the axis-aligned envelope of the rotated rectangle.
    rad = math.radians(text.rotation)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    ox, oy = text.position.x, text.position.y
    corners = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    rot_xs = [cos_a * (cx - ox) - sin_a * (cy - oy) + ox for cx, cy in corners]
    rot_ys = [sin_a * (cx - ox) + cos_a * (cy - oy) + oy for cx, cy in corners]
    return (min(rot_xs), min(rot_ys), max(rot_xs), max(rot_ys))


# ---------------------------------------------------------------------------
# Check 1: non-orthogonal wires.
# ---------------------------------------------------------------------------


@deal.pure
def check_orthogonal_wires(
    wires: list[Line], angle_tolerance_deg: float = 0.5
) -> list[Finding]:
    """Flag wire segments that are not horizontal or vertical."""
    findings: list[Finding] = []
    for wire in wires:
        dx = wire.end.x - wire.start.x
        dy = wire.end.y - wire.start.y
        length = math.hypot(dx, dy)
        if length < _ZERO_LENGTH_TOLERANCE:
            continue
        angle = math.degrees(math.atan2(dy, dx)) % 90
        deviation = min(angle, 90 - angle)
        if deviation > angle_tolerance_deg:
            findings.append(
                Finding(
                    kind="non_orthogonal_wire",
                    severity="error",
                    message=(
                        f"Non-orthogonal wire from ({wire.start.x:.1f}, "
                        f"{wire.start.y:.1f}) to ({wire.end.x:.1f}, {wire.end.y:.1f}) "
                        f"deviates {deviation:.2f} deg from horizontal/vertical"
                    ),
                    location=_midpoint(wire.start, wire.end),
                    weight=deviation,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Check 2: text bbox intersects a wire segment.
# ---------------------------------------------------------------------------


@deal.pure
def check_text_wire_collisions(wires: list[Line], texts: list[Text]) -> list[Finding]:
    """Flag wire segments that cross a text label's estimated bounding box."""
    findings: list[Finding] = []
    for text in texts:
        box = text_bbox(text)
        findings.extend(
            Finding(
                kind="text_wire_collision",
                severity="error",
                message=(
                    f"Wire from ({wire.start.x:.1f}, {wire.start.y:.1f}) to "
                    f"({wire.end.x:.1f}, {wire.end.y:.1f}) crosses text "
                    f"{text.content!r}"
                ),
                location=_midpoint(wire.start, wire.end),
                weight=5.0,
            )
            for wire in wires
            if segment_intersects_bbox_interior((wire.start, wire.end), box)
        )
    return findings


# ---------------------------------------------------------------------------
# Check 3: a wire cuts through a symbol's footprint (not just touching a port
# on its edge).
# ---------------------------------------------------------------------------


@deal.pure
def _endpoint_inside_bbox(p: Point, box: Bbox, tolerance: float) -> bool:
    """True if *p* lands inside or on *box*, padded by *tolerance*.

    A wire's own start/end port commonly sits *inside* its symbol's
    rectangular bbox (not exactly on the edge -- e.g. a contactor's splayed
    contact ports), not just touching it -- so a plain boundary check isn't
    enough to recognize "this is the wire's own terminating symbol."
    """
    return (
        box[0] - tolerance <= p.x <= box[2] + tolerance
        and box[1] - tolerance <= p.y <= box[3] + tolerance
    )


@deal.pure
def check_wire_symbol_collisions(
    wires: list[Line], obstacles: list[Bbox], tolerance: float = 1e-6
) -> list[Finding]:
    """Flag wire segments that pass through a symbol's bounding-box interior.

    A wire terminating at a port on a symbol's edge touches the bbox boundary,
    not its interior, so legitimate connections are never flagged -- only a
    wire that visibly crosses through another component's body. An obstacle
    containing either of the wire's own endpoints is skipped entirely (it is
    presumptively the wire's own origin/destination symbol, not an unrelated
    one it cuts through).
    """
    findings: list[Finding] = []
    for wire in wires:
        for box in obstacles:
            if _endpoint_inside_bbox(
                wire.start, box, tolerance
            ) or _endpoint_inside_bbox(wire.end, box, tolerance):
                continue
            if segment_intersects_bbox_interior((wire.start, wire.end), box):
                findings.append(
                    Finding(
                        kind="wire_symbol_collision",
                        severity="error",
                        message=(
                            f"Wire from ({wire.start.x:.1f}, {wire.start.y:.1f}) "
                            f"to ({wire.end.x:.1f}, {wire.end.y:.1f}) passes "
                            "through a symbol's footprint"
                        ),
                        location=_midpoint(wire.start, wire.end),
                        weight=8.0,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Check 4: near-aligned but not exactly aligned points ("almost on grid").
# ---------------------------------------------------------------------------


@deal.pure
def check_near_alignment(points: list[Point], tolerance: float = 0.5) -> list[Finding]:
    """Flag points close to, but not exactly on, a shared grid line.

    Grouped by alignment line rather than by pair, so one point drifting off an
    axis shared by several others produces one finding, not one per pair.
    """
    findings: list[Finding] = []
    for axis, get in (("x", lambda p: p.x), ("y", lambda p: p.y)):
        counts = Counter(get(p) for p in points)
        rails = sorted(v for v, c in counts.items() if c >= _MIN_RAIL_OCCUPANCY)
        flagged: set[float] = set()
        for p in points:
            v = get(p)
            if counts[v] >= _MIN_RAIL_OCCUPANCY or v in flagged:
                continue
            for rail in rails:
                delta = abs(v - rail)
                if _ZERO_LENGTH_TOLERANCE < delta <= tolerance:
                    loc = Point(p.x, rail) if axis == "y" else Point(rail, p.y)
                    findings.append(
                        Finding(
                            kind="near_misaligned_pins",
                            severity="warn",
                            message=(
                                f"Point at {axis}={v:.3f} is {delta:.3f} mm off the "
                                f"{axis}={rail:.3f} alignment line"
                            ),
                            location=loc,
                            weight=(tolerance - delta) / tolerance * 2.0,
                        )
                    )
                    flagged.add(v)
                    break
    return findings


# ---------------------------------------------------------------------------
# Check 5: redundant jogs -- a wire chain with more turns than its endpoints
# need, obstacle-aware.
# ---------------------------------------------------------------------------


@deal.pure
def _snap_key(p: Point, tol: float) -> tuple[float, float]:
    return (round(p.x / tol), round(p.y / tol))


@pure
def _chain_wires(wires: list[Line], join_tol: float = 1e-6) -> list[list[Line]]:
    """Group wires into polyline chains by shared endpoints, degree-aware.

    A chain only continues through a point where exactly two segment-ends meet
    (this wire's own end, plus exactly one other) -- a T-junction (degree >= 3,
    e.g. a bus tap) or a free end (degree == 1) always stops the chain, so two
    independent wires that merely touch at a junction are never fused into one
    fictitious path.
    """
    live = [
        (i, w)
        for i, w in enumerate(wires)
        if math.hypot(w.end.x - w.start.x, w.end.y - w.start.y) > _ZERO_LENGTH_TOLERANCE
    ]

    endpoints: dict[tuple[float, float], list[tuple[int, str]]] = {}
    for i, wire in live:
        endpoints.setdefault(_snap_key(wire.start, join_tol), []).append((i, "start"))
        endpoints.setdefault(_snap_key(wire.end, join_tol), []).append((i, "end"))
    degree = {key: len(v) for key, v in endpoints.items()}

    visited: set[int] = set()
    chains: list[list[Line]] = []

    def other_unvisited(key: tuple[float, float]) -> tuple[int, str] | None:
        candidates = [(j, side) for j, side in endpoints[key] if j not in visited]
        return candidates[0] if len(candidates) == 1 else None

    for i, wire in live:
        if i in visited:
            continue
        visited.add(i)
        chain = [wire]

        while degree.get(_snap_key(chain[-1].end, join_tol), 0) == _PASS_THROUGH_DEGREE:
            found = other_unvisited(_snap_key(chain[-1].end, join_tol))
            if found is None:
                break
            j, side = found
            visited.add(j)
            nxt = wires[j]
            chain.append(
                nxt if side == "start" else Line(nxt.end, nxt.start, nxt.style)
            )

        while (
            degree.get(_snap_key(chain[0].start, join_tol), 0) == _PASS_THROUGH_DEGREE
        ):
            found = other_unvisited(_snap_key(chain[0].start, join_tol))
            if found is None:
                break
            j, side = found
            visited.add(j)
            prv = wires[j]
            chain.insert(
                0, prv if side == "end" else Line(prv.end, prv.start, prv.style)
            )

        chains.append(chain)
    return chains


@deal.pure
def _l_bend_candidates(start: Point, end: Point) -> list[list[tuple[Point, Point]]]:
    """The Manhattan-minimum candidate path(s) between two points."""
    if (
        abs(start.x - end.x) < _ZERO_LENGTH_TOLERANCE
        or abs(start.y - end.y) < _ZERO_LENGTH_TOLERANCE
    ):
        return [[(start, end)]]
    bend_h = Point(end.x, start.y)
    bend_v = Point(start.x, end.y)
    return [[(start, bend_h), (bend_h, end)], [(start, bend_v), (bend_v, end)]]


@deal.pure
def _path_is_unobstructed(
    path: list[tuple[Point, Point]], obstacles: tuple[Bbox, ...]
) -> bool:
    return not any(
        segment_intersects_bbox_interior(seg, box) for seg in path for box in obstacles
    )


@deal.pure
def check_redundant_jogs(
    wires: list[Line], obstacles: tuple[Bbox, ...] = ()
) -> list[Finding]:
    """Flag wire chains with more turns than their endpoints need.

    A chain's extra turns are only reported when at least one simpler
    (0-turn-if-collinear, else single-L-bend) route between its overall
    endpoints is provably unobstructed by `obstacles` (e.g. symbol footprints)
    -- a chain that legitimately routes around a component is not flagged.
    """
    min_chain_length = 2
    baseline_turns = 1
    findings: list[Finding] = []
    for chain in _chain_wires(wires):
        if len(chain) < min_chain_length:
            continue
        horizontal = [
            abs(w.end.x - w.start.x) > abs(w.end.y - w.start.y) for w in chain
        ]
        turns = sum(a != b for a, b in itertools.pairwise(horizontal))
        if turns <= baseline_turns:
            continue

        start, end = chain[0].start, chain[-1].end
        routes = _l_bend_candidates(start, end)
        if not any(_path_is_unobstructed(r, obstacles) for r in routes):
            continue

        findings.append(
            Finding(
                kind="redundant_jog_candidate",
                severity="info",
                message=(
                    f"Wire chain from ({start.x:.1f}, {start.y:.1f}) to "
                    f"({end.x:.1f}, {end.y:.1f}) has {turns} turns "
                    f"({len(chain)} segments), more than the Manhattan minimum"
                ),
                location=_midpoint(start, end),
                weight=float(turns - baseline_turns),
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Entry points.
# ---------------------------------------------------------------------------


@pure
def collect_wire_geometry(
    elements: list[Element],
) -> tuple[list[Line], list[Text], list[Bbox]]:
    """Split an element tree into top-level wires/labels vs. symbol obstacles.

    A `Symbol`'s interior `Line`s are fixed component glyph artwork (an IEC
    breaker's diagonal isolator blade, a fuse's crossed strokes) --
    legitimately non-orthogonal, not a wire defect. Only `Line`/`Text` reached
    without passing through a `Symbol` boundary count as wires/labels; each
    `Symbol` still contributes its bounding box as a `check_redundant_jogs`
    obstacle.
    """
    wires: list[Line] = []
    texts: list[Text] = []
    obstacles: list[Bbox] = []

    def walk(elem: Element, *, inside_symbol: bool) -> None:
        if isinstance(elem, Line):
            if not inside_symbol:
                wires.append(elem)
        elif isinstance(elem, Text):
            texts.append(elem)
        elif isinstance(elem, Symbol):
            obstacles.append(calculate_bounds(elem.elements))
            for child in elem.elements:
                walk(child, inside_symbol=True)
        elif isinstance(elem, Group):
            for child in elem.elements:
                walk(child, inside_symbol=inside_symbol)

    for elem in elements:
        walk(elem, inside_symbol=False)
    # A composite symbol wrapping a single nested symbol with no added margin
    # contributes the identical bbox twice (once per nesting level) -- dedupe
    # so a real collision isn't double-counted/double-weighted.
    return wires, texts, list(dict.fromkeys(obstacles))


@deal.pure
def lint_elements(
    elements: list[Element],
    *,
    angle_tolerance_deg: float = 0.5,
    align_tolerance: float = 0.5,
    extra_obstacles: tuple[Bbox, ...] = (),
) -> LintReport:
    """Run all five wire-geometry checks against an element tree in one call."""
    wires, texts, obstacles = collect_wire_geometry(elements)
    points = [w.start for w in wires] + [w.end for w in wires]
    all_obstacles = tuple(obstacles) + extra_obstacles
    findings = [
        *check_orthogonal_wires(wires, angle_tolerance_deg=angle_tolerance_deg),
        *check_text_wire_collisions(wires, texts),
        *check_wire_symbol_collisions(wires, list(all_obstacles)),
        *check_near_alignment(points, tolerance=align_tolerance),
        *check_redundant_jogs(wires, obstacles=all_obstacles),
    ]
    return LintReport(findings=tuple(findings))


@pure
def lint_build_result(result: object) -> LintReport:
    """Lint an `electrical.BuildResult`/`pid.PIDBuildResult`-shaped object in one call.

    Duck-typed on `.circuit` (electrical), `.diagram` (pid), or a bare
    `.elements` -- `core` cannot import any domain's `*BuildResult` type
    without violating the one-way dependency rule, so this is structural by
    necessity, not a style choice. `pcb.PCBBuildResult` has no single
    `.circuit`/`.elements` (its pages render on demand via
    `render_connector_block`) -- lint each rendered page's `Circuit.elements`
    with `lint_elements` directly instead.
    """
    if hasattr(result, "circuit"):
        return lint_elements(result.circuit.elements)  # ty: ignore[unresolved-attribute]
    if hasattr(result, "diagram"):
        return lint_elements(result.diagram.elements)  # ty: ignore[unresolved-attribute]
    return lint_elements(result.elements)  # ty: ignore[unresolved-attribute]
