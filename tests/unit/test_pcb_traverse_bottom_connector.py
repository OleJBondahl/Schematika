"""Traverse test: connector with position="bottom" is rotated 180°."""

import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.electrical.symbols import connector_pin, fuse
from schematika.pcb.builder import (
    _ConnectorTerminator,
    _placed_symbol_for_connector_terminator,
    build,
)
from schematika.pcb.model import ConnectorMap, SymbolMap, SymbolMapping, SymbolSlice


def _make_connector_template(n_pins: int = 1) -> Part:
    return Part(
        name="Connector",
        ref_prefix="J",
        pins=[Pin(num=str(i), name="") for i in range(1, n_pins + 1)],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )


def _make_fuse_template() -> Part:
    return Part(
        name="Fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )


class TestBottomConnectorRotation:
    def test_bottom_connector_placed_symbol_is_rotated(self) -> None:
        cmap = ConnectorMap(
            template=_make_connector_template(1),
            pin_symbol=connector_pin,
            position="bottom",
        )
        t = _ConnectorTerminator(cmap=cmap, pin_name="1", part_ref="J1")
        ps = _placed_symbol_for_connector_terminator(t)
        assert ps.rotated is True

    def test_top_connector_placed_symbol_not_rotated(self) -> None:
        cmap = ConnectorMap(
            template=_make_connector_template(1),
            pin_symbol=connector_pin,
            position="top",
        )
        t = _ConnectorTerminator(cmap=cmap, pin_name="1", part_ref="J1")
        ps = _placed_symbol_for_connector_terminator(t)
        assert ps.rotated is False

    def test_build_with_bottom_connector(self) -> None:
        """Build succeeds with a bottom-position connector."""
        c = Circuit()
        top_tmpl = _make_connector_template(1)
        bot_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j_top = top_tmpl(ref="J1", circuit=c)
        j_bot = bot_tmpl(ref="J2", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        net_in = Net("net_in", circuit=c)
        net_in += j_top["1"], f1["1"]
        net_out = Net("net_out", circuit=c)
        net_out += f1["2"], j_bot["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        top_cmap = ConnectorMap(
            template=top_tmpl, pin_symbol=connector_pin, position="top"
        )
        bot_cmap = ConnectorMap(
            template=bot_tmpl, pin_symbol=connector_pin, position="bottom"
        )

        mapping = SymbolMapping(
            symbols=(fuse_map,),
            connectors=(top_cmap, bot_cmap),
        )
        result = build(c, mapping)
        assert len(result.columns) == 1

    def test_bottom_connector_column_not_empty(self) -> None:
        """Column with bottom connector produces non-zero placed symbols."""
        cmap = ConnectorMap(
            template=_make_connector_template(1),
            pin_symbol=connector_pin,
            position="bottom",
        )
        t = _ConnectorTerminator(cmap=cmap, pin_name="1", part_ref="J1")
        ps = _placed_symbol_for_connector_terminator(t)
        assert ps.symbol_factory is not None

    def test_multiple_pins_bottom_connector(self) -> None:
        """Each pin of a bottom connector produces a rotated terminator."""
        tmpl = _make_connector_template(3)
        cmap = ConnectorMap(template=tmpl, pin_symbol=connector_pin, position="bottom")
        for pin_name in ["1", "2", "3"]:
            t = _ConnectorTerminator(cmap=cmap, pin_name=pin_name, part_ref="J1")
            ps = _placed_symbol_for_connector_terminator(t)
            assert ps.rotated is True
