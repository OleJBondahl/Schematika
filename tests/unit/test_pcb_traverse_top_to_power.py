"""Traverse test: J1.pin1 -> fuse -> V24 power net (>=3 pins)."""

import skidl  # ty: ignore[unresolved-import]
from skidl import Circuit, Net, Part, Pin  # ty: ignore[unresolved-import]

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.electrical.symbols import connector_pin, fuse
from schematika.pcb.builder import build
from schematika.pcb.model import (
    ConnectorMap,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)


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


def _power_factory(label: str = "", **_kw) -> Symbol:
    port = Port("1", Point(0, 0), Vector(0, -1))
    return Symbol(elements=[], ports={"1": port}, label=label)


class TestTopToPower:
    def _build(self, extra_pins: int = 2):
        """Build circuit: J1 -> F1 -> v24 (power net with extra_pins+1 total pins)."""
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()
        extra_tmpl = _make_connector_template(1)

        j1 = conn_tmpl(ref="J1", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        # net_in: J1 -> F1 (CHAIN)
        net_in = Net("net_in", circuit=c)
        net_in += j1["1"], f1["1"]

        # v24: F1.2 + 2 extra parts (total 3 pins -> POWER)
        v24 = Net("v24", circuit=c)
        v24 += f1["2"]
        for i in range(extra_pins):
            p = extra_tmpl(ref=f"Px{i}", circuit=c)
            v24 += p["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        extra_cmap = ConnectorMap(
            template=extra_tmpl, pin_symbol=connector_pin, position="top"
        )

        mapping = SymbolMapping(
            symbols=(fuse_map,),
            connectors=(cmap, extra_cmap),
            power_nets=(PowerNetMap(net_name="v24", symbol=_power_factory),),
        )
        return c, mapping

    def test_produces_columns(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        assert len(result.columns) >= 1

    def test_power_net_classified(self) -> None:
        from schematika.pcb.adapter import adapt
        from schematika.pcb.builder import _classify_nets, _NetKind

        c, mapping = self._build()
        ir = adapt(c)
        kinds = _classify_nets(ir, mapping)
        assert kinds.get("v24") == _NetKind.POWER

    def test_fuse_chain_net_classified(self) -> None:
        from schematika.pcb.adapter import adapt
        from schematika.pcb.builder import _classify_nets, _NetKind

        c, mapping = self._build()
        ir = adapt(c)
        kinds = _classify_nets(ir, mapping)
        assert kinds.get("net_in") == _NetKind.CHAIN

    def test_result_has_pages(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        assert len(result.pages) >= 1

    def test_page_title_auto_generated(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        assert result.pages[0][0] == "Page 1"
