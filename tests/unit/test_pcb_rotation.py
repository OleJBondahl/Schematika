"""Tests for rotation heuristic: entry port facing down triggers 180° rotation."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import _should_rotate


def _make_factory_with_entry_direction(entry_port: str, dy: float):
    """Factory whose entry_port has direction Vector(0, dy)."""

    def factory(label: str = "", **_kw) -> Symbol:
        port = Port(entry_port, Point(0, 0), Vector(0, dy))
        return Symbol(elements=[], ports={entry_port: port}, label=label)

    return factory


class TestShouldRotate:
    def test_entry_port_facing_up_no_rotation(self) -> None:
        """Port direction dy=-1 (upward) -> no rotation needed."""
        factory = _make_factory_with_entry_direction("1", dy=-1.0)
        assert _should_rotate(factory, "1") is False

    def test_entry_port_facing_down_needs_rotation(self) -> None:
        """Port direction dy=+1 (downward) -> rotation needed."""
        factory = _make_factory_with_entry_direction("1", dy=1.0)
        assert _should_rotate(factory, "1") is True

    def test_entry_port_zero_direction_no_rotation(self) -> None:
        """Port direction dy=0 -> dy > 0 is False -> no rotation."""
        factory = _make_factory_with_entry_direction("1", dy=0.0)
        assert _should_rotate(factory, "1") is False

    def test_unknown_port_no_rotation(self) -> None:
        """If the port name doesn't exist, return False (safe default)."""
        factory = _make_factory_with_entry_direction("1", dy=1.0)
        assert _should_rotate(factory, "nonexistent") is False


class TestRotationIntegration:
    def test_connector_pin_entry_port_is_downward(self) -> None:
        """connector_pin's port "1" faces down (dy=1) so would need rotation if used as entry."""
        from schematika.electrical.symbols import connector_pin

        sym = connector_pin()
        port = sym.ports["1"]
        assert port.direction.dy > 0

    def test_fuse_entry_port_1_faces_up(self) -> None:
        """fuse port '1' faces up (dy=-1) so no rotation needed when entry is '1'."""
        from schematika.electrical.symbols import fuse

        sym = fuse()
        port = sym.ports["1"]
        assert port.direction.dy < 0
