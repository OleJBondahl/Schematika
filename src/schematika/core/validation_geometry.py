"""Geometry helpers for overlap/intersection checks."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from schematika.core.geometry import Point


def _cross(
    ox: float,
    oy: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Signed cross product of vectors OA and OB."""
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def _on_segment_strict(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    tolerance: float,
) -> bool:
    """True if (px, py) lies strictly in the interior of segment a-b.

    Strictly interior means not within *tolerance* of either endpoint.
    Caller must ensure p is collinear with a-b.
    """
    in_x = min(ax, bx) <= px <= max(ax, bx)
    in_y = min(ay, by) <= py <= max(ay, by)
    if not (in_x and in_y):
        return False
    near_a = abs(px - ax) <= tolerance and abs(py - ay) <= tolerance
    near_b = abs(px - bx) <= tolerance and abs(py - by) <= tolerance
    return not (near_a or near_b)


def _collinear_overlap(
    seg_a: tuple[float, float, float, float],
    seg_b: tuple[float, float, float, float],
    tolerance: float,
) -> bool:
    """True if two collinear segments have interior overlap (beyond tolerance).

    Each segment is (x1, y1, x2, y2).
    """
    p1x, p1y, p2x, p2y = seg_a
    p3x, p3y, p4x, p4y = seg_b
    if abs(p2x - p1x) > abs(p2y - p1y):
        lo = max(min(p1x, p2x), min(p3x, p4x))
        hi = min(max(p1x, p2x), max(p3x, p4x))
    else:
        lo = max(min(p1y, p2y), min(p3y, p4y))
        hi = min(max(p1y, p2y), max(p3y, p4y))
    return hi - lo > tolerance


def segments_intersect_strict(
    a: tuple[Point, Point],
    b: tuple[Point, Point],
    *,
    tolerance: float = 1e-6,
) -> bool:
    """True iff segments cross or overlap interior.

    Touching at a single shared endpoint returns False.
    """
    p1x, p1y = a[0].x, a[0].y
    p2x, p2y = a[1].x, a[1].y
    p3x, p3y = b[0].x, b[0].y
    p4x, p4y = b[1].x, b[1].y

    d1 = _cross(p3x, p3y, p4x, p4y, p1x, p1y)
    d2 = _cross(p3x, p3y, p4x, p4y, p2x, p2y)
    d3 = _cross(p1x, p1y, p2x, p2y, p3x, p3y)
    d4 = _cross(p1x, p1y, p2x, p2y, p4x, p4y)

    # General case: proper crossing (segments straddle each other)
    if (
        (d1 > tolerance and d2 < -tolerance) or (d1 < -tolerance and d2 > tolerance)
    ) and (
        (d3 > tolerance and d4 < -tolerance) or (d3 < -tolerance and d4 > tolerance)
    ):
        return True

    # Collinear case: both d1 and d2 near zero
    if abs(d1) <= tolerance and abs(d2) <= tolerance:
        return _collinear_overlap((p1x, p1y, p2x, p2y), (p3x, p3y, p4x, p4y), tolerance)

    # Endpoint-inside-other-segment cases
    return (
        (
            abs(d1) <= tolerance
            and _on_segment_strict(p1x, p1y, p3x, p3y, p4x, p4y, tolerance)
        )
        or (
            abs(d2) <= tolerance
            and _on_segment_strict(p2x, p2y, p3x, p3y, p4x, p4y, tolerance)
        )
        or (
            abs(d3) <= tolerance
            and _on_segment_strict(p3x, p3y, p1x, p1y, p2x, p2y, tolerance)
        )
        or (
            abs(d4) <= tolerance
            and _on_segment_strict(p4x, p4y, p1x, p1y, p2x, p2y, tolerance)
        )
    )


class _Bbox(NamedTuple):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def _outcode(self, x: float, y: float) -> int:
        code = 0
        if x < self.xmin:
            code |= 1
        elif x > self.xmax:
            code |= 2
        if y < self.ymin:
            code |= 4
        elif y > self.ymax:
            code |= 8
        return code


def _cs_clip_step(
    cx1: float,
    cy1: float,
    cx2: float,
    cy2: float,
    oc_out: int,
    box: _Bbox,
    tolerance: float,
) -> tuple[float, float] | None:
    """Single Cohen-Sutherland clip step. Returns new endpoint or None."""
    dx, dy = cx2 - cx1, cy2 - cy1
    if oc_out & 8:
        return (
            None
            if abs(dy) < tolerance
            else (cx1 + dx * (box.ymax - cy1) / dy, box.ymax)
        )
    if oc_out & 4:
        return (
            None
            if abs(dy) < tolerance
            else (cx1 + dx * (box.ymin - cy1) / dy, box.ymin)
        )
    if oc_out & 2:
        return (
            None
            if abs(dx) < tolerance
            else (box.xmax, cy1 + dy * (box.xmax - cx1) / dx)
        )
    return None if abs(dx) < tolerance else (box.xmin, cy1 + dy * (box.xmin - cx1) / dx)


def segment_intersects_bbox_interior(
    seg: tuple[Point, Point],
    bbox: tuple[float, float, float, float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    """True if segment passes through bbox interior.

    Endpoints landing exactly on edges return False (just-touching).
    Uses Cohen-Sutherland clipping; the clipped midpoint must be strictly
    inside the bbox.
    """
    box = _Bbox(*bbox)
    cx1, cy1 = seg[0].x, seg[0].y
    cx2, cy2 = seg[1].x, seg[1].y
    oc1 = box._outcode(cx1, cy1)
    oc2 = box._outcode(cx2, cy2)

    for _ in range(10):
        if not (oc1 | oc2):
            break
        if oc1 & oc2:
            return False
        oc_out = oc1 if oc1 else oc2
        pt = _cs_clip_step(cx1, cy1, cx2, cy2, oc_out, box, tolerance)
        if pt is None:
            return False
        if oc_out == oc1:
            cx1, cy1 = pt
            oc1 = box._outcode(cx1, cy1)
        else:
            cx2, cy2 = pt
            oc2 = box._outcode(cx2, cy2)

    clipped_len_sq = (cx2 - cx1) ** 2 + (cy2 - cy1) ** 2
    if clipped_len_sq <= tolerance**2:
        return False

    mx = (cx1 + cx2) / 2
    my = (cy1 + cy2) / 2
    return (
        box.xmin + tolerance < mx < box.xmax - tolerance
        or box.ymin + tolerance < my < box.ymax - tolerance
    )
