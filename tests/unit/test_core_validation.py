"""Tests for core.validation helpers, specifically text_bbox rotation handling."""

from __future__ import annotations

import pytest

from schematika.core.geometry import Point, Style
from schematika.core.primitives import Text
from schematika.core.validation import boxes_overlap, text_bbox

_STYLE = Style(stroke="none", fill="black")


def _text(
    content: str,
    x: float,
    y: float,
    font_size: float = 10.0,
    anchor: str = "start",
    rotation: float = 0.0,
) -> Text:
    return Text(
        content=content,
        position=Point(x, y),
        style=_STYLE,
        anchor=anchor,
        font_size=font_size,
        rotation=rotation,
    )


class TestTextBboxNoRotation:
    def test_basic_start_anchor(self) -> None:
        t = _text("AB", x=0.0, y=10.0, font_size=10.0, anchor="start")
        x0, y0, x1, y1 = text_bbox(t)
        # width = 2 chars * 10 * 0.6 = 12, height = 1 line * 10 * 1.3 = 13
        assert x0 == pytest.approx(0.0)
        assert x1 == pytest.approx(12.0)
        assert y0 == pytest.approx(0.0)  # y - font_size = 10 - 10
        assert y1 == pytest.approx(13.0)  # y0 + height

    def test_middle_anchor(self) -> None:
        t = _text("AB", x=10.0, y=10.0, font_size=10.0, anchor="middle")
        x0, _y0, x1, _y1 = text_bbox(t)
        # x = 10 - 12/2 = 4
        assert x0 == pytest.approx(4.0)
        assert x1 == pytest.approx(16.0)

    def test_end_anchor(self) -> None:
        t = _text("AB", x=12.0, y=10.0, font_size=10.0, anchor="end")
        x0, _y0, x1, _y1 = text_bbox(t)
        assert x0 == pytest.approx(0.0)
        assert x1 == pytest.approx(12.0)


class TestTextBboxRotation:
    def test_90_degree_rotation_swaps_extents(self) -> None:
        """A 90-degree rotated text bbox width/height should be swapped vs 0-degree."""
        t0 = _text("ABCD", x=50.0, y=50.0, font_size=10.0, anchor="start", rotation=0.0)
        t90 = _text(
            "ABCD", x=50.0, y=50.0, font_size=10.0, anchor="start", rotation=90.0
        )

        x0_0, y0_0, x1_0, y1_0 = text_bbox(t0)
        x0_90, y0_90, x1_90, y1_90 = text_bbox(t90)

        unrot_w = x1_0 - x0_0
        unrot_h = y1_0 - y0_0
        rot_w = x1_90 - x0_90
        rot_h = y1_90 - y0_90

        # After 90-degree rotation, the rotated bbox width == unrotated height
        assert rot_w == pytest.approx(unrot_h, abs=1e-9)
        assert rot_h == pytest.approx(unrot_w, abs=1e-9)

    def test_neg90_degree_rotation(self) -> None:
        """-90-degree rotation should also swap extents like +90-degree."""
        t0 = _text("XYZ", x=20.0, y=20.0, font_size=5.0, anchor="start", rotation=0.0)
        t_neg = _text(
            "XYZ", x=20.0, y=20.0, font_size=5.0, anchor="start", rotation=-90.0
        )

        x0_0, y0_0, x1_0, y1_0 = text_bbox(t0)
        x0_n, y0_n, x1_n, y1_n = text_bbox(t_neg)

        unrot_w = x1_0 - x0_0
        unrot_h = y1_0 - y0_0
        rot_w = x1_n - x0_n
        rot_h = y1_n - y0_n

        assert rot_w == pytest.approx(unrot_h, abs=1e-9)
        assert rot_h == pytest.approx(unrot_w, abs=1e-9)

    def test_45_degree_rotation_enlarges_bbox(self) -> None:
        """A 45-degree rotated bbox must be larger than both original dimensions."""
        t0 = _text("ABCDE", x=0.0, y=0.0, font_size=10.0, anchor="start", rotation=0.0)
        t45 = _text(
            "ABCDE", x=0.0, y=0.0, font_size=10.0, anchor="start", rotation=45.0
        )

        x0_0, y0_0, x1_0, y1_0 = text_bbox(t0)
        x0_45, y0_45, x1_45, y1_45 = text_bbox(t45)

        unrot_w = x1_0 - x0_0
        unrot_h = y1_0 - y0_0
        rot_w = x1_45 - x0_45
        rot_h = y1_45 - y0_45

        # At 45-degree, both projected extents exceed the shorter original dimension
        assert rot_w > min(unrot_w, unrot_h)
        assert rot_h > min(unrot_w, unrot_h)

    def test_two_90deg_labels_at_different_x_do_not_overlap(self) -> None:
        """Vertical (90-degree) labels at pin_x values 10mm apart must not overlap.

        This is the real-world regression case: Q1_feedback_a / Q1_feedback_b.
        """
        label_a = _text(
            "Q1_feedback_a",
            x=10.0,
            y=30.0,
            font_size=2.0,
            anchor="start",
            rotation=90.0,
        )
        label_b = _text(
            "Q1_feedback_b",
            x=20.0,
            y=30.0,
            font_size=2.0,
            anchor="start",
            rotation=90.0,
        )

        bb_a = text_bbox(label_a)
        bb_b = text_bbox(label_b)

        assert not boxes_overlap(bb_a, bb_b), (
            f"Labels at x=10 and x=20 should not overlap; got {bb_a} vs {bb_b}"
        )
