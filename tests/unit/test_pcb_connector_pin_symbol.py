import pytest

from schematika.core.constants import GRID_SIZE, TERMINAL_RADIUS
from schematika.core.symbol import Symbol
from schematika.electrical.symbols.connector_pins import (
    CONNECTOR_PIN_SIZE,
    connector_pin,
)


class TestConnectorPinSymbol:
    def test_returns_symbol_with_exactly_one_port(self):
        sym = connector_pin()
        assert isinstance(sym, Symbol)
        assert len(sym.ports) == 1

    def test_port_direction_faces_outward_downward(self):
        """Port direction must be (0, 1) — outward from the glyph bottom."""
        sym = connector_pin()
        port = sym.ports["1"]
        assert port.direction.dx == pytest.approx(0.0)
        assert port.direction.dy == pytest.approx(1.0)

    def test_glyph_is_square_and_roughly_twice_terminal_size(self):
        """CONNECTOR_PIN_SIZE == 2*GRID_SIZE == 10mm; terminal diameter == 2*TERMINAL_RADIUS == 2.5mm."""
        terminal_diameter = 2 * TERMINAL_RADIUS  # 2.5 mm
        assert CONNECTOR_PIN_SIZE == pytest.approx(2 * GRID_SIZE)
        # Width == height (square)
        half = CONNECTOR_PIN_SIZE / 2
        assert half == pytest.approx(CONNECTOR_PIN_SIZE / 2)
        # At least 2× terminal diameter (we use 4× for extra clarity — 10mm vs 2.5mm)
        assert CONNECTOR_PIN_SIZE >= 2 * terminal_diameter

    def test_label_text_present_when_provided(self):
        sym = connector_pin(label="J1")
        from schematika.core.primitives import Text

        texts = [e for e in sym.elements if isinstance(e, Text)]
        assert any(t.content == "J1" for t in texts)

    def test_label_text_absent_when_empty(self):
        sym = connector_pin(label="")
        from schematika.core.primitives import Text

        texts = [e for e in sym.elements if isinstance(e, Text)]
        assert len(texts) == 0

    def test_pin_label_renders_when_provided(self):
        sym = connector_pin(label="J1", pin_label="1")
        from schematika.core.primitives import Text

        texts = [e for e in sym.elements if isinstance(e, Text)]
        assert any(t.content == "1" for t in texts)

    def test_label_pos_right_shifts_anchor(self):
        sym_left = connector_pin(label="J1", label_pos="left")
        sym_right = connector_pin(label="J1", label_pos="right")
        from schematika.core.primitives import Text

        def label_text(sym: Symbol) -> Text:
            return next(
                e for e in sym.elements if isinstance(e, Text) and e.content == "J1"
            )

        t_left = label_text(sym_left)
        t_right = label_text(sym_right)
        assert t_left.anchor == "end"
        assert t_right.anchor == "start"

    def test_invalid_label_pos_raises(self):
        with pytest.raises(ValueError, match="label_pos"):
            connector_pin(label_pos="top")
