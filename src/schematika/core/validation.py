"""Shared validation helpers used by all diagram validators."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import deal

from schematika._purity import pure
from schematika.core.geometry import Point
from schematika.core.primitives import Group, Line, Text
from schematika.core.renderer import calculate_bounds
from schematika.core.symbol import Symbol
from schematika.core.traversal import collect_by_type
from schematika.core.validation_geometry import segment_intersects_bbox_interior

if TYPE_CHECKING:
    from collections.abc import Callable

    from schematika.core.geometry import Element

TEXT_WIDTH_FACTOR = 0.6
TEXT_LINE_HEIGHT_FACTOR = 1.3


@dataclass
class ValidationResult:
    """Result of diagram layout validation."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@pure
def collect_elements(elements: list[Element], element_type: type) -> list:
    """Recursively collect elements of a given type from nested structures."""
    return collect_by_type(elements, element_type)


@deal.pure
def boxes_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """Return True if two axis-aligned bounding boxes intersect."""
    a_min_x, a_min_y, a_max_x, a_max_y = a
    b_min_x, b_min_y, b_max_x, b_max_y = b
    return (
        a_min_x < b_max_x
        and a_max_x > b_min_x
        and a_min_y < b_max_y
        and a_max_y > b_min_y
    )


@deal.pure
def text_bbox(text: Text) -> tuple[float, float, float, float]:
    """Estimate axis-aligned bounding box for a Text element.

    Handles multi-line text (content with newlines) and Text.rotation.
    For rotated text, returns the axis-aligned bbox of the rotated rectangle.
    """
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
    corners = [
        (x, y),
        (x + width, y),
        (x + width, y + height),
        (x, y + height),
    ]
    rot_xs = [cos_a * (cx - ox) - sin_a * (cy - oy) + ox for cx, cy in corners]
    rot_ys = [sin_a * (cx - ox) + cos_a * (cy - oy) + oy for cx, cy in corners]
    return (min(rot_xs), min(rot_ys), max(rot_xs), max(rot_ys))


@pure
def check_text_overlap(elements: list[Element]) -> list[str]:
    """Return warnings for pairwise text overlap among all Text elements."""
    warnings: list[str] = []
    texts = collect_elements(elements, Text)
    text_boxes = [text_bbox(t) for t in texts]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if boxes_overlap(text_boxes[i], text_boxes[j]):
                x = (texts[i].position.x + texts[j].position.x) / 2
                y = (texts[i].position.y + texts[j].position.y) / 2
                warnings.append(
                    f"Text overlap: '{texts[i].content}' and '{texts[j].content}' "
                    f"at ({x:.1f}, {y:.1f})"
                )
    return warnings


@deal.pure
def check_page_bounds(
    items: list[Any],
    bounds: list[tuple[float, float, float, float]],
    page_width: float,
    page_height: float,
    margin: float,
    label_fn: Callable[[Any], str] = lambda x: x.label,
) -> list[str]:
    """Return errors for items whose bounds extend outside the page boundary."""
    errors: list[str] = []
    min_x, max_x = margin, page_width - margin
    min_y, max_y = margin, page_height - margin
    for item, bbox in zip(items, bounds, strict=True):
        bx_min, by_min, bx_max, by_max = bbox
        if bx_min < min_x or bx_max > max_x or by_min < min_y or by_max > max_y:
            errors.append(f"'{label_fn(item)}' extends outside page boundary")
    return errors


# ---------------------------------------------------------------------------
# Wire geometry checks: orthogonality, near-miss alignment, text/wire
# collision, and redundant routing jogs. Operate on `core.primitives.Line`/
# `Text` only -- no domain knowledge of breakers, tanks, or connectors.
# ---------------------------------------------------------------------------

_ZERO_LENGTH_TOLERANCE = 1e-9
_PASS_THROUGH_DEGREE = 2
_MIN_RAIL_OCCUPANCY = 2


@deal.pure
def check_orthogonal_wires(
    wires: list[Line], angle_tolerance_deg: float = 0.5
) -> list[str]:
    """Return warnings for wire segments that are not horizontal or vertical."""
    warnings: list[str] = []
    for wire in wires:
        dx = wire.end.x - wire.start.x
        dy = wire.end.y - wire.start.y
        length = math.hypot(dx, dy)
        if length < _ZERO_LENGTH_TOLERANCE:
            continue
        angle = math.degrees(math.atan2(dy, dx)) % 90
        deviation = min(angle, 90 - angle)
        if deviation > angle_tolerance_deg:
            warnings.append(
                f"Non-orthogonal wire from ({wire.start.x:.1f}, {wire.start.y:.1f}) to "
                f"({wire.end.x:.1f}, {wire.end.y:.1f}) deviates {deviation:.2f} deg "
                "from horizontal/vertical"
            )
    return warnings


@deal.pure
def check_near_alignment(points: list[Point], tolerance: float = 0.5) -> list[str]:
    """Return warnings for points close to, but not exactly on, a shared grid line.

    Grouped by alignment line rather than by pair, so one point drifting off
    an axis shared by several others produces one warning, not one per pair.
    """
    warnings: list[str] = []
    for axis, get in (("x", lambda p: p.x), ("y", lambda p: p.y)):
        counts: dict[float, int] = {}
        for p in points:
            v = get(p)
            counts[v] = counts.get(v, 0) + 1
        rails = sorted(v for v, c in counts.items() if c >= _MIN_RAIL_OCCUPANCY)
        flagged: set[float] = set()
        for p in points:
            v = get(p)
            if counts[v] >= _MIN_RAIL_OCCUPANCY or v in flagged:
                continue
            for rail in rails:
                delta = abs(v - rail)
                if _ZERO_LENGTH_TOLERANCE < delta <= tolerance:
                    warnings.append(
                        f"Point at {axis}={v:.3f} is {delta:.3f} mm off the "
                        f"{axis}={rail:.3f} alignment line"
                    )
                    flagged.add(v)
                    break
    return warnings


