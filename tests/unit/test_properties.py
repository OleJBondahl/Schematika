"""Hypothesis property tests for three geometry + packing invariants.

Audit §3 flagged the suite as structural (isinstance / len >= N) and absent
of any property-based coverage. These three targets were named explicitly:
rotate_point, translate, _pack_pages.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from schematika.core.geometry import Point
from schematika.core.transform import rotate_point, translate
from schematika.pcb.builder import _Column, _pack_pages

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


_COLUMN = st.builds(
    _Column,
    key=st.from_regex(r"col_[0-9]{1,3}", fullmatch=True),
    placed_symbols=st.just(()),
    width_mm=st.integers(min_value=1, max_value=60).map(float),
    height_mm=st.just(50.0),
)


@given(columns=st.lists(_COLUMN, min_size=1, max_size=30, unique_by=lambda c: c.key))
@settings(max_examples=200, deadline=None)
def test_pack_pages_count_invariant(columns: list[_Column]) -> None:
    """Every column key appears in exactly one page."""
    pages = _pack_pages(columns, page_size=(297.0, 210.0), column_spacing_mm=5.0)
    packed = [k for _, keys in pages for k in keys]
    assert len(packed) == len(columns)
    assert set(packed) == {c.key for c in columns}
