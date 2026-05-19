"""Tests for the PCB connector-pin square (pcb namespace)."""

from schematika.core.constants import GRID_SIZE
from schematika.pcb.symbols.connector_pin import (
    CONNECTOR_PIN_SIZE,
    connector_pin,
)


def test_size_is_half_of_grid_size_doubled() -> None:
    # Original connector_pin = 2 * GRID_SIZE = 10 mm; half = GRID_SIZE = 5 mm
    assert CONNECTOR_PIN_SIZE == GRID_SIZE


def test_has_single_port_named_1() -> None:
    sym = connector_pin()
    assert list(sym.ports.keys()) == ["1"]


def test_label_renders() -> None:
    sym = connector_pin(label="J1:1")
    contents = [getattr(el, "content", None) for el in sym.elements]
    assert "J1:1" in contents


def test_port_at_top_edge() -> None:
    """Port must be at local y=0 (top edge); body extends downward."""
    sym = connector_pin()
    port = sym.ports["1"]
    assert port.position.y == 0.0
    assert port.direction.dy < 0  # incoming from above


def test_body_entirely_below_port() -> None:
    """Every polygon/box point must have y >= port y (= 0)."""
    from schematika.core.primitives import Polygon

    sym = connector_pin()
    boxes = [el for el in sym.elements if isinstance(el, Polygon)]
    assert boxes, "Expected at least one box polygon"
    port_y = sym.ports["1"].position.y
    for poly in boxes:
        for pt in poly.points:
            assert pt.y >= port_y - 1e-9, f"Box point y={pt.y} is above port y={port_y}"
