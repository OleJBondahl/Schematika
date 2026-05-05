"""Hypothesis property tests for geometry invariants.

The third target (_pack_pages) was retired with the v1 pcb builder;
Phase 2 of the pcb rewrite will introduce a v2 pack_pages with its own
property test in test_pcb_pack_pages.py.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from schematika.core.geometry import Point
from schematika.core.transform import rotate_point, translate

_FINITE_COORD = st.floats(
    min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
)
_FINITE_ANGLE = st.floats(
    min_value=0.0, max_value=720.0, allow_nan=False, allow_infinity=False
)


@given(x=_FINITE_COORD, y=_FINITE_COORD, theta=_FINITE_ANGLE)
@settings(max_examples=200, deadline=None)
def test_rotate_point_roundtrip(x: float, y: float, theta: float) -> None:
    """rotate_point(rotate_point(p, θ), -θ) ≈ p."""
    p = Point(x, y)
    back = rotate_point(rotate_point(p, theta), -theta)
    assert math.isclose(back.x, p.x, abs_tol=1e-6)
    assert math.isclose(back.y, p.y, abs_tol=1e-6)


@given(
    x=_FINITE_COORD,
    y=_FINITE_COORD,
    a=st.integers(min_value=-1000, max_value=1000),
    b=st.integers(min_value=-1000, max_value=1000),
    c=st.integers(min_value=-1000, max_value=1000),
    d=st.integers(min_value=-1000, max_value=1000),
)
@settings(max_examples=200, deadline=None)
def test_translate_composition(
    x: float, y: float, a: int, b: int, c: int, d: int
) -> None:
    """translate(translate(p, a, b), c, d) ≈ translate(p, a+c, b+d)."""
    p = Point(x, y)
    step = translate(translate(p, a, b), c, d)
    once = translate(p, a + c, b + d)
    assert math.isclose(step.x, once.x, abs_tol=1e-9)
    assert math.isclose(step.y, once.y, abs_tol=1e-9)
