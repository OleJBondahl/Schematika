"""Tests for walk_pin — max_symbols_per_column column-cut with CONTINUATION."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PartRef, PinRef
from schematika.pcb.model import (
    ConnectorMap,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)
from schematika.pcb.symbols.power import power_24v
from schematika.pcb.walk import WalkContext, walk_pin

# ---------------------------------------------------------------------------
# Symbol factory
# ---------------------------------------------------------------------------


def _two_port_symbol(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label=label or "two_port",
    )


# ---------------------------------------------------------------------------
# Template stubs
# ---------------------------------------------------------------------------

_conn_template = type(
    "conn_2p",
    (),
    {"name": "conn_2p", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()

_fuse_template = type(
    "fuse",
    (),
    {"name": "fuse", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()

_relay_spst_template = type(
    "relay_spst",
    (),
    {
        "name": "relay_spst",
        "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")],
    },
)()


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _chain_fixture() -> WalkContext:
    """Build a 3-part chain with max_symbols_per_column=1.

    Topology:
        J1.1 --/net_a-- F1.1; F1.2 --/net_b-- K1.1; K1.2 --/v24-- (POWER)

    With max_symbols_per_column=1:
        Column 0: [F1], CONTINUATION, "net_b"
        Column 1: [K1], POWER, "+24V"
    """
    fuse_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"1": "top", "2": "bottom"}
    )
    relay_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"1": "top", "2": "bottom"}
    )

    power_net = PowerNetMap(
        canonical_name="+24V",
        symbol=power_24v,
        aliases=("/v24",),
    )

    mapping = SymbolMapping(
        symbols=(
            SymbolMap(template=_fuse_template, slices=(fuse_slice,)),
            SymbolMap(template=_relay_spst_template, slices=(relay_slice,)),
        ),
        connectors=(ConnectorMap(template=_conn_template),),
        power_nets=(power_net,),
    )

    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_2p", pin_numbers=("1", "2")),
            PartRef(ref="F1", template_name="fuse", pin_numbers=("1", "2")),
            PartRef(ref="K1", template_name="relay_spst", pin_numbers=("1", "2")),
        ),
        nets=(
            NetRef(name="/net_a", pins=(PinRef("J1", "1"), PinRef("F1", "1"))),
            NetRef(name="/net_b", pins=(PinRef("F1", "2"), PinRef("K1", "1"))),
            NetRef(name="/v24", pins=(PinRef("K1", "2"),)),
        ),
        nc_pins=(),
    )

    return WalkContext(
        ir=ir, mapping=mapping, slice_ownership={}, max_symbols_per_column=1
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_column_cut_produces_two_columns() -> None:
    ctx = _chain_fixture()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    assert len(columns) == 2, f"Expected 2 columns, got {len(columns)}: {columns}"


def test_first_column_terminates_with_continuation() -> None:
    ctx = _chain_fixture()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    assert columns[0].terminator is Terminator.CONTINUATION
    assert columns[0].terminator_label == "net_b"


def test_second_column_terminates_with_power() -> None:
    ctx = _chain_fixture()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    assert columns[1].terminator is Terminator.POWER
    assert columns[1].terminator_label == "+24V"


def test_f1_in_first_column_k1_in_second() -> None:
    ctx = _chain_fixture()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    assert columns[0].slices[0].part_ref == "F1"
    assert columns[1].slices[0].part_ref == "K1"
