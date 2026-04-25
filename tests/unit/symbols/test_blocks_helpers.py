"""Characterisation tests for private block() helpers."""

import pytest

from schematika.core.exceptions import CircuitValidationError
from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port
from schematika.electrical.model.parts import standard_style
from schematika.electrical.symbols.blocks import (
    _compute_pin_x_positions,
    _make_alias_ports,
    _make_pin_side,
    _validate_pin_positions,
)


@pytest.mark.parametrize(
    ("pins", "explicit", "spacing", "expected"),
    [
        ((), None, 5.0, []),
        (("A",), None, 5.0, [0.0]),
        (("A", "B"), None, 5.0, [0.0, 5.0]),
        (("A", "B"), (1.0, 7.0), 5.0, [1.0, 7.0]),
    ],
)
def test_compute_pin_x_positions(pins, explicit, spacing, expected):
    assert _compute_pin_x_positions(pins, explicit, spacing) == expected


def test_validate_pin_positions_raises_on_length_mismatch():
    with pytest.raises(CircuitValidationError, match="top_pin_positions length"):
        _validate_pin_positions((1.0,), ("A", "B"), "top")


def test_validate_pin_positions_passes_when_none():
    _validate_pin_positions(None, ("A", "B"), "top")


def test_validate_pin_positions_passes_when_lengths_match():
    _validate_pin_positions((1.0, 2.0), ("A", "B"), "top")


@pytest.mark.parametrize(
    ("side", "expected_port_y_sign"),
    [
        ("top", -1),  # top pins point UP, port_y is negative
        (
            "bottom",
            +1,
        ),  # bottom pins point DOWN, port_y is positive box_height + pin_length
    ],
)
def test_make_pin_side_directionality(side, expected_port_y_sign):
    pins = ("A",)
    x_positions = [0.0]
    box_height = 20.0
    pin_length = 2.5
    style = standard_style()
    elements, ports = _make_pin_side(
        pins, x_positions, side, box_height, pin_length, style
    )
    assert "A" in ports
    if side == "top":
        assert ports["A"].position.y == -pin_length  # ports point up from box top
    else:
        assert (
            ports["A"].position.y == box_height + pin_length
        )  # ports point down from box bottom
    assert len(elements) >= 2  # at least line + text per pin


def test_make_pin_side_empty():
    elements, ports = _make_pin_side((), [], "top", 20.0, 2.5, standard_style())
    assert ports == {}
    assert elements == []


def test_make_alias_ports_top_assigns_odd_ids():
    existing = {
        "A": Port("A", Point(0, 0), Vector(0, -1)),
        "B": Port("B", Point(5, 0), Vector(0, -1)),
    }
    aliases = _make_alias_ports(("A", "B"), existing, parity_offset=1)
    assert "1" in aliases  # i=0, 0*2+1
    assert "3" in aliases  # i=1, 1*2+1
    assert aliases["1"].id == "1"


def test_make_alias_ports_bottom_assigns_even_ids():
    existing = {"X": Port("X", Point(0, 20), Vector(0, 1))}
    aliases = _make_alias_ports(("X",), existing, parity_offset=2)
    assert "2" in aliases  # i=0, 0*2+2


def test_make_alias_ports_skips_existing_collisions():
    # If "1" already exists in existing_ports, the alias should NOT be re-added
    existing = {
        "A": Port("A", Point(0, 0), Vector(0, -1)),
        "1": Port("1", Point(0, 0), Vector(0, -1)),  # pre-existing "1"
    }
    aliases = _make_alias_ports(("A",), existing, parity_offset=1)
    assert "1" not in aliases  # collision avoided