@deal.pure
def check_text_wire_collisions(wires: list[Line], texts: list[Text]) -> list[str]:
    """Return warnings for wire segments that cross a text label's bounding box."""
    warnings: list[str] = []
    for text in texts:
        box = text_bbox(text)
        warnings.extend(
            f"Wire from ({wire.start.x:.1f}, {wire.start.y:.1f}) to "
            f"({wire.end.x:.1f}, {wire.end.y:.1f}) crosses text {text.content!r}"
            for wire in wires
            if segment_intersects_bbox_interior((wire.start, wire.end), box)
        )
    return warnings


def _snap_key(p: Point, tol: float) -> tuple[float, float]:
    return (round(p.x / tol), round(p.y / tol))


def _chain_wires(wires: list[Line], join_tol: float = 1e-6) -> list[list[Line]]:
    """Group wires into polyline chains by shared endpoints, degree-aware.

    A chain only continues through a point where exactly two segment-ends
    meet (this wire's own end, plus exactly one other) -- a T-junction
    (degree >= 3, e.g. a bus tap) or a free end (degree == 1) always stops
    the chain, so two independent wires that merely touch at a junction are
    never fused into one fictitious path.
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


def _path_is_unobstructed(
    path: list[tuple[Point, Point]],
    obstacles: tuple[tuple[float, float, float, float], ...],
) -> bool:
    return not any(
        segment_intersects_bbox_interior(seg, box) for seg in path for box in obstacles
    )


@deal.pure
def check_redundant_jogs(
    wires: list[Line],
    obstacles: tuple[tuple[float, float, float, float], ...] = (),
) -> list[str]:
    """Return warnings for wire chains with more turns than their endpoints need.

    A chain's extra turns are only reported when at least one simpler
    (0-turn-if-collinear, else single-L-bend) route between its overall
    endpoints is provably unobstructed by `obstacles` (e.g. symbol
    footprints) -- a chain that legitimately routes around a component does
    not get flagged.
    """
    min_chain_length = 2
    baseline_turns = 1
    warnings: list[str] = []
    for chain in _chain_wires(wires):
        if len(chain) < min_chain_length:
            continue
        turns = 0
        for prev, nxt in itertools.pairwise(chain):
            prev_horiz = abs(prev.end.x - prev.start.x) > abs(prev.end.y - prev.start.y)
            next_horiz = abs(nxt.end.x - nxt.start.x) > abs(nxt.end.y - nxt.start.y)
            if prev_horiz != next_horiz:
                turns += 1
        if turns <= baseline_turns:
            continue

        start, end = chain[0].start, chain[-1].end
        candidates = _l_bend_candidates(start, end)
        if obstacles and not any(
            _path_is_unobstructed(c, obstacles) for c in candidates
        ):
            continue

        warnings.append(
            f"Wire chain from ({start.x:.1f}, {start.y:.1f}) to "
            f"({end.x:.1f}, {end.y:.1f}) has {turns} turns ({len(chain)} segments), "
            "more than the Manhattan minimum"
        )
    return warnings


def collect_wire_geometry(
    elements: list[Element],
) -> tuple[list[Line], list[Text], list[tuple[float, float, float, float]]]:
    """Split an element tree into top-level wires/labels vs. symbol obstacles.

    A `Symbol`'s interior `Line`s are fixed component glyph artwork (an IEC
    breaker's diagonal isolator blade, a fuse's crossed strokes) --
    legitimately non-orthogonal, not a wire defect. Only `Line`/`Text`
    reached without passing through a `Symbol` boundary count as wires/
    labels; each `Symbol` still contributes its bounding box as an obstacle
    for `check_redundant_jogs`.
    """
    wires: list[Line] = []
    texts: list[Text] = []
    obstacles: list[tuple[float, float, float, float]] = []

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
    return wires, texts, obstacles


def check_wire_geometry(
    elements: list[Element],
    *,
    angle_tolerance_deg: float = 0.5,
    align_tolerance: float = 0.5,
    extra_obstacles: tuple[tuple[float, float, float, float], ...] = (),
) -> list[str]:
    """Run all four wire-geometry checks against an element tree in one call.

    The single entry point placement/pagination engines should use: pass
    whatever `*BuildResult.circuit.elements` (or equivalent) they just
    produced and get back every orthogonality/collision/alignment/jog
    warning without needing to know the collection internals.
    """
    wires, texts, obstacles = collect_wire_geometry(elements)
    points = [w.start for w in wires] + [w.end for w in wires]
    return [
        *check_orthogonal_wires(wires, angle_tolerance_deg=angle_tolerance_deg),
        *check_text_wire_collisions(wires, texts),
        *check_near_alignment(points, tolerance=align_tolerance),
        *check_redundant_jogs(wires, obstacles=tuple(obstacles) + extra_obstacles),
    ]
