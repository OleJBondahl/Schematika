"""Tests for _classify_nets: 0/1/2/3+ pin nets, POWER vs LABEL."""

import skidl  # ty: ignore[unresolved-import]
from skidl import Circuit, Net, Part, Pin  # ty: ignore[unresolved-import]

from schematika.pcb.adapter import adapt
from schematika.pcb.builder import _classify_nets, _NetKind
from schematika.pcb.model import PowerNetMap, SymbolMapping


def _make_part(name: str, ref_prefix: str, n_pins: int) -> Part:
    pins = [Pin(num=str(i), name="") for i in range(1, n_pins + 1)]
    return Part(
        name=name,
        ref_prefix=ref_prefix,
        pins=pins,
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )


def _one_port_factory():
    from schematika.core.geometry import Point, Vector
    from schematika.core.symbol import Port, Symbol

    def factory(label: str = "", **_kw) -> Symbol:
        port = Port("1", Point(0, 0), Vector(0, -1))
        return Symbol(elements=[], ports={"1": port}, label=label)

    return factory


class TestDroppedNets:
    def test_zero_pin_net_dropped(self) -> None:
        c = Circuit()
        Net("empty_net", circuit=c)
        ir = adapt(c)
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        kinds = _classify_nets(ir, mapping)
        assert "empty_net" not in kinds

    def test_one_pin_net_dropped(self) -> None:
        c = Circuit()
        t = _make_part("P", "P", 2)
        p = t(ref="P1", circuit=c)
        n = Net("solo", circuit=c)
        n += p["1"]
        ir = adapt(c)
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        kinds = _classify_nets(ir, mapping)
        assert "solo" not in kinds


class TestChainNets:
    def test_two_pin_net_is_chain(self) -> None:
        c = Circuit()
        t = _make_part("F", "F", 2)
        f1 = t(ref="F1", circuit=c)
        f2 = t(ref="F2", circuit=c)
        n = Net("chain_net", circuit=c)
        n += f1["1"], f2["1"]
        ir = adapt(c)
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        kinds = _classify_nets(ir, mapping)
        assert kinds["chain_net"] == _NetKind.CHAIN

    def test_exactly_two_pins_is_chain(self) -> None:
        c = Circuit()
        t = _make_part("R", "R", 2)
        r1 = t(ref="R1", circuit=c)
        r2 = t(ref="R2", circuit=c)
        n = Net("two_pin", circuit=c)
        n += r1["1"], r2["2"]
        ir = adapt(c)
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        kinds = _classify_nets(ir, mapping)
        assert kinds["two_pin"] == _NetKind.CHAIN


class TestPowerNets:
    def test_three_pin_net_in_power_nets_is_power(self) -> None:
        c = Circuit()
        t = _make_part("F", "F", 2)
        f1 = t(ref="F1", circuit=c)
        f2 = t(ref="F2", circuit=c)
        f3 = t(ref="F3", circuit=c)
        n = Net("v24", circuit=c)
        n += f1["1"], f2["1"], f3["1"]
        ir = adapt(c)
        factory = _one_port_factory()
        mapping = SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="v24", symbol=factory),),
        )
        kinds = _classify_nets(ir, mapping)
        assert kinds["v24"] == _NetKind.POWER

    def test_four_pin_power_net(self) -> None:
        c = Circuit()
        t = _make_part("P", "P", 2)
        parts = [t(ref=f"P{i}", circuit=c) for i in range(1, 5)]
        n = Net("gnd", circuit=c)
        for p in parts:
            n += p["1"]
        ir = adapt(c)
        factory = _one_port_factory()
        mapping = SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="gnd", symbol=factory),),
        )
        kinds = _classify_nets(ir, mapping)
        assert kinds["gnd"] == _NetKind.POWER


class TestLabelNets:
    def test_three_pin_net_not_in_power_nets_is_label(self) -> None:
        c = Circuit()
        t = _make_part("F", "F", 2)
        parts = [t(ref=f"F{i}", circuit=c) for i in range(1, 4)]
        n = Net("em_stop", circuit=c)
        for p in parts:
            n += p["1"]
        ir = adapt(c)
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        kinds = _classify_nets(ir, mapping)
        assert kinds["em_stop"] == _NetKind.LABEL

    def test_five_pin_net_not_in_power_nets_is_label(self) -> None:
        c = Circuit()
        t = _make_part("F", "F", 2)
        parts = [t(ref=f"F{i}", circuit=c) for i in range(1, 6)]
        n = Net("big_label", circuit=c)
        for p in parts:
            n += p["1"]
        ir = adapt(c)
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
        kinds = _classify_nets(ir, mapping)
        assert kinds["big_label"] == _NetKind.LABEL

    def test_power_net_name_but_only_two_pins_is_chain(self) -> None:
        """Even if a net name is in power_nets, 2-pin net is still CHAIN."""
        c = Circuit()
        t = _make_part("F", "F", 2)
        f1 = t(ref="F1", circuit=c)
        f2 = t(ref="F2", circuit=c)
        n = Net("v24", circuit=c)
        n += f1["1"], f2["1"]
        ir = adapt(c)
        factory = _one_port_factory()
        mapping = SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="v24", symbol=factory),),
        )
        kinds = _classify_nets(ir, mapping)
        assert kinds["v24"] == _NetKind.CHAIN


class TestMultipleNets:
    def test_mixed_kinds(self) -> None:
        c = Circuit()
        t6 = _make_part("P", "P", 6)
        p1 = t6(ref="P1", circuit=c)
        p2 = t6(ref="P2", circuit=c)
        p3 = t6(ref="P3", circuit=c)
        p4 = t6(ref="P4", circuit=c)
        # chain: 2 pins, distinct from all other nets
        n_chain = Net("chain", circuit=c)
        n_chain += p1["1"], p2["1"]
        # label: 3 pins
        n_label = Net("label", circuit=c)
        n_label += p1["2"], p2["2"], p3["1"]
        # power: 3 pins in power_nets
        n_power = Net("v24", circuit=c)
        n_power += p1["3"], p2["3"], p3["2"]
        # solo: 1 pin (dropped)
        n_solo = Net("solo", circuit=c)
        n_solo += p4["1"]
        ir = adapt(c)
        factory = _one_port_factory()
        mapping = SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="v24", symbol=factory),),
        )
        kinds = _classify_nets(ir, mapping)
        assert kinds["chain"] == _NetKind.CHAIN
        assert kinds["label"] == _NetKind.LABEL
        assert kinds["v24"] == _NetKind.POWER
        assert "solo" not in kinds
