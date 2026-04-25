"""Tests for schematika.core.svg_path: parse, serialize, translate_command."""

from __future__ import annotations

import pytest
from dirty_equals import IsApprox
from hypothesis import given, settings
from hypothesis import strategies as st

from schematika.core.svg_path import (
    Close,
    Curve,
    HLine,
    Line,
    Move,
    PassThrough,
    Quad,
    Smooth,
    Tangent,
    VLine,
    parse,
    serialize,
    translate_command,
)

# ---------------------------------------------------------------------------
# Per-command parse + serialize round-trip
# ---------------------------------------------------------------------------

_ROUND_TRIP_CASES = [
    ("M 1.0 2.0", (Move(1.0, 2.0),), "M 1.0 2.0"),
    ("L 3.0 4.0", (Line(3.0, 4.0),), "L 3.0 4.0"),
    ("H 5.0", (HLine(5.0),), "H 5.0"),
    ("V 6.0", (VLine(6.0),), "V 6.0"),
    (
        "C 1.0 2.0 3.0 4.0 5.0 6.0",
        (Curve(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),),
        "C 1.0 2.0 3.0 4.0 5.0 6.0",
    ),
    ("S 1.0 2.0 3.0 4.0", (Smooth(1.0, 2.0, 3.0, 4.0),), "S 1.0 2.0 3.0 4.0"),
    ("Q 1.0 2.0 3.0 4.0", (Quad(1.0, 2.0, 3.0, 4.0),), "Q 1.0 2.0 3.0 4.0"),
    ("T 1.0 2.0", (Tangent(1.0, 2.0),), "T 1.0 2.0"),
    ("M 1.0 2.0 Z", (Move(1.0, 2.0), Close("Z")), "M 1.0 2.0 Z"),
    ("M 1.0 2.0 z", (Move(1.0, 2.0), Close("z")), "M 1.0 2.0 z"),
    ("l 1 2", (PassThrough("l"), PassThrough("1"), PassThrough("2")), "l 1 2"),
    ("M 1,2", (Move(1.0, 2.0),), "M 1.0 2.0"),
]


@pytest.mark.parametrize(("d", "expected_cmds", "expected_ser"), _ROUND_TRIP_CASES)
def test_parse_round_trip(d, expected_cmds, expected_ser):
    cmds = parse(d)
    assert cmds == expected_cmds
    assert serialize(cmds) == expected_ser


# ---------------------------------------------------------------------------
# PassThrough round-trip
# ---------------------------------------------------------------------------


def test_passthrough_sequence_round_trips():
    cmds = (PassThrough("l"), PassThrough("5"), PassThrough("5"))
    assert serialize(cmds) == "l 5 5"


# ---------------------------------------------------------------------------
# Hypothesis: serialize → parse stability
# ---------------------------------------------------------------------------

_coord = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)

# Excludes PassThrough: arbitrary strings don't round-trip stably through
# parse → serialize → parse (the parser would re-tokenize the inner string).
_command_strategy = st.one_of(
    st.builds(Move, x=_coord, y=_coord),
    st.builds(Line, x=_coord, y=_coord),
    st.builds(HLine, x=_coord),
    st.builds(VLine, y=_coord),
    st.builds(Curve, x1=_coord, y1=_coord, x2=_coord, y2=_coord, x=_coord, y=_coord),
    st.builds(Smooth, x2=_coord, y2=_coord, x=_coord, y=_coord),
    st.builds(Quad, x1=_coord, y1=_coord, x=_coord, y=_coord),
    st.builds(Tangent, x=_coord, y=_coord),
    st.just(Close("Z")),
    st.just(Close("z")),
)


@given(st.lists(_command_strategy, min_size=1, max_size=10))
@settings(max_examples=200)
def test_serialize_parse_stability(cmds):
    """serialize then parse produces the same command sequence."""
    original = tuple(cmds)
    d = serialize(original)
    reparsed = parse(d)
    assert reparsed == original


# ---------------------------------------------------------------------------
# Hypothesis: translate_command inverse-translation cancels
# ---------------------------------------------------------------------------

_delta = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)

_coord_bounded = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
)

_command_strategy_bounded = st.one_of(
    st.builds(Move, x=_coord_bounded, y=_coord_bounded),
    st.builds(Line, x=_coord_bounded, y=_coord_bounded),
    st.builds(HLine, x=_coord_bounded),
    st.builds(VLine, y=_coord_bounded),
    st.builds(
        Curve,
        x1=_coord_bounded,
        y1=_coord_bounded,
        x2=_coord_bounded,
        y2=_coord_bounded,
        x=_coord_bounded,
        y=_coord_bounded,
    ),
    st.builds(
        Smooth, x2=_coord_bounded, y2=_coord_bounded, x=_coord_bounded, y=_coord_bounded
    ),
    st.builds(
        Quad, x1=_coord_bounded, y1=_coord_bounded, x=_coord_bounded, y=_coord_bounded
    ),
    st.builds(Tangent, x=_coord_bounded, y=_coord_bounded),
    st.just(Close("Z")),
)


def _approx(expected: float) -> IsApprox:
    """Return an IsApprox matcher for *expected* with abs delta 1e-9."""
    return IsApprox(expected, delta=1e-9)


