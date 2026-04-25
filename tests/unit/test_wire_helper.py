"""Tests for the wire() helper function."""

from schematika.electrical.layout.wire_labels import format_wire_specification
from schematika.electrical.wire import wire


def test_wire_returns_formatted_string():
    """wire() should match format_wire_specification()."""
    assert wire("RD", "2.5mm2") == format_wire_specification("RD", "2.5mm2")


def test_wire_empty_is_empty_string():
    """wire.EMPTY should be an empty string."""
    assert wire.EMPTY == ""


def test_wire_various_colors():
    """wire() should work with different color codes."""
    assert wire("BR", "2.5mm2") == "BR 2.5mm2"
    assert wire("BK", "0.5mm2") == "BK 0.5mm2"
    assert wire("GY", "2.5mm2") == "GY 2.5mm2"
    assert wire("WH", "0.5mm2") == "WH 0.5mm2"
    assert wire("RD", "1.5mm2") == "RD 1.5mm2"


def test_wire_color_only():
    """wire() with empty size should return just the color."""
    assert wire("RD", "") == "RD"


def test_wire_size_only():
    """wire() with empty color should return just the size."""
    assert wire("", "2.5mm2") == "2.5mm2"


def test_wire_importable_from_package():
    """wire should be importable from the advanced module."""
    from schematika.electrical.wire import wire as w

    assert w("RD", "2.5mm2") == "RD 2.5mm2"
