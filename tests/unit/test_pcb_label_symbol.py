"""Tests for the internal _label_symbol factory and _placed_symbol_for_net_terminator.

Wave 3 survivors covered:
  - 65, 66, 67, 68, 69, 70: Port id "1", Point(0,0), Vector(0,-1) of the label port.
  - 72, 73: Text position Point(0, 5.0).
  - 74, 75: Text style stroke="none", fill="black".
  - 76:     Text anchor="middle".
  - 77:     Text font_size=3.0.
  - 79:     Symbol ports dict key "1".
"""

import pytest

from schematika.core.geometry import Point, Vector
from schematika.core.primitives import Text
from schematika.core.symbol import Symbol
from schematika.pcb.builder import _label_symbol, _label_symbol_factory


class TestLabelSymbolPort:
    def test_has_single_port_named_1(self) -> None:
        sym = _label_symbol("foo")
        assert list(sym.ports.keys()) == ["1"]

    def test_port_id_is_string_1(self) -> None:
        sym = _label_symbol("foo")
        assert sym.ports["1"].id == "1"

    def test_port_position_is_origin(self) -> None:
        sym = _label_symbol("foo")
        port = sym.ports["1"]
        assert port.position == Point(0, 0)

    def test_port_position_x_exactly_zero(self) -> None:
        sym = _label_symbol("foo")
        assert sym.ports["1"].position.x == 0

    def test_port_position_y_exactly_zero(self) -> None:
        sym = _label_symbol("foo")
        assert sym.ports["1"].position.y == 0

    def test_port_direction_is_0_minus_1(self) -> None:
        sym = _label_symbol("foo")
        port = sym.ports["1"]
        assert port.direction == Vector(0, -1)

    def test_port_direction_dx_is_zero(self) -> None:
        sym = _label_symbol("foo")
        assert sym.ports["1"].direction.dx == 0

    def test_port_direction_dy_is_minus_one(self) -> None:
        """Direction dy must be exactly -1 (faces up in SVG coords)."""
        sym = _label_symbol("foo")
        assert sym.ports["1"].direction.dy == -1


class TestLabelSymbolText:
    def _text(self, sym: Symbol) -> Text:
        return next(e for e in sym.elements if isinstance(e, Text))

    def test_contains_a_text_element(self) -> None:
        sym = _label_symbol("net42")
        texts = [e for e in sym.elements if isinstance(e, Text)]
        assert len(texts) == 1

    def test_text_content_is_the_input(self) -> None:
        sym = _label_symbol("net42")
        assert self._text(sym).content == "net42"

    def test_text_position_is_0_5(self) -> None:
        """Text anchor sits at (0, 5.0) — 5 mm below the port."""
        sym = _label_symbol("x")
        assert self._text(sym).position == Point(0, 5.0)

    def test_text_position_x_exactly_zero(self) -> None:
        sym = _label_symbol("x")
        assert self._text(sym).position.x == 0

    def test_text_position_y_exactly_5(self) -> None:
        sym = _label_symbol("x")
        assert self._text(sym).position.y == 5.0

    def test_text_style_stroke_is_none(self) -> None:
        sym = _label_symbol("x")
        assert self._text(sym).style.stroke == "none"

    def test_text_style_fill_is_black(self) -> None:
        sym = _label_symbol("x")
        assert self._text(sym).style.fill == "black"

    def test_text_anchor_is_middle(self) -> None:
        sym = _label_symbol("x")
        assert self._text(sym).anchor == "middle"

    def test_text_font_size_is_3(self) -> None:
        sym = _label_symbol("x")
        assert self._text(sym).font_size == 3.0


class TestLabelSymbolWhole:
    def test_label_equals_input(self) -> None:
        sym = _label_symbol("my_net")
        assert sym.label == "my_net"

    def test_factory_returns_zero_arg_callable(self) -> None:
        factory = _label_symbol_factory("v24")
        sym = factory()
        assert isinstance(sym, Symbol)
        assert sym.label == "v24"

    def test_factory_accepts_and_ignores_args(self) -> None:
        """The factory must accept *args, **kwargs (CircuitBuilder passes label=...)."""
        factory = _label_symbol_factory("v24")
        sym = factory("foo", label="bar", pin_label="p")
        assert sym.label == "v24"