@given(_command_strategy_bounded, _delta, _delta)
@settings(max_examples=200)
def test_translate_command_inverse_cancels(cmd, dx, dy):
    """translate(translate(cmd, dx, dy), -dx, -dy) ≈ cmd."""
    forward = translate_command(cmd, dx, dy)
    back = translate_command(forward, -dx, -dy)
    assert type(back) is type(cmd)
    match back:
        case Move(x, y):
            assert x == _approx(cmd.x)
            assert y == _approx(cmd.y)
        case Line(x, y):
            assert x == _approx(cmd.x)
            assert y == _approx(cmd.y)
        case HLine(x):
            assert x == _approx(cmd.x)
        case VLine(y):
            assert y == _approx(cmd.y)
        case Curve(x1, y1, x2, y2, x, y):
            assert x1 == _approx(cmd.x1)
            assert y1 == _approx(cmd.y1)
            assert x2 == _approx(cmd.x2)
            assert y2 == _approx(cmd.y2)
            assert x == _approx(cmd.x)
            assert y == _approx(cmd.y)
        case Smooth(x2, y2, x, y):
            assert x2 == _approx(cmd.x2)
            assert y2 == _approx(cmd.y2)
            assert x == _approx(cmd.x)
            assert y == _approx(cmd.y)
        case Quad(x1, y1, x, y):
            assert x1 == _approx(cmd.x1)
            assert y1 == _approx(cmd.y1)
            assert x == _approx(cmd.x)
            assert y == _approx(cmd.y)
        case Tangent(x, y):
            assert x == _approx(cmd.x)
            assert y == _approx(cmd.y)
        case _:
            assert back == cmd


# ---------------------------------------------------------------------------
# Equivalence table: new _translate_path_d must match old snapshot
# ---------------------------------------------------------------------------
# Snapshots from branch1 _translate_path_d before refactor (captured by
# claude-tools/snapshot_translate.py on 2026-04-25).

from schematika.core.transform import _translate_path_d  # noqa: E402

_EQUIVALENCE_TABLE = [
    ("M", "M 1 2", 10, 20, "M 11.0 22.0"),
    ("L", "L 3 4", 10, 20, "L 13.0 24.0"),
    ("H", "H 5", 10, 20, "H 15.0"),
    ("V", "V 6", 10, 20, "V 26.0"),
    ("C", "C 1 2 3 4 5 6", 10, 20, "C 11.0 22.0 13.0 24.0 15.0 26.0"),
    ("S", "S 1 2 3 4", 10, 20, "S 11.0 22.0 13.0 24.0"),
    ("Q", "Q 1 2 3 4", 10, 20, "Q 11.0 22.0 13.0 24.0"),
    ("T", "T 1 2", 10, 20, "T 11.0 22.0"),
    ("Z_upper", "M 1 2 Z", 10, 20, "M 11.0 22.0 Z"),
    ("z_lower", "M 1 2 z", 10, 20, "M 11.0 22.0 z"),
    ("relative_l", "l 1 2", 10, 20, "l 1 2"),
    ("comma_sep", "M 1,2", 10, 20, "M 11.0 22.0"),
    (
        "mixed",
        "M 0 0 L 5 3 H 10 V 8 C 1 2 3 4 5 6 S 1 2 3 4 Q 1 2 3 4 T 1 2 Z",
        5,
        10,
        "M 5.0 10.0 L 10.0 13.0 H 15.0 V 18.0 C 6.0 12.0 8.0 14.0 10.0 16.0 S 6.0 12.0 8.0 14.0 Q 6.0 12.0 8.0 14.0 T 6.0 12.0 Z",
    ),
    ("sci_notation", "M 1e1 2E1", 10, 20, "M 20.0 40.0"),
    ("no_space", "M1 2L3 4", 10, 20, "M 11.0 22.0 L 13.0 24.0"),
    ("zero_delta", "M 1 2 L 3 4", 0, 0, "M 1.0 2.0 L 3.0 4.0"),
    ("relative_m", "M 0 0 m 1 2", 10, 20, "M 10.0 20.0 m 1 2"),
]


@pytest.mark.parametrize(("label", "d", "dx", "dy", "expected"), _EQUIVALENCE_TABLE)
def test_equivalence_with_snapshot(label, d, dx, dy, expected):
    assert _translate_path_d(d, dx, dy) == expected, label


# ---------------------------------------------------------------------------
# Regression: orphan C arm emits no spurious Move commands (Fix 2)
# ---------------------------------------------------------------------------


def test_malformed_c_arm_no_spurious_move():
    """Incomplete C arm (orphan '3') round-trips with no spurious M tokens.

    Input:  "M 0 0 C 1 0 2 0 3 L 5 0"
    The C arm has only 5 numbers (needs 6); '3' is the orphan that aborts it.
    After translation by (10, 20):
    - M 0 0 → M 10.0 20.0
    - C 1 0 2 0 3 (broken) → round-trips as-is: "C 1 0 2 0 3"
    - L 5 0 → L 15.0 20.0
    No "M" marker must be inserted between C and L.
    """
    d = "M 0 0 C 1 0 2 0 3 L 5 0"
    result = _translate_path_d(d, 10, 20)
    assert "M 10.0 20.0" in result, f"translated M missing: {result!r}"
    assert "L 15.0 20.0" in result, f"translated L missing: {result!r}"
    # The broken C arm must survive unchanged, no spurious Move added
    assert result.count("M") == 1, f"spurious M marker: {result!r}"
    assert result == "M 10.0 20.0 C 1 0 2 0 3 L 15.0 20.0"
