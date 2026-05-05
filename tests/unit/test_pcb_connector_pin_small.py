"""Tests for the half-size PCB connector-pin square."""

from schematika.core.constants import GRID_SIZE
from schematika.pcb.symbols.connector_pin_small import (
    CONNECTOR_PIN_SMALL_SIZE,
    connector_pin_small,
)


def test_size_is_half_of_grid_size_doubled() -> None:
    # Original connector_pin = 2 * GRID_SIZE = 10 mm; half = GRID_SIZE = 5 mm
    assert CONNECTOR_PIN_SMALL_SIZE == GRID_SIZE


def test_has_single_port_named_1() -> None:
    sym = connector_pin_small()
    assert list(sym.ports.keys()) == ["1"]


def test_label_renders() -> None:
    sym = connector_pin_small(label="J1:1")
    contents = [getattr(el, "content", None) for el in sym.elements]
    assert "J1:1" in contents
