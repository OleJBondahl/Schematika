"""Deep tests for schematika.core.transform._rotate_path_d.

Wave-3 targets the 213 un-processed mutants in transform.py (IDs 340-552) which
all live inside `_rotate_path_d`, plus the processed survivors 313, 326, 328.

The strategy is exact-value numerical assertion on the emitted path-d string,
parsed back into tokens so we can compare rotated coordinates at 1e-9 tolerance.
"""

from __future__ import annotations

import math

import pytest

from schematika.core.geometry import Point
from schematika.core.transform import _rotate_path_d, tokenize_path_d

# --- helpers --------------------------------------------------------------


def _numbers(s: str) -> list[float]:
    """Extract all floats (in order) from a path-d string."""
    return [float(tok) for tok in tokenize_path_d(s) if not tok.isalpha()]


def _letters(s: str) -> list[str]:
    return [tok for tok in tokenize_path_d(s) if tok.isalpha()]


def _rot(angle_deg: float, x: float, y: float, cx: float = 0.0, cy: float = 0.0):
    c = math.cos(math.radians(angle_deg))
    s = math.sin(math.radians(angle_deg))
    tx, ty = x - cx, y - cy
    return tx * c - ty * s + cx, tx * s + ty * c + cy


def _assert_numbers_close(actual: list[float], expected: list[float]) -> None:
    assert len(actual) == len(expected), (
        f"expected {len(expected)} numbers, got {len(actual)}: {actual}"
    )
    for a, e in zip(actual, expected, strict=True):
        assert math.isclose(a, e, abs_tol=1e-9), f"{a} != {e}"


# --- M / L --------------------------------------------------------------


class TestMoveAndLine:
    def test_ml_90deg(self):
        # (1,0) -> (0,1) ; (2,0) -> (0,2)
        out = _rotate_path_d("M 1 0 L 2 0", 90, Point(0, 0))
        assert _letters(out) == ["M", "L"]
        _assert_numbers_close(_numbers(out), [0, 1, 0, 2])

    def test_ml_180deg(self):
        # (5,3) -> (-5,-3); (7,-2) -> (-7,2)
        out = _rotate_path_d("M 5 3 L 7 -2", 180, Point(0, 0))
        _assert_numbers_close(_numbers(out), [-5, -3, -7, 2])

    def test_ml_270deg(self):
        # (1,0) -> (0,-1)
        out = _rotate_path_d("M 1 0", 270, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, -1])

    def test_ml_45deg(self):
        r22 = math.sqrt(2) / 2
        out = _rotate_path_d("M 1 0 L 0 1", 45, Point(0, 0))
        _assert_numbers_close(_numbers(out), [r22, r22, -r22, r22])

    def test_around_non_origin_center(self):
        # center (5,5); point (10,5) -> relative (5,0) -> rotate 90 -> (0,5) -> back (5,10)
        out = _rotate_path_d("M 10 5", 90, Point(5, 5))
        _assert_numbers_close(_numbers(out), [5, 10])

    def test_negative_coordinates(self):
        out = _rotate_path_d("M -3 -4 L -1 -1", 90, Point(0, 0))
        # (-3,-4) -> (4,-3) ; (-1,-1) -> (1,-1)
        _assert_numbers_close(_numbers(out), [4, -3, 1, -1])

    def test_decimal_coordinates(self):
        out = _rotate_path_d("M 1.5 2.5", 180, Point(0, 0))
        _assert_numbers_close(_numbers(out), [-1.5, -2.5])

    def test_multiple_m_segments(self):
        """Sub-paths: two M commands in sequence."""
        out = _rotate_path_d("M 1 0 L 2 0 M 0 3 L 0 4", 90, Point(0, 0))
        # (1,0)->(0,1); (2,0)->(0,2); (0,3)->(-3,0); (0,4)->(-4,0)
        _assert_numbers_close(_numbers(out), [0, 1, 0, 2, -3, 0, -4, 0])

    def test_letters_preserved_in_order(self):
        out = _rotate_path_d("M 0 0 L 1 0 M 2 2 L 3 3", 90, Point(0, 0))
        assert _letters(out) == ["M", "L", "M", "L"]


# --- H / V convert to L ----------------------------------------------------


