"""Deterministic geometry linter, round 2 (deep dive).

Round 1 (`research/layout/svg-geometry-linter/linter.py`) built four checks
and found two real false positives (symbol-interior glyph lines mistaken for
wires, rotated wire-label bboxes computed as unrotated) which it fixed. This
file starts from that fixed baseline and closes the three gaps round 1
explicitly flagged as unresolved, per
`docs/research/layout-improvement/deepdive-svg-geometry-linter.md`:

1. `check_redundant_jogs` had no obstacle model and a chaining heuristic with
   a real bug (see `_chain_wires`'s docstring) that could silently weld two
   unrelated wire branches at a T-junction into one fictitious chain. Fixed
   with a degree-aware graph walk plus an obstacle-gated "is a simpler route
   actually available" check.
2. `check_text_wire_collisions`'s text-width estimate used one guessed
   constant (`AVG_CHAR_WIDTH_EM = 0.52`) for every character. Replaced with
   `CHAR_WIDTH_EM`, a per-glyph advance-width table calibrated from the
   actual Times New Roman font file Schematika's renderer names
   (`core/constants.py::TEXT_FONT_FAMILY`), via
   `calibrate_text_metrics.py` (fontTools, PEP 723, calibration-time only --
   never a runtime dependency of this module).
3. `LintReport.cost` is exercised for real by `optimizer_demo.py`, not just
   sketched.

Still stdlib-only at runtime (see round 1's dependency verdict -- shapely
and fontTools both stay confined to their respective one-off comparison/
calibration scripts).
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Minimal geometry types (deliberately not importing schematika.core.geometry
# so this prototype also works standalone against parsed SVG text).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pt:
    """A 2D point in diagram-space (mm)."""

    x: float
    y: float


@dataclass(frozen=True)
class Seg:
    """A wire/line segment between two points."""

    start: Pt
    end: Pt
    source: str = "line"  # free-text provenance for messages


@dataclass(frozen=True)
class TextBox:
    """A text element's estimated bounding box."""

    content: str
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass(frozen=True)
class Box:
    """A generic axis-aligned rectangle (e.g. a symbol's bounding box, used as
    an obstacle by `check_redundant_jogs`). Same shape as `TextBox` minus the
    `content` field -- `_segment_intersects_rect` only reads the four bounds,
    so both types are interchangeable wherever a rectangle is expected."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float


Severity = Literal["error", "warn", "info"]


@dataclass(frozen=True)
class Finding:
    """One linter finding."""

    kind: str
    severity: Severity
    message: str
    location: Pt
    weight: float  # contribution to the scalar cost function


# ---------------------------------------------------------------------------
# Text bbox estimation, calibrated against real font metrics.
#
# Schematika's own `core/bbox.py::_collect_points` explicitly does NOT
# compute text extent ("Text extent is not computed; use the anchor
# position only") -- see the comment there. That is a real gap this linter
# fills: without an estimated width, "text overlaps wire" can't be checked
# at all.
#
# CHAR_WIDTH_EM below is not a guess: it is the actual per-glyph advance
# width of "Times New Roman" (`core/constants.py::TEXT_FONT_FAMILY` /
# `TEXT_FONT_FAMILY_AUX` -- both literally that font), read from
# `C:\Windows\Fonts\times.ttf` via fontTools by
# `calibrate_text_metrics.py` and pasted here verbatim. Round 1 used one
# constant (`AVG_CHAR_WIDTH_EM = 0.52`) for every character; the real spread
# is large (space/digit glyphs are 0.25-0.5em, 'W' is 0.94em, 'I' is 0.33em)
# -- see the findings doc for the measured before/after delta on real
# Schematika label strings ("X1" was 17.5% too narrow under the old
# constant, "WWWW" was 81.5% too narrow, "IIII" was 36% too wide).
# ---------------------------------------------------------------------------

# fmt: off
CHAR_WIDTH_EM: dict[str, float] = {
    "0": 0.5, "1": 0.5, "2": 0.5, "3": 0.5, "4": 0.5,
    "5": 0.5, "6": 0.5, "7": 0.5, "8": 0.5, "9": 0.5,
    "A": 0.7222, "B": 0.667, "C": 0.667, "D": 0.7222, "E": 0.6108,
    "F": 0.5562, "G": 0.7222, "H": 0.7222, "I": 0.333, "J": 0.3892,
    "K": 0.7222, "L": 0.6108, "M": 0.8892, "N": 0.7222, "O": 0.7222,
    "P": 0.5562, "Q": 0.7222, "R": 0.667, "S": 0.5562, "T": 0.6108,
    "U": 0.7222, "V": 0.7222, "W": 0.9438, "X": 0.7222, "Y": 0.7222,
    "Z": 0.6108, " ": 0.25, "(": 0.333, ")": 0.333, "-": 0.333,
    ".": 0.25, "/": 0.2778, ":": 0.2778, "_": 0.5,
}
# fmt: on
DEFAULT_CHAR_WIDTH_EM = 0.5657  # avg of the table; fallback for e.g. lowercase

# Round 1's superseded uniform constant. Kept only as a labeled reference
# point for `test_synthetic_defects.py`'s before/after calibration tests and
# `optimizer_demo.py`'s reporting -- `estimate_text_bbox` no longer uses it.
AVG_CHAR_WIDTH_EM_OLD = 0.52

# hhea ascent for Times New Roman (0.8911em) -- replaces round 1's guessed
# TEXT_HEIGHT_EM = 0.72. Only the ascent side is modeled (matches
# `dominant_baseline="auto"`, the only value Schematika's renderer emits);
# descent (0.2163em) is not added because Schematika's real label content is
# uppercase tags/wire-codes/pin-IDs with no descenders ('g', 'y', 'p') --
# see the findings doc for why this is a documented scope choice, not an
# oversight.
TEXT_HEIGHT_EM = 0.8911


def estimate_text_bbox(
    content: str,
    position: Pt,
    font_size: float,
    anchor: str = "middle",
    dominant_baseline: str = "auto",
    rotation: float = 0.0,
) -> TextBox:
    """Estimate a text element's bounding box from its anchor and font size.

    Args:
        content: Rendered text.
        position: SVG anchor point (`x`, `y` attributes).
        font_size: Font size in mm (Schematika uses mm-equivalent units).
        anchor: SVG `text-anchor` ("start" | "middle" | "end").
        dominant_baseline: SVG `dominant-baseline`. Only "auto" (baseline at
            `position.y`) is distinguished from anything else (treated as
            centered on `position.y`); Schematika only emits "auto".
        rotation: Degrees the glyph is rotated about `position` (Schematika's
            `Text.rotation` / the SVG `transform="rotate(deg, x, y)"` wire
            labels use to run parallel to a vertical wire).

    Returns:
        Estimated axis-aligned bounding box in the same units as `position`,
        already accounting for `rotation`.
    """
    width = sum(CHAR_WIDTH_EM.get(ch, DEFAULT_CHAR_WIDTH_EM) for ch in content) * font_size
    if anchor == "start":
        min_x, max_x = position.x, position.x + width
    elif anchor == "end":
        min_x, max_x = position.x - width, position.x
    else:  # "middle"
        min_x, max_x = position.x - width / 2, position.x + width / 2

    half_h = font_size * TEXT_HEIGHT_EM
    if dominant_baseline == "auto":
        min_y, max_y = position.y - half_h, position.y
    else:
        min_y, max_y = position.y - half_h / 2, position.y + half_h / 2

    if rotation % 180 == 0:
        return TextBox(content=content, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)

    # Rotate the four un-rotated corners about `position` and take the
    # enclosing axis-aligned box of the result.
    theta = math.radians(rotation)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    corners = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    rotated_x: list[float] = []
    rotated_y: list[float] = []
    for cx, cy in corners:
        dx, dy = cx - position.x, cy - position.y
        rotated_x.append(position.x + dx * cos_t - dy * sin_t)
        rotated_y.append(position.y + dx * sin_t + dy * cos_t)

    return TextBox(
        content=content,
        min_x=min(rotated_x),
        max_x=max(rotated_x),
        min_y=min(rotated_y),
        max_y=max(rotated_y),
    )


# ---------------------------------------------------------------------------
# Check 1: non-orthogonal segments.
# ---------------------------------------------------------------------------


def check_orthogonal(segments: list[Seg], angle_tol_deg: float = 0.5) -> list[Finding]:
    """Flag wire segments that are not purely horizontal or vertical.

    Args:
        segments: Wire/line segments to check.
        angle_tol_deg: Maximum deviation from 0/90/180/270 degrees tolerated
            before flagging, to absorb floating-point noise.

    Returns:
        One `Finding` per non-orthogonal segment, weight proportional to the
        angular deviation (bigger tilt costs more).
    """
    findings: list[Finding] = []
    for seg in segments:
        dx = seg.end.x - seg.start.x
        dy = seg.end.y - seg.start.y
        length = math.hypot(dx, dy)
        if length < 1e-9:
            continue  # zero-length "segment" -- not a geometry defect
        angle = math.degrees(math.atan2(dy, dx)) % 90
        deviation = min(angle, 90 - angle)
        if deviation > angle_tol_deg:
            mid = Pt((seg.start.x + seg.end.x) / 2, (seg.start.y + seg.end.y) / 2)
            findings.append(
                Finding(
                    kind="non_orthogonal_wire",
                    severity="error",
                    message=(
                        f"{seg.source} segment {seg.start}->{seg.end} deviates "
                        f"{deviation:.2f} deg from horizontal/vertical"
                    ),
                    location=mid,
                    weight=deviation,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Check 2: text bounding box intersects a wire segment.
# ---------------------------------------------------------------------------


def _segment_intersects_rect(seg: Seg, box: TextBox | Box) -> bool:
    """True if `seg` crosses or touches the interior of `box` (Cohen-Sutherland-ish).

    `box` only needs `min_x`/`max_x`/`min_y`/`max_y` -- this works for both
    `TextBox` (text-collision check) and `Box` (obstacle-avoidance check)
    unchanged.
    """
    x0, y0, x1, y1 = seg.start.x, seg.start.y, seg.end.x, seg.end.y

    def outcode(x: float, y: float) -> int:
        code = 0
        if x < box.min_x:
            code |= 1
        elif x > box.max_x:
            code |= 2
        if y < box.min_y:
            code |= 4
        elif y > box.max_y:
            code |= 8
        return code

    oc0, oc1 = outcode(x0, y0), outcode(x1, y1)
    # Trivial accept: either endpoint inside the box.
    if oc0 == 0 or oc1 == 0:
        return True
    # Trivial reject: both endpoints share an "outside" side.
    if oc0 & oc1:
        return False
    # Clip iteratively (Cohen-Sutherland).
    while True:
        oc_out = oc0 or oc1
        if oc_out & 8:
            x = x0 + (x1 - x0) * (box.max_y - y0) / (y1 - y0)
            y = box.max_y
        elif oc_out & 4:
            x = x0 + (x1 - x0) * (box.min_y - y0) / (y1 - y0)
            y = box.min_y
        elif oc_out & 2:
            y = y0 + (y1 - y0) * (box.max_x - x0) / (x1 - x0)
            x = box.max_x
        else:  # oc_out & 1
            y = y0 + (y1 - y0) * (box.min_x - x0) / (x1 - x0)
            x = box.min_x
        if oc_out == oc0:
            x0, y0 = x, y
            oc0 = outcode(x0, y0)
        else:
            x1, y1 = x, y
            oc1 = outcode(x1, y1)
        if oc0 == 0 and oc1 == 0:
            return True
        if oc0 & oc1:
            return False


def check_text_wire_collisions(segments: list[Seg], texts: list[TextBox]) -> list[Finding]:
    """Flag wire segments that cross a text element's estimated bounding box.

    Args:
        segments: Wire/line segments to check.
        texts: Estimated text bounding boxes (see `estimate_text_bbox`).

    Returns:
        One `Finding` per (segment, text) collision.
    """
    findings: list[Finding] = []
    for seg in segments:
        for box in texts:
            if _segment_intersects_rect(seg, box):
                mid = Pt((seg.start.x + seg.end.x) / 2, (seg.start.y + seg.end.y) / 2)
                findings.append(
                    Finding(
                        kind="text_wire_collision",
                        severity="error",
                        message=(
                            f"wire {seg.start}->{seg.end} crosses text "
                            f"{box.content!r} bbox"
                        ),
                        location=mid,
                        weight=5.0,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Check 3: near-aligned but not exactly aligned endpoints ("almost on grid").
# ---------------------------------------------------------------------------


def check_near_alignment(points: list[Pt], tolerance: float = 0.5) -> list[Finding]:
    """Flag point pairs that are close on one axis but not exactly equal.

    A "pin pair" here is any two endpoints drawn from wire/port geometry.
    Two points at `dx == 0` (or `dy == 0`) exactly are considered correctly
    aligned and never flagged; small nonzero deltas below `tolerance` are the
    defect this check targets -- close enough to look aligned to a human
    eye/at print scale, far enough to not be exactly on-grid.

    Args:
        points: Candidate endpoints (deduplicated internally).
        tolerance: Maximum axis delta (mm) considered a near-miss.

    Returns:
        One `Finding` per near-miss pair, weight scaled by how close to
        "should be exact" the miss is (smaller delta -> more clearly a bug,
        not a coincidence -> higher weight).
    """
    findings: list[Finding] = []
    seen: set[tuple[float, float]] = set()
    unique = [p for p in points if (p.x, p.y) not in seen and not seen.add((p.x, p.y))]

    for i, a in enumerate(unique):
        for b in unique[i + 1 :]:
            dx = abs(a.x - b.x)
            dy = abs(a.y - b.y)
            # Vertically near-aligned (same-ish x) but not exact, on distinct y.
            if 1e-9 < dx <= tolerance and dy > 1e-9:
                findings.append(
                    _near_alignment_finding(a, b, dx, axis="x", tolerance=tolerance)
                )
            # Horizontally near-aligned (same-ish y) but not exact, on distinct x.
            if 1e-9 < dy <= tolerance and dx > 1e-9:
                findings.append(
                    _near_alignment_finding(a, b, dy, axis="y", tolerance=tolerance)
                )
    return findings


def _near_alignment_finding(a: Pt, b: Pt, delta: float, axis: str, tolerance: float) -> Finding:
    mid = Pt((a.x + b.x) / 2, (a.y + b.y) / 2)
    return Finding(
        kind="near_misaligned_pins",
        severity="warn",
        message=f"points {a} and {b} are {delta:.3f} mm off exact {axis}-alignment",
        location=mid,
        weight=(tolerance - delta) / tolerance * 2.0,
    )


# ---------------------------------------------------------------------------
# Check 4: redundant jogs -- a wire chain with more turns than the Manhattan
# minimum for its endpoints, now graph-based and obstacle-aware.
# ---------------------------------------------------------------------------


def _snap_key(p: Pt, tol: float) -> tuple[float, float]:
    """Bucket a point into a `tol`-sized grid cell for adjacency lookup."""
    return (round(p.x / tol), round(p.y / tol))


def _chain_wires(segments: list[Seg], join_tol: float = 1e-6) -> list[list[Seg]]:
    """Group segments into polyline chains by shared endpoints -- degree-aware.

    Round 1's version chained greedily: it captured `head`/`tail` once per
    `while extended` pass and then re-scanned the *entire* remaining list
    against that single stale tail. If two *different* segments both touched
    the same tail point (a real T-junction/bus-tap -- three or more wires
    meeting at one coordinate), the old loop's inner `for` didn't `break`
    after the first match, so **both** got appended to the same chain back
    to back, fabricating a `seg_a -> seg_b -> seg_c` path through a point
    that was actually a branch, not a bend. That fabricated path could then
    trip `check_redundant_jogs` on two logically unrelated wires that merely
    happened to meet -- exactly the false-positive risk round 1 flagged
    ("neither test circuit has two independent wires meeting collinearly at
    a shared point").

    Fix: build the point-degree of every snapped endpoint first. A chain may
    only continue through a point where the degree is *exactly* 2 (this
    segment's own endpoint, plus exactly one other) -- a real T-junction
    (degree >= 3) or a genuine free end (degree == 1) always stops the
    chain, never guesses which of several touching segments "continues" it.
    This still cannot prove two wires meeting end-to-end at a degree-2 point
    are the *same* logical wire (Schematika's `Line`/`Circuit.elements` has
    no net/wire identity to check against -- see the findings doc), but it
    eliminates the provably-wrong multi-branch-merge bug above, and pairs
    with `check_redundant_jogs`'s new obstacle gate so a false chain can at
    worst produce an "info" candidate that is itself proven avoidable, never
    a confident claim built on a broken chain.

    Args:
        segments: Wire/line segments to chain.
        join_tol: Endpoint coincidence tolerance (mm).

    Returns:
        List of chains (each a list of `Seg`, oriented head-to-tail).
    """
    live = [(i, s) for i, s in enumerate(segments) if math.hypot(s.end.x - s.start.x, s.end.y - s.start.y) > 1e-9]

    endpoints: dict[tuple[float, float], list[tuple[int, str]]] = defaultdict(list)
    for i, seg in live:
        endpoints[_snap_key(seg.start, join_tol)].append((i, "start"))
        endpoints[_snap_key(seg.end, join_tol)].append((i, "end"))
    degree = {key: len(v) for key, v in endpoints.items()}

    visited: set[int] = set()
    chains: list[list[Seg]] = []

    def other_unvisited(key: tuple[float, float]) -> tuple[int, str] | None:
        candidates = [(j, side) for j, side in endpoints[key] if j not in visited]
        return candidates[0] if len(candidates) == 1 else None

    for i, seg in live:
        if i in visited:
            continue
        visited.add(i)
        chain = [seg]

        # Extend forward from the tail while the tail point is a pass-through.
        while degree.get(_snap_key(chain[-1].end, join_tol), 0) == 2:
            found = other_unvisited(_snap_key(chain[-1].end, join_tol))
            if found is None:
                break
            j, side = found
            visited.add(j)
            nxt = segments[j]
            chain.append(nxt if side == "start" else Seg(nxt.end, nxt.start, nxt.source))

        # Extend backward from the head, symmetrically.
        while degree.get(_snap_key(chain[0].start, join_tol), 0) == 2:
            found = other_unvisited(_snap_key(chain[0].start, join_tol))
            if found is None:
                break
            j, side = found
            visited.add(j)
            prv = segments[j]
            chain.insert(0, prv if side == "end" else Seg(prv.end, prv.start, prv.source))

        chains.append(chain)
    return chains


def _l_bend_candidates(start: Pt, end: Pt) -> list[list[Seg]]:
    """The Manhattan-minimum candidate path(s) between two points.

    One 0-turn candidate if already collinear; otherwise the two possible
    single-L-bend candidates (bend first horizontally, or first vertically).
    """
    if abs(start.x - end.x) < 1e-9 or abs(start.y - end.y) < 1e-9:
        return [[Seg(start, end, "candidate")]]
    bend_h = Pt(end.x, start.y)
    bend_v = Pt(start.x, end.y)
    return [
        [Seg(start, bend_h, "candidate"), Seg(bend_h, end, "candidate")],
        [Seg(start, bend_v, "candidate"), Seg(bend_v, end, "candidate")],
    ]


def _path_is_unobstructed(path: list[Seg], obstacles: tuple[Box, ...]) -> bool:
    return not any(_segment_intersects_rect(seg, box) for seg in path for box in obstacles)


def check_redundant_jogs(segments: list[Seg], obstacles: tuple[Box, ...] = ()) -> list[Finding]:
    """Flag wire chains with more orthogonal turns than their endpoints need,
    *and* whose extra turns are not explained by any given obstacle.

    Round 1: no obstacle model at all -- ">1 turn" alone was reported as a
    "candidate," which fires just as readily on a chain that legitimately
    routes around a symbol as on one with a genuinely pointless jog. This
    version only reports a finding when at least one simpler
    (0-turn-if-collinear, else single-L-bend) candidate path between the
    chain's overall endpoints is provably unobstructed by any `obstacles`
    box (e.g. a symbol's bounding box) -- i.e. the router *could* have taken
    a simpler path and didn't, rather than merely "took more than one turn."

    Args:
        segments: Wire/line segments to group into chains and check.
        obstacles: Bounding boxes (e.g. symbol footprints) a simpler
            candidate route must avoid to count as "available." Empty by
            default (no obstacle awareness, matching round 1's behavior).

    Returns:
        One `Finding` per chain whose turn count exceeds the 1-turn baseline
        AND has a proven-unobstructed simpler alternative.
    """
    findings: list[Finding] = []
    for chain in _chain_wires(segments):
        if len(chain) < 2:
            continue
        turns = 0
        for prev, nxt in zip(chain, chain[1:], strict=False):
            prev_dx, prev_dy = prev.end.x - prev.start.x, prev.end.y - prev.start.y
            next_dx, next_dy = nxt.end.x - nxt.start.x, nxt.end.y - nxt.start.y
            prev_horiz = abs(prev_dx) > abs(prev_dy)
            next_horiz = abs(next_dx) > abs(next_dy)
            if prev_horiz != next_horiz:
                turns += 1
        if turns <= 1:
            continue

        start, end = chain[0].start, chain[-1].end
        candidates = _l_bend_candidates(start, end)
        if obstacles and not any(_path_is_unobstructed(c, obstacles) for c in candidates):
            continue  # every simpler route is blocked -- the extra turns are justified

        mid = Pt((start.x + end.x) / 2, (start.y + end.y) / 2)
        findings.append(
            Finding(
                kind="redundant_jog_candidate",
                severity="info",
                message=(
                    f"wire chain {start}->{end} ({len(chain)} segments, "
                    f"{turns} turns) exceeds the 1-turn Manhattan baseline"
                    + (" with an unobstructed simpler route available" if obstacles else "")
                ),
                location=mid,
                weight=float(turns - 1),
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Aggregate entry points.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LintReport:
    """All findings from one lint pass, plus the derived scalar cost."""

    findings: list[Finding]

    @property
    def cost(self) -> float:
        """Scalar cost = sum of finding weights. Used directly as the
        objective function in `optimizer_demo.py`."""
        return sum(f.weight for f in self.findings)

    def by_kind(self) -> dict[str, int]:
        """Count findings per `Finding.kind`, for a quick summary line."""
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        return counts


def lint(
    segments: list[Seg],
    texts: list[TextBox],
    *,
    angle_tol_deg: float = 0.5,
    align_tolerance: float = 0.5,
    obstacles: tuple[Box, ...] = (),
) -> LintReport:
    """Run all four checks and return a combined report.

    Args:
        segments: Wire/line segments extracted from the diagram.
        texts: Estimated text bounding boxes extracted from the diagram.
        angle_tol_deg: Passed through to `check_orthogonal`.
        align_tolerance: Passed through to `check_near_alignment`.
        obstacles: Passed through to `check_redundant_jogs`.

    Returns:
        A `LintReport` with every finding from all four checks.
    """
    points = [s.start for s in segments] + [s.end for s in segments]
    findings = [
        *check_orthogonal(segments, angle_tol_deg=angle_tol_deg),
        *check_text_wire_collisions(segments, texts),
        *check_near_alignment(points, tolerance=align_tolerance),
        *check_redundant_jogs(segments, obstacles=obstacles),
    ]
    return LintReport(findings=findings)


# ---------------------------------------------------------------------------
# Entry point 1: Schematika's pre-render geometry model.
# ---------------------------------------------------------------------------


def _bbox_of(elem: object) -> Box | None:
    """Compute an axis-aligned obstacle bbox for a `Symbol`/`Group` subtree.

    Mirrors `schematika.core.bbox._collect_points`'s coverage (Line, Circle,
    Text-anchor-only, Polygon; `Path` is not parsed here, matching round 1's
    documented scope limit) -- duck-typed by class name, not `isinstance`,
    to keep this file import-free from `schematika.core`.
    """
    points: list[tuple[float, float]] = []

    def collect(node: object) -> None:
        cls_name = type(node).__name__
        if cls_name == "Line":
            points.append((node.start.x, node.start.y))  # type: ignore[attr-defined]
            points.append((node.end.x, node.end.y))  # type: ignore[attr-defined]
        elif cls_name == "Circle":
            r = node.radius  # type: ignore[attr-defined]
            cx, cy = node.center.x, node.center.y  # type: ignore[attr-defined]
            points.append((cx - r, cy - r))
            points.append((cx + r, cy + r))
        elif cls_name == "Text":
            points.append((node.position.x, node.position.y))  # type: ignore[attr-defined]
        elif cls_name == "Polygon":
            points.extend((p.x, p.y) for p in node.points)  # type: ignore[attr-defined]
        elif cls_name in ("Group", "Symbol"):
            for child in node.elements:  # type: ignore[attr-defined]
                collect(child)

    collect(elem)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Box(min_x=min(xs), max_x=max(xs), min_y=min(ys), max_y=max(ys))


def lint_elements(elements: list, *, extra_obstacles: tuple[Box, ...] = ()) -> LintReport:  # noqa: ANN001 -- schematika.core.geometry.Element, kept untyped so this file has zero import-time dependency on schematika
    """Lint a list of Schematika `Element`s (e.g. `Circuit.elements` or
    `PIDDiagram.elements`).

    Walks `Group`/`Symbol` containers recursively, collecting `Line` and
    `Text` elements by structural type name (not `isinstance`, to avoid a
    hard import dependency from this standalone research file onto
    `schematika.core` -- see the module docstring). Every `Symbol`
    encountered also contributes its bounding box to `check_redundant_jogs`'s
    obstacle list -- a symbol footprint is real geometry a router had to (or
    should have) routed around.

    Only `Line`s that are NOT nested inside a `Symbol` are treated as wires
    for the orthogonality/redundant-jog checks. Symbol-interior `Line`s are
    fixed IEC 60617 glyph artwork (e.g. a breaker's diagonal isolator blade,
    a fuse's crossed "X" strokes) -- legitimately non-orthogonal by the
    standard itself. `Text` (tags, pin numbers, wire labels) is collected
    everywhere, since a symbol's own tag label can legitimately crowd a
    neighboring wire.

    Args:
        elements: A flat list of Schematika core `Element` instances, e.g.
            `build_result.circuit.elements` (electrical/pcb) or
            `pid_result.diagram.elements` (pid).

    Returns:
        A `LintReport` covering every top-level wire, every text label, and
        every symbol footprint (as an obstacle for the jog check).
    """
    segments: list[Seg] = []
    texts: list[TextBox] = []
    obstacles: list[Box] = []

    def walk(elem: object, *, inside_symbol: bool) -> None:
        cls_name = type(elem).__name__
        if cls_name == "Line":
            if inside_symbol:
                return  # symbol glyph artwork, not a wire -- see docstring
            start, end = elem.start, elem.end  # type: ignore[attr-defined]
            segments.append(Seg(Pt(start.x, start.y), Pt(end.x, end.y), source="Line"))
        elif cls_name == "Text":
            texts.append(
                estimate_text_bbox(
                    content=elem.content,  # type: ignore[attr-defined]
                    position=Pt(elem.position.x, elem.position.y),  # type: ignore[attr-defined]
                    font_size=elem.font_size,  # type: ignore[attr-defined]
                    anchor=elem.anchor,  # type: ignore[attr-defined]
                    dominant_baseline=elem.dominant_baseline,  # type: ignore[attr-defined]
                    rotation=elem.rotation,  # type: ignore[attr-defined]
                )
            )
        elif cls_name in ("Group", "Symbol"):
            if cls_name == "Symbol":
                box = _bbox_of(elem)
                if box is not None:
                    obstacles.append(box)
            for child in elem.elements:  # type: ignore[attr-defined]
                walk(child, inside_symbol=inside_symbol or cls_name == "Symbol")
        # Circle/Path/Polygon (top-level, outside a Symbol): out of scope for
        # this prototype's wire/text checks (see findings doc) -- but still
        # contribute to obstacle bboxes via `_bbox_of` when inside a Symbol.

    for elem in elements:
        walk(elem, inside_symbol=False)

    return lint(segments, texts, obstacles=tuple(obstacles) + extra_obstacles)


# ---------------------------------------------------------------------------
# Entry point 2: raw rendered SVG text (regex extraction, no XML parser dep).
# ---------------------------------------------------------------------------

_LINE_RE = re.compile(
    r'<line\s+x1="([\d.\-]+)"\s+y1="([\d.\-]+)"\s+x2="([\d.\-]+)"\s+y2="([\d.\-]+)"'
)
_TEXT_RE = re.compile(
    r'<text\s+x="([\d.\-]+)"\s+y="([\d.\-]+)"\s+text-anchor="(\w+)"\s+'
    r'dominant-baseline="([\w-]+)"\s+font-size="([\d.\-]+)"'
    r'(?:\s+transform="rotate\(([\d.\-]+)[^)]*\)")?[^>]*>([^<]*)</text>'
)


def lint_svg_text(svg_source: str, **lint_kwargs: float) -> LintReport:
    """Lint a rendered SVG string by regex-extracting `<line>`/`<text>` tags.

    This is the "no access to internals" path: it only needs the final SVG
    Schematika already writes to disk, at the cost of the structural
    blindness documented in round 1's findings doc (cannot distinguish a
    symbol's glyph line from a real wire, and has no way to build an
    obstacle list for `check_redundant_jogs` either -- both need the
    pre-render `Symbol` boundary this path doesn't have).

    Args:
        svg_source: Full SVG document text.
        **lint_kwargs: Forwarded to `lint()` (`angle_tol_deg`, `align_tolerance`).

    Returns:
        A `LintReport` covering every `<line>` and `<text>` tag matched.
    """
    segments = [
        Seg(Pt(float(x1), float(y1)), Pt(float(x2), float(y2)), source="<line>")
        for x1, y1, x2, y2 in _LINE_RE.findall(svg_source)
    ]
    texts = [
        estimate_text_bbox(
            content=content,
            position=Pt(float(x), float(y)),
            font_size=float(font_size),
            anchor=anchor,
            dominant_baseline=baseline,
            rotation=float(rotation) if rotation else 0.0,
        )
        for x, y, anchor, baseline, font_size, rotation, content in _TEXT_RE.findall(
            svg_source
        )
    ]
    return lint(segments, texts, **lint_kwargs)


# ---------------------------------------------------------------------------
# Single-call convenience wrapper -- the calling convention placement/
# pagination engines should use (see "Integration awareness" in the
# findings doc).
# ---------------------------------------------------------------------------


def _collect_line_ids(elem: object, ids: set[int]) -> None:
    """Recursively collect `id()` of every `Line` reachable from `elem`."""
    cls_name = type(elem).__name__
    if cls_name == "Line":
        ids.add(id(elem))
    elif cls_name in ("Group", "Symbol"):
        for child in elem.elements:  # type: ignore[attr-defined]
            _collect_line_ids(child, ids)


def lint_pid_diagram(diagram: object) -> LintReport:
    """Lint a `pid.PIDDiagram` -- NOT just `lint_elements(diagram.elements)`.

    Real, structural gap found by testing round 2 against a `pid` circuit
    (round 1 only tested `electrical`): `PIDBuilder.build()` flattens every
    placed equipment `Symbol`'s children directly into `diagram.elements`
    (`pid/builder.py:459-465`: `diagram.elements.extend(sym.elements)`), NOT
    `diagram.elements.append(sym)` the way `electrical/system/system.py:54`
    does. Round 1's entire "don't treat symbol-interior Lines as wires" fix
    -- the thing that got `lint_elements` to 0 false positives on
    `electrical` -- relies on the `Symbol` wrapper still being there to
    recurse into with `inside_symbol=True`. For `pid`, that wrapper is gone
    by the time `diagram.elements` exists: a tank's rectangular outline, a
    heat exchanger's internal U-tube pass lines, are bare top-level `Line`s
    indistinguishable from a real pipe. Concretely: a single lone `tank`
    equipment with zero pipes produces a spurious
    `redundant_jog_candidate` from `lint_elements(diagram.elements)` --
    the tank's own 4-line rectangular outline chains into a closed loop and
    trips the >1-turn check. See the findings doc for the full before/after.

    Workaround (not a `pid/builder.py` production fix -- out of scope for
    this research spike): `diagram.equipment` still holds each placed
    equipment as an un-flattened `Symbol` (`build()` appends to both
    `diagram.equipment` AND flattens into `diagram.elements` from the SAME
    `Symbol` object, so the `Line`s are identical objects, not copies).
    Every `Line` reachable from any `diagram.equipment` entry is excluded
    from the wire population before linting, and each equipment's bounding
    box is fed to `check_redundant_jogs` as an obstacle -- restoring both
    things `lint_elements`'s `Symbol`-boundary walk would have given it for
    free if `pid` didn't flatten.

    Args:
        diagram: A `pid.diagram.PIDDiagram` (or anything with `.equipment`
            and `.elements` in that shape).

    Returns:
        A `LintReport` with equipment-glyph contamination removed from the
        wire/jog checks.
    """
    equipment = list(getattr(diagram, "equipment", []))
    equipment_line_ids: set[int] = set()
    obstacles: list[Box] = []
    for sym in equipment:
        _collect_line_ids(sym, equipment_line_ids)
        box = _bbox_of(sym)
        if box is not None:
            obstacles.append(box)

    wire_elements = [
        e
        for e in diagram.elements  # type: ignore[attr-defined]
        if not (type(e).__name__ == "Line" and id(e) in equipment_line_ids)
    ]
    return lint_elements(wire_elements, extra_obstacles=tuple(obstacles))


def lint_build_result(result: object) -> LintReport:
    """Lint any Schematika `*BuildResult` in one call.

    Accepts `electrical.BuildResult` (`.circuit.elements`, via
    `lint_elements` -- `electrical` preserves `Symbol` boundaries, so no
    workaround is needed), `pid.PIDBuildResult` (`.diagram`, via
    `lint_pid_diagram` -- see that function's docstring for why `pid` needs
    different handling), or anything else exposing an `.elements` list
    directly -- duck-typed, so callers never need to know which domain
    produced the result. This is the one function `grid-astar-router` and
    `pagination-partitioner` should call; see the findings doc for why round
    1's two-step "get `.circuit.elements`, then call `lint_elements`" wasn't
    quite a single call, and why `pid` specifically needs more than that
    single step even now.
    """
    if hasattr(result, "circuit"):
        return lint_elements(result.circuit.elements)  # type: ignore[attr-defined]
    if hasattr(result, "diagram"):
        return lint_pid_diagram(result.diagram)  # type: ignore[attr-defined]
    return lint_elements(result.elements)  # type: ignore[attr-defined]
