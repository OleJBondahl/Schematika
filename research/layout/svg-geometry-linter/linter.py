"""Deterministic geometry linter prototype for Schematika layouts.

Research spike for `docs/research/layout-improvement/svg-geometry-linter.md`.
NOT production code — throwaway prototype, lives entirely under
`research/layout/svg-geometry-linter/`, never imported by `src/schematika`.

Two entry points into the same checks:

1. `lint_elements(elements)` — walks Schematika's own pre-render geometry
   model (`Line`/`Text`/`Group`/`Symbol` from `schematika.core.primitives`
   and `schematika.core.symbol`), which is what `Circuit.elements` already
   holds before `render_system` serializes it to SVG.
2. `lint_svg_text(svg_source)` — regex-extracts `<line>`/`<text>` tags from
   a rendered SVG string, for comparison against the model-based path.

Both funnel into the same four checks and the same `Finding`/scalar-cost
shape, described in the findings doc.

Uses stdlib geometry only (no shapely) — see the findings doc for why.
"""

from __future__ import annotations

import math
import re
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
# Text bbox estimation.
#
# Schematika's own `core/bbox.py::_collect_points` explicitly does NOT
# compute text extent ("Text extent is not computed; use the anchor
# position only") -- see the comment there. That is a real gap this linter
# fills: without an estimated width, "text overlaps wire" can't be checked
# at all. This is a heuristic (avg glyph width for the Times New Roman
# metric the renderer uses), not exact metrics -- flagged as a limitation
# in the findings doc.
# ---------------------------------------------------------------------------