class TestHorizontalVertical:
    def test_h_converts_to_l_and_no_h_in_output(self):
        out = _rotate_path_d("M 0 0 H 10", 90, Point(0, 0))
        assert "H" not in _letters(out)

    def test_h_produces_l_command(self):
        out = _rotate_path_d("M 0 0 H 10", 90, Point(0, 0))
        assert "L" in _letters(out)

    def test_h_90deg_values(self):
        # M 0 0 H 10: last_y starts at 0, so we draw to (10, 0) rotated 90 -> (0, 10)
        out = _rotate_path_d("M 0 0 H 10", 90, Point(0, 0))
        nums = _numbers(out)
        # M pair (0,0), then rotated H target (0, 10)
        _assert_numbers_close(nums, [0, 0, 0, 10])

    def test_v_converts_to_l_and_no_v_in_output(self):
        out = _rotate_path_d("M 0 0 V 10", 90, Point(0, 0))
        assert "V" not in _letters(out)

    def test_v_produces_l_command(self):
        out = _rotate_path_d("M 0 0 V 10", 90, Point(0, 0))
        assert "L" in _letters(out)

    def test_v_90deg_values(self):
        # (0, 10) rotated 90° -> (-10, 0)
        out = _rotate_path_d("M 0 0 V 10", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, -10, 0])

    def test_h_uses_running_last_y(self):
        # After M 3 4, last_y=4. H 7 draws to (7, 4). Rotate 180° -> (-7, -4).
        out = _rotate_path_d("M 3 4 H 7", 180, Point(0, 0))
        _assert_numbers_close(_numbers(out), [-3, -4, -7, -4])

    def test_v_uses_running_last_x(self):
        # After M 3 4, last_x=3. V 9 draws to (3, 9). Rotate 180° -> (-3, -9).
        out = _rotate_path_d("M 3 4 V 9", 180, Point(0, 0))
        _assert_numbers_close(_numbers(out), [-3, -4, -3, -9])

    def test_h_chained_multiple_times(self):
        # H can take multiple x-values in sequence per SVG spec, but the
        # implementation treats only one at a time. M then multiple Hs.
        out = _rotate_path_d("M 0 0 H 5 H 10", 180, Point(0, 0))
        # First H: (5,0) -> (-5,0); last_x=5. Second H: (10, 0) -> (-10, 0).
        _assert_numbers_close(_numbers(out), [0, 0, -5, 0, -10, 0])


# --- C / S / Q / T ---------------------------------------------------------


class TestBezierAndCurves:
    def test_c_rotates_all_three_pairs(self):
        # C 1 0 2 0 3 0 rotated 90 -> 0,1 0,2 0,3
        out = _rotate_path_d("M 0 0 C 1 0 2 0 3 0", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, 0, 1, 0, 2, 0, 3])

    def test_c_letter_preserved(self):
        out = _rotate_path_d("M 0 0 C 1 0 2 0 3 0", 90, Point(0, 0))
        assert "C" in _letters(out)

    def test_s_rotates_two_pairs(self):
        out = _rotate_path_d("M 0 0 S 1 0 2 0", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, 0, 1, 0, 2])
        assert "S" in _letters(out)

    def test_q_rotates_two_pairs(self):
        out = _rotate_path_d("M 0 0 Q 1 0 2 0", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, 0, 1, 0, 2])
        assert "Q" in _letters(out)

    def test_t_rotates_one_pair(self):
        out = _rotate_path_d("M 0 0 T 1 0", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, 0, 1])
        assert "T" in _letters(out)

    def test_c_with_decimals_and_negatives(self):
        out = _rotate_path_d("M 0 0 C -1.5 2.5 3 -4 5 6", 180, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, 1.5, -2.5, -3, 4, -5, -6])


# --- Z command -------------------------------------------------------------


class TestZ:
    def test_z_upper_preserved_no_numbers(self):
        out = _rotate_path_d("M 0 0 L 1 0 Z", 90, Point(0, 0))
        assert "Z" in _letters(out)

    def test_lowercase_z_preserved(self):
        out = _rotate_path_d("M 0 0 L 1 0 z", 90, Point(0, 0))
        assert "z" in _letters(out)


# --- Relative (lowercase) commands pass through ---------------------------


class TestRelativeCommands:
    def test_relative_l_passes_through(self):
        out = _rotate_path_d("M 0 0 l 5 5", 90, Point(0, 0))
        assert "l" in _letters(out)
        # The 5s are passed through unchanged (they're deltas)
        # M pair is rotated: (0,0) -> (0,0); then 'l' 5 5 pass-through
        nums = _numbers(out)
        assert 5.0 in nums

    def test_relative_m_passes_through(self):
        """Lowercase m after absolute M — the lowercase m takes over cmd."""
        out = _rotate_path_d("M 0 0 m 1 2 l 3 4", 90, Point(0, 0))
        # Neither the m nor l numbers are rotated (they're relative deltas).
        # Only the initial M pair (0,0) is rotated.
        assert "m" in _letters(out)
        assert "l" in _letters(out)


# --- Round-trip identity --------------------------------------------------


