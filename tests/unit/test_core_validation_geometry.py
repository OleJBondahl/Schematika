"""Tests for core.validation_geometry helpers."""

from schematika.core.geometry import Point
from schematika.core.validation_geometry import (
    segment_intersects_bbox_interior,
    segments_intersect_strict,
)


def _p(x: float, y: float) -> Point:
    return Point(x, y)


# ---------------------------------------------------------------------------
# segments_intersect_strict
# ---------------------------------------------------------------------------


class TestSegmentsIntersectStrict:
    def test_crossing_at_right_angles(self) -> None:
        # (+) shape: horizontal and vertical crossing in the middle
        a = (_p(0, 1), _p(2, 1))
        b = (_p(1, 0), _p(1, 2))
        assert segments_intersect_strict(a, b) is True

    def test_parallel_non_overlapping(self) -> None:
        a = (_p(0, 0), _p(2, 0))
        b = (_p(0, 1), _p(2, 1))
        assert segments_intersect_strict(a, b) is False

    def test_collinear_overlapping(self) -> None:
        # a covers [0,2], b covers [1,3] — interior overlap
        a = (_p(0, 0), _p(2, 0))
        b = (_p(1, 0), _p(3, 0))
        assert segments_intersect_strict(a, b) is True

    def test_collinear_non_overlapping(self) -> None:
        # a covers [0,1], b covers [2,3] — no contact
        a = (_p(0, 0), _p(1, 0))
        b = (_p(2, 0), _p(3, 0))
        assert segments_intersect_strict(a, b) is False

    def test_endpoint_touching_only(self) -> None:
        # Segments share exactly one endpoint — exempt
        a = (_p(0, 0), _p(1, 0))
        b = (_p(1, 0), _p(2, 0))
        assert segments_intersect_strict(a, b) is False

    def test_t_intersection(self) -> None:
        # Endpoint of b lands on interior of a
        a = (_p(0, 0), _p(4, 0))
        b = (_p(2, 0), _p(2, 3))
        assert segments_intersect_strict(a, b) is True

    def test_disjoint_diagonal(self) -> None:
        a = (_p(0, 0), _p(1, 1))
        b = (_p(2, 0), _p(3, 1))
        assert segments_intersect_strict(a, b) is False

    def test_same_segment(self) -> None:
        # Identical segments overlap fully
        a = (_p(0, 0), _p(1, 0))
        b = (_p(0, 0), _p(1, 0))
        assert segments_intersect_strict(a, b) is True

    def test_endpoint_inside_other(self) -> None:
        # b's start is in the interior of a
        a = (_p(0, 0), _p(10, 0))
        b = (_p(5, 0), _p(5, 5))
        assert segments_intersect_strict(a, b) is True


# ---------------------------------------------------------------------------
# segment_intersects_bbox_interior
# ---------------------------------------------------------------------------


class TestSegmentIntersectsBboxInterior:
    def test_segment_through_middle(self) -> None:
        bbox = (0.0, 0.0, 4.0, 4.0)
        seg = (_p(-1, 2), _p(5, 2))
        assert segment_intersects_bbox_interior(seg, bbox) is True

    def test_segment_outside(self) -> None:
        bbox = (0.0, 0.0, 4.0, 4.0)
        seg = (_p(5, 0), _p(5, 4))
        assert segment_intersects_bbox_interior(seg, bbox) is False

    def test_segment_just_touching_edge(self) -> None:
        # Endpoint exactly on the left edge — just touching, not interior
        bbox = (1.0, 0.0, 4.0, 4.0)
        seg = (_p(0, 2), _p(1, 2))
        assert segment_intersects_bbox_interior(seg, bbox) is False

    def test_segment_endpoint_inside(self) -> None:
        # One endpoint inside the bbox
        bbox = (0.0, 0.0, 4.0, 4.0)
        seg = (_p(-1, 2), _p(2, 2))
        assert segment_intersects_bbox_interior(seg, bbox) is True

    def test_segment_both_endpoints_inside(self) -> None:
        bbox = (0.0, 0.0, 4.0, 4.0)
        seg = (_p(1, 1), _p(3, 3))
        assert segment_intersects_bbox_interior(seg, bbox) is True

    def test_segment_diagonal_miss(self) -> None:
        bbox = (0.0, 0.0, 2.0, 2.0)
        seg = (_p(3, 0), _p(0, 3))
        assert segment_intersects_bbox_interior(seg, bbox) is True

    def test_segment_diagonal_miss_outside(self) -> None:
        # Segment misses the box entirely
        bbox = (2.0, 2.0, 4.0, 4.0)
        seg = (_p(0, 0), _p(1, 1))
        assert segment_intersects_bbox_interior(seg, bbox) is False