AVG_CHAR_WIDTH_EM = 0.52  # average glyph width as a fraction of font-size, Times-ish
TEXT_HEIGHT_EM = 0.72  # cap-height-ish fraction of font-size, used above/below baseline


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
            labels use to run parallel to a vertical wire). Neither
            Schematika's own `core/bbox.py::_collect_points` nor a naive
            axis-aligned estimate accounts for this -- omitting it makes
            every rotated wire label look like it overlaps the wire it
            labels, which is by design, not a defect. See the findings doc.

    Returns:
        Estimated axis-aligned bounding box in the same units as `position`,
        already accounting for `rotation`.
    """
    width = len(content) * font_size * AVG_CHAR_WIDTH_EM
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


def _segment_intersects_rect(seg: Seg, box: TextBox) -> bool:
    """True if `seg` crosses or touches the interior of `box` (Cohen-Sutherland-ish)."""
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
# minimum for its endpoints.
# ---------------------------------------------------------------------------


def _chain_wires(segments: list[Seg], join_tol: float = 1e-6) -> list[list[Seg]]:
    """Group segments into polyline chains by shared endpoints.

    This is a connectivity heuristic, not a net-aware router trace: it only
    knows "these segments touch," not "these belong to the same net." Two
    unrelated wires that happen to touch end-to-end will be chained together
    -- a known false-positive source, called out in the findings doc.
    """
    remaining = list(segments)
    chains: list[list[Seg]] = []

    def close(p: Pt, q: Pt) -> bool:
        return abs(p.x - q.x) <= join_tol and abs(p.y - q.y) <= join_tol

    while remaining:
        chain = [remaining.pop(0)]
        extended = True
        while extended:
            extended = False
            head, tail = chain[0].start, chain[-1].end
            for seg in list(remaining):
                if close(seg.start, tail):
                    chain.append(seg)
                    remaining.remove(seg)
                    extended = True
                elif close(seg.end, tail):
                    chain.append(Seg(seg.end, seg.start, seg.source))
                    remaining.remove(seg)
                    extended = True
                elif close(seg.end, head):
                    chain.insert(0, seg)
                    remaining.remove(seg)
                    extended = True
                elif close(seg.start, head):
                    chain.insert(0, Seg(seg.end, seg.start, seg.source))
                    remaining.remove(seg)
                    extended = True
        chains.append(chain)
    return chains


def check_redundant_jogs(segments: list[Seg]) -> list[Finding]:
    """Flag wire chains with more orthogonal turns than their endpoints need.

    The Manhattan-routing minimum between two points is 0 turns (already
    collinear), 1 turn (a single L-bend), or -- if going around something --
    more. This check has no obstacle model, so it can only flag chains with
    more than 1 turn as *candidates* for a redundant jog; it cannot confirm
    no obstacle justified the extra bends. Treat `warn` findings here as
    "worth a human look," not proven defects.

    Args:
        segments: Wire/line segments to group into chains and check.

    Returns:
        One `Finding` per chain whose turn count exceeds the 1-turn baseline.
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
        if turns > 1:
            start, end = chain[0].start, chain[-1].end
            mid = Pt((start.x + end.x) / 2, (start.y + end.y) / 2)
            findings.append(
                Finding(
                    kind="redundant_jog_candidate",
                    severity="info",
                    message=(
                        f"wire chain {start}->{end} ({len(chain)} segments, "
                        f"{turns} turns) exceeds the 1-turn Manhattan baseline"
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
        """Scalar cost = sum of finding weights. See the findings doc for how
        this could double as an optimizer objective."""
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
) -> LintReport:
    """Run all four checks and return a combined report.

    Args:
        segments: Wire/line segments extracted from the diagram.
        texts: Estimated text bounding boxes extracted from the diagram.
        angle_tol_deg: Passed through to `check_orthogonal`.
        align_tolerance: Passed through to `check_near_alignment`.

    Returns:
        A `LintReport` with every finding from all four checks.
    """
    points = [s.start for s in segments] + [s.end for s in segments]
    findings = [
        *check_orthogonal(segments, angle_tol_deg=angle_tol_deg),
        *check_text_wire_collisions(segments, texts),
        *check_near_alignment(points, tolerance=align_tolerance),
        *check_redundant_jogs(segments),
    ]
    return LintReport(findings=findings)


# ---------------------------------------------------------------------------
# Entry point 1: Schematika's pre-render geometry model.
# ---------------------------------------------------------------------------


def lint_elements(elements: list) -> LintReport:  # noqa: ANN001 -- schematika.core.geometry.Element, kept untyped so this file has zero import-time dependency on schematika
    """Lint a list of Schematika `Element`s (e.g. `Circuit.elements`).

    Walks `Group`/`Symbol` containers recursively, collecting `Line` and
    `Text` elements by structural type name (not `isinstance`, to avoid a
    hard import dependency from this standalone research file onto
    `schematika.core` -- see the module docstring).

    Only `Line`s that are NOT nested inside a `Symbol` are treated as wires
    for the orthogonality/redundant-jog checks. Symbol-interior `Line`s are
    fixed IEC 60617 glyph artwork (e.g. a breaker's diagonal isolator blade,
    a fuse's crossed "X" strokes) -- legitimately non-orthogonal by the
    standard itself, appended into `Circuit.elements` as a placed `Symbol`
    (see `electrical/symbols/breakers.py`), while actual connecting wires are
    `draw_wire()`'s `Line`s extended directly into `Circuit.elements`
    (`electrical/layout/layout.py`, `electrical/builder_phases.py:605`).
    Conflating the two was this prototype's first false-positive source --
    see the findings doc. `Text` (tags, pin numbers, wire labels) is
    collected everywhere, since a symbol's own tag label can legitimately
    crowd a neighboring wire.

    Args:
        elements: A flat list of Schematika core `Element` instances, e.g.
            `build_result.circuit.elements`.

    Returns:
        A `LintReport` covering every top-level wire and every text label
        found (including symbol-interior tags/pin numbers).
    """
    segments: list[Seg] = []
    texts: list[TextBox] = []

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
            for child in elem.elements:  # type: ignore[attr-defined]
                walk(child, inside_symbol=inside_symbol or cls_name == "Symbol")
        # Circle/Path/Polygon: out of scope for this prototype (see findings doc).

    for elem in elements:
        walk(elem, inside_symbol=False)

    return lint(segments, texts)


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
    Schematika already writes to disk, at the cost of two problems the
    model-based `lint_elements` doesn't have:

    1. Brittle to attribute-order/formatting changes in `core/renderer.py`'s
       output (this regex matches the exact attribute order Schematika
       currently emits, including the optional `transform="rotate(...)"`
       wire labels get).
    2. Structurally blind to "is this Line a connecting wire or part of a
       symbol's fixed IEC glyph artwork" -- that distinction only exists in
       the pre-render `Circuit.elements` tree (a `Symbol`'s nested `Line`s
       vs. top-level ones); by the time it's flattened into `<line>` tags,
       a breaker's diagonal isolator blade is indistinguishable from an
       actual wire. `lint_svg_text` therefore *cannot* apply the
       symbol-vs-wire filter `lint_elements` does -- see the findings doc
       for the resulting finding-count gap between the two entry points.

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
