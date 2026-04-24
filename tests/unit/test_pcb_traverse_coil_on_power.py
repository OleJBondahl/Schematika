"""Traverse test: relay coil reachable from label-endpoint and power net."""

import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.electrical.symbols import coil, connector_pin
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
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


def _make_coil_template() -> Part:
    return Part(
        name="Coil",
        ref_prefix="K",
        pins=[Pin(num="A1", name=""), Pin(num="A2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


def _power_factory(label: str = "", **_kw) -> Symbol:
    port = Port("1", Point(0, 0), Vector(0, -1))
    return Symbol(elements=[], ports={"1": port}, label=label)


class TestCoilOnPower:
    def _build(self):
        """
        Circuit topology:
          J1 --ctrl_net(CHAIN)--> K1.A1
          K1.A2 --gnd(POWER, 3 pins)

        The coil slice (K1) is reachable from the J1 terminator via ctrl_net.
        K1.A2 ends at the GND power net.
        """
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        coil_tmpl = _make_coil_template()
        extra_tmpl = _make_connector_template(1)

        j1 = conn_tmpl(ref="J1", circuit=c)
        k1 = coil_tmpl(ref="K1", circuit=c)
        px1 = extra_tmpl(ref="Px1", circuit=c)
        px2 = extra_tmpl(ref="Px2", circuit=c)

        ctrl_net = Net("ctrl", circuit=c)
        ctrl_net += j1["1"], k1["A1"]

        gnd = Net("gnd", circuit=c)
        gnd += k1["A2"], px1["1"], px2["1"]

        coil_slice = SymbolSlice(symbol=coil, pin_map={"A1": "A1", "A2": "A2"})
        coil_map = SymbolMap(template=coil_tmpl, slices=(coil_slice,))
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        extra_cmap = ConnectorMap(
            template=extra_tmpl, pin_symbol=connector_pin, position="top"
        )

        mapping = SymbolMapping(
            symbols=(coil_map,),
            connectors=(cmap, extra_cmap),
            power_nets=(PowerNetMap(net_name="gnd", symbol=_power_factory),),
        )
        return c, mapping

    def test_coil_placed_no_orphan(self) -> None:
        """Coil must be placed without raising OrphanSliceError."""
        c, mapping = self._build()
        result = build(c, mapping)
        assert len(result.columns) >= 1

    def test_columns_have_keys(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        for key, _ in result.columns:
            assert key.startswith("pcb_col_")

    def test_pages_non_empty(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        assert len(result.pages) >= 1

    def test_all_columns_in_pages(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        paged = set()
        for _, keys in result.pages:
            paged.update(keys)
        col_keys = {k for k, _ in result.columns}
        assert col_keys == paged