class TestRoundTrip:
    def test_rotate_360_restores_values(self):
        # A 360° rotation in one shot should reproduce the original coords.
        d = "M 3 7 L 11 13 C 1 2 3 4 5 6"
        out = _rotate_path_d(d, 360, Point(0, 0))
        _assert_numbers_close(_numbers(out), [3, 7, 11, 13, 1, 2, 3, 4, 5, 6])

    def test_four_90_deg_rotations_restore_values(self):
        d = "M 3 7 L 11 13"
        r = d
        for _ in range(4):
            r = _rotate_path_d(r, 90, Point(0, 0))
        # After 4x90 degrees we're back to the start (within float tolerance).
        _assert_numbers_close(_numbers(r), [3, 7, 11, 13])

    def test_180_180_restores_values(self):
        d = "M -1.5 2.5 L 3.25 -4.75"
        out = _rotate_path_d(_rotate_path_d(d, 180, Point(0, 0)), 180, Point(0, 0))
        _assert_numbers_close(_numbers(out), [-1.5, 2.5, 3.25, -4.75])


# --- 0° identity ----------------------------------------------------------


class TestIdentityRotation:
    def test_zero_angle_leaves_coords_unchanged(self):
        out = _rotate_path_d("M 3 7 L 11 13", 0, Point(0, 0))
        _assert_numbers_close(_numbers(out), [3, 7, 11, 13])

    def test_empty_path_returns_empty(self):
        assert _rotate_path_d("", 90, Point(0, 0)).strip() == ""


# --- Separator tolerance (comma vs space) ---------------------------------


class TestTokenizer:
    def test_comma_separated_m(self):
        """SVG lets coords be comma-separated — the tokenizer must still find numbers."""
        out = _rotate_path_d("M1,0L2,0", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 1, 0, 2])

    def test_tight_no_space_between_letter_and_number(self):
        out = _rotate_path_d("M1 0L2 0", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 1, 0, 2])


# --- Incomplete pairs (defensive branches) -------------------------------


class TestIncompletePairs:
    def test_m_followed_by_letter_single_number_passes_through(self):
        """M with only one number before the next command — lone number passes through."""
        out = _rotate_path_d("M 5 L 1 0", 90, Point(0, 0))
        # The L pair (1,0) is rotated -> (~0, 1). The lone "5" falls into else branch.
        nums = _numbers(out)
        assert 5.0 in nums  # passed through unchanged
        # After rotation the L coords should include ~0 and ~1
        assert any(math.isclose(n, 1.0, abs_tol=1e-9) for n in nums)
        assert any(math.isclose(n, 0.0, abs_tol=1e-9) for n in nums)

    def test_c_interrupted_by_letter(self):
        """C with fewer than 3 pairs — break triggers."""
        # C 1 0 then "3" followed by "L": 1 pair consumed, then "3" passes through.
        out = _rotate_path_d("M 0 0 C 1 0 3 L 5 0", 90, Point(0, 0))
        assert "C" in _letters(out)
        assert "L" in _letters(out)
        # The L pair (5,0) is rotated: (0, 5)
        nums = _numbers(out)
        assert any(math.isclose(n, 5.0, abs_tol=1e-9) for n in nums)


# --- Complex mixed paths ---------------------------------------------------


class TestMixedPaths:
    def test_complex_path_all_letters_present(self):
        d = "M 0 0 L 5 0 H 10 V 10 C 10 5 5 10 0 10 Z"
        out = _rotate_path_d(d, 90, Point(0, 0))
        letters = _letters(out)
        assert "M" in letters
        assert "L" in letters  # original + 2 conversions
        assert "C" in letters
        assert "Z" in letters
        # H and V must be absent (converted to L)
        assert "H" not in letters
        assert "V" not in letters
        assert letters.count("L") >= 3

    def test_mixed_path_h_v_values_consistent(self):
        """Precise values through a mixed path at 90°.

        d = "M 0 0 H 5 V 7"
        After M 0 0: (0,0) -> (0,0)
        After H 5: draw to (5, 0); rotate 90 -> (0, 5). last_x=5.
        After V 7: draw to (5, 7); rotate 90 -> (-7, 5). last_y=7.
        """
        out = _rotate_path_d("M 0 0 H 5 V 7", 90, Point(0, 0))
        _assert_numbers_close(_numbers(out), [0, 0, 0, 5, -7, 5])


# --- Tokenizer standalone -------------------------------------------------


class TestTokenizePathD:
    def test_tokenize_ml(self):
        assert tokenize_path_d("M 1 0 L 2 0") == ["M", "1", "0", "L", "2", "0"]

    def test_tokenize_decimals(self):
        assert tokenize_path_d("M 1.5 -2.5") == ["M", "1.5", "-2.5"]

    def test_tokenize_handles_scientific_notation(self):
        toks = tokenize_path_d("M 1e3 2E-2")
        assert toks == ["M", "1e3", "2E-2"]

    def test_tokenize_no_spaces_between_numbers(self):
        # "M1,2" parses as M, 1, 2
        assert tokenize_path_d("M1,2") == ["M", "1", "2"]


# Keep pytest imported even if no parametrize used — makes future additions cheap.
_ = pytest
