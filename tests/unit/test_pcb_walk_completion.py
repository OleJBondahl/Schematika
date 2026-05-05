"""Tests for walk_pin — slice-aware single-slice placement for multi-slice parts."""

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
)
from schematika.pcb.symbols.power import power_24v
from schematika.pcb.walk import WalkContext, walk_pin

# ---------------------------------------------------------------------------
# Symbol factories
# ---------------------------------------------------------------------------


def _two_port_symbol(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label=label or "relay_slice",
    )


# ---------------------------------------------------------------------------
# Template stubs
# ---------------------------------------------------------------------------

_conn_template = type(
    "conn_2p",
    (),
    {"name": "conn_2p", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()

_relay_template = type(
    "relay_dpst",
    (),
    {
        "name": "relay_dpst",
        "pins": [
            SimpleNamespace(num="A1"),
            SimpleNamespace(num="A2"),
            SimpleNamespace(num="13"),
            SimpleNamespace(num="14"),
            SimpleNamespace(num="21"),
            SimpleNamespace(num="22"),
        ],
    },
)()


def _build_ctx() -> WalkContext:
    coil_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"A1": "top", "A2": "bottom"}
    )
    no1_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"13": "top", "14": "bottom"}
    )
    no2_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"21": "top", "22": "bottom"}
    )

    relay_map = SymbolMap(
        template=_relay_template,
        slices=(coil_slice, no1_slice, no2_slice),
    )
    power_net = PowerNetMap(
        canonical_name="+24V",
        symbol=power_24v,
        aliases=("/v24", "/v24_no1_a", "/v24_no1_b", "/v24_no2_a", "/v24_no2_b"),
    )
    mapping = SymbolMapping(
        symbols=(relay_map,),
        connectors=(ConnectorMap(template=_conn_template),),
        power_nets=(power_net,),
    )
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_2p", pin_numbers=("1", "2")),
            PartRef(
                ref="K1",
                template_name="relay_dpst",
                pin_numbers=("A1", "A2", "13", "14", "21", "22"),
            ),
        ),
        nets=(
            # J1.1 → K1.A1 (2-pin chain)
            NetRef(name="/em_stop", pins=(PinRef("J1", "1"), PinRef("K1", "A1"))),
            # Power aliases on all remaining K1 pins (single-pin → DROPPED count, POWER by alias)
            NetRef(name="/v24", pins=(PinRef("K1", "A2"),)),
            NetRef(name="/v24_no1_a", pins=(PinRef("K1", "13"),)),
            NetRef(name="/v24_no1_b", pins=(PinRef("K1", "14"),)),
            NetRef(name="/v24_no2_a", pins=(PinRef("K1", "21"),)),
            NetRef(name="/v24_no2_b", pins=(PinRef("K1", "22"),)),
        ),
        nc_pins=(),
    )
    return WalkContext(
        ir=ir, mapping=mapping, slice_ownership={}, max_symbols_per_column=8
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_only_entry_slice_placed_in_column() -> None:
    """Walking J1.1 → K1.A1 places ONLY the coil slice (slice 0), not all 3."""
    ctx = _build_ctx()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    all_slices = [sl for col in columns for sl in col.slices]
    k1_slices = [sl for sl in all_slices if sl.part_ref == "K1"]
    assert len(k1_slices) == 1, f"Expected 1 K1 slice (coil only), got {len(k1_slices)}"
    assert k1_slices[0].slice_index == 0, "Expected coil slice (index 0)"


def test_entry_slice_coil_pins_correct() -> None:
    """The placed K1 slice contains pins A1 and A2 (the coil slice)."""
    ctx = _build_ctx()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    all_slices = [sl for col in columns for sl in col.slices]
    k1_slices = [sl for sl in all_slices if sl.part_ref == "K1"]
    assert len(k1_slices) == 1
    placed_pin_ids = {pp.pin_id for pp in k1_slices[0].pins}
    assert placed_pin_ids == {"A1", "A2"}


def test_k1_coil_slice_ownership_set_to_j1() -> None:
    """walk_pin sets ctx.slice_ownership[('K1', 0)] = 'J1' after placing coil slice."""
    ctx = _build_ctx()
    walk_pin(ctx, connector_ref="J1", pin_id="1")
    assert ctx.slice_ownership.get(("K1", 0)) == "J1"