class TestPlacedSymbolForNetTerminator:
    """Covers mutants 87, 88, 89, 90, 91, 92, 93 on _placed_symbol_for_net_terminator."""

    def _make_mapping_with_power(self, factory):
        from schematika.pcb.model import PowerNetMap, SymbolMapping

        return SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="v24", symbol=factory),),
        )

    def _one_port_factory(self):
        def factory(label: str = "", **_kw) -> Symbol:
            from schematika.core.symbol import Port

            port = Port("1", Point(0, 0), Vector(0, -1))
            return Symbol(elements=[], ports={"1": port}, label=label)

        return factory

    def test_power_net_placed_symbol_has_pwr_part_ref(self) -> None:
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )

        net = SimpleNamespace(name="v24", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        factory = self._one_port_factory()
        mapping = self._make_mapping_with_power(factory)
        ps = _placed_symbol_for_net_terminator(t, mapping)
        assert ps.part_ref == "pwr_v24"

    def test_power_net_placed_symbol_tag_prefix_is_pwr(self) -> None:
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )

        net = SimpleNamespace(name="v24", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        mapping = self._make_mapping_with_power(self._one_port_factory())
        ps = _placed_symbol_for_net_terminator(t, mapping)
        assert ps.tag_prefix == "PWR"

    def test_power_net_placed_symbol_not_rotated(self) -> None:
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )

        net = SimpleNamespace(name="v24", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        mapping = self._make_mapping_with_power(self._one_port_factory())
        ps = _placed_symbol_for_net_terminator(t, mapping)
        assert ps.rotated is False

    def test_power_symbol_selected_only_when_net_name_equals(self) -> None:
        """Mutant 87 flips == to !=. With == the correct branch triggers."""
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )

        # net.name == "v24" matches the single PowerNetMap entry.
        net = SimpleNamespace(name="v24", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        mapping = self._make_mapping_with_power(self._one_port_factory())
        ps = _placed_symbol_for_net_terminator(t, mapping)
        # If == were replaced by != the POWER branch would miss and we'd
        # fall through to the LABEL branch, producing "lbl_v24" + "LBL".
        assert ps.part_ref == "pwr_v24"
        assert ps.tag_prefix == "PWR"

    def test_label_net_placed_symbol_has_lbl_part_ref(self) -> None:
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )
        from schematika.pcb.model import SymbolMapping

        net = SimpleNamespace(name="em_stop", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        ps = _placed_symbol_for_net_terminator(t, mapping)
        assert ps.part_ref == "lbl_em_stop"

    def test_label_net_placed_symbol_tag_prefix_is_lbl(self) -> None:
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )
        from schematika.pcb.model import SymbolMapping

        net = SimpleNamespace(name="em_stop", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        ps = _placed_symbol_for_net_terminator(t, mapping)
        assert ps.tag_prefix == "LBL"

    def test_label_net_placed_symbol_not_rotated(self) -> None:
        from types import SimpleNamespace

        from schematika.pcb.builder import (
            _NetEndpointTerminator,
            _placed_symbol_for_net_terminator,
        )
        from schematika.pcb.model import SymbolMapping

        net = SimpleNamespace(name="em_stop", pins=())
        t = _NetEndpointTerminator(net=net, pin_part_ref="X", pin_name="1")
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        ps = _placed_symbol_for_net_terminator(t, mapping)
        assert ps.rotated is False


class TestPlacedSymbolForConnectorTerminator:
    """Covers mutant 86: part_ref format f'{ref}_pin{pin_name}'."""

    def test_part_ref_format_includes_underscore_pin(self) -> None:
        from _factories import make_fake_template

        from schematika.electrical.symbols import connector_pin
        from schematika.pcb.builder import (
            _ConnectorTerminator,
            _placed_symbol_for_connector_terminator,
        )
        from schematika.pcb.model import ConnectorMap

        tmpl = make_fake_template("J1", ("1",))
        cmap = ConnectorMap(template=tmpl, pin_symbol=connector_pin, position="top")
        t = _ConnectorTerminator(cmap=cmap, pin_name="1", part_ref="J1")
        ps = _placed_symbol_for_connector_terminator(t)
        assert ps.part_ref == "J1_pin1"

    def test_pin_name_kwarg_defaulted_by_factory(self) -> None:
        """Mutant 84 sets pin_name=None; the resulting factory then defaults
        pin_label to None, but the captured variable should be the actual pin_name.
        """
        from _factories import make_fake_template

        from schematika.electrical.symbols import connector_pin
        from schematika.pcb.builder import (
            _ConnectorTerminator,
            _placed_symbol_for_connector_terminator,
        )
        from schematika.pcb.model import ConnectorMap

        tmpl = make_fake_template("J1", ("7",))
        cmap = ConnectorMap(template=tmpl, pin_symbol=connector_pin, position="top")
        t = _ConnectorTerminator(cmap=cmap, pin_name="7", part_ref="J1")
        ps = _placed_symbol_for_connector_terminator(t)
        sym = ps.symbol_factory()
        # The factory forwards pin_label=pin_name to the underlying connector_pin.
        # A renderer should see "7" somewhere among Text elements.
        texts = [e for e in sym.elements if isinstance(e, Text)]
        contents = [t.content for t in texts]
        assert "7" in contents


# Silence pyflakes about unused imports introduced by local imports-within-tests
_ = pytest
