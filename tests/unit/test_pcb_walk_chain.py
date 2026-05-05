"""Tests for walk_pin — single-step CHAIN traversal."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PartRef, PinRef
from schematika.pcb.model import (
    Column,
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
# Fuse symbol factory (minimal 2-pin symbol for tests)
# ---------------------------------------------------------------------------


def _fuse_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="fuse",
    )


# ---------------------------------------------------------------------------
# Shared template stubs
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


def _make_mapping(*, with_power: bool = True) -> SymbolMapping:
    fuse_slice = SymbolSlice(
        symbol=_fuse_symbol,
        pin_map={"1": "top", "2": "bottom"},
    )
    power_net = PowerNetMap(
        canonical_name="+24V",
        symbol=power_24v,
        aliases=("/v24",),
    )
    return SymbolMapping(
        symbols=(SymbolMap(template=_fuse_template, slices=(fuse_slice,)),),
        connectors=(ConnectorMap(template=_conn_template),),
        power_nets=(power_net,) if with_power else (),
    )


def _make_ir(parts, nets) -> CircuitIR:
    return CircuitIR(parts=tuple(parts), nets=tuple(nets), nc_pins=())


# ---------------------------------------------------------------------------
# Test 1: CHAIN → power alias → POWER terminator
# ---------------------------------------------------------------------------


def test_chain_terminating_in_power_returns_power_terminator() -> None:
    """J1.1 → /PWR_IN (chain 2 pins) → F1.1; F1.2 → /v24 (power alias) → POWER."""
    mapping = _make_mapping(with_power=True)
    ir = _make_ir(
        parts=[
            PartRef(ref="J1", template_name="conn_2p", pin_numbers=("1", "2")),
            PartRef(ref="F1", template_name="fuse", pin_numbers=("1", "2")),
        ],
        nets=[
            NetRef(
                name="/PWR_IN",
                pins=(PinRef("J1", "1"), PinRef("F1", "1")),
            ),
            NetRef(
                name="/v24",
                pins=(
                    PinRef("F1", "2"),
                ),  # single pin → DROPPED by count, but POWER by alias
            ),
        ],
    )
    ctx = WalkContext(
        ir=ir,
        mapping=mapping,
        slice_ownership={},
        max_symbols_per_column=10,
    )
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    column = columns[0]
    assert isinstance(column, Column)
    assert len(column.slices) == 1
    assert column.slices[0].part_ref == "F1"
    assert column.terminator is Terminator.POWER
    assert column.terminator_label == "+24V"


# ---------------------------------------------------------------------------
# Test 2: CHAIN → label (3-pin net) → LABEL terminator
# ---------------------------------------------------------------------------


def test_chain_terminating_in_label_returns_label_terminator() -> None:
    """J1.1 → /PWR_IN (chain) → F1.1; F1.2 → /multi_drop (3 pins) → LABEL."""
    mapping = _make_mapping(with_power=False)
    ir = _make_ir(
        parts=[
            PartRef(ref="J1", template_name="conn_2p", pin_numbers=("1", "2")),
            PartRef(ref="F1", template_name="fuse", pin_numbers=("1", "2")),
            PartRef(ref="K1", template_name="fuse", pin_numbers=("1", "2")),
            PartRef(ref="K2", template_name="fuse", pin_numbers=("1", "2")),
        ],
        nets=[
            NetRef(
                name="/PWR_IN",
                pins=(PinRef("J1", "1"), PinRef("F1", "1")),
            ),
            NetRef(
                name="/multi_drop",
                pins=(PinRef("F1", "2"), PinRef("K1", "1"), PinRef("K2", "1")),
            ),
        ],
    )
    ctx = WalkContext(
        ir=ir,
        mapping=mapping,
        slice_ownership={},
        max_symbols_per_column=10,
    )
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    # Under the new semantics LABEL exits become dedicated empty columns;
    # F1 is placed in a separate column (the final one from _walk_part_to_completion).
    label_cols = [c for c in columns if c.terminator is Terminator.LABEL]
    f1_cols = [c for c in columns if any(s.part_ref == "F1" for s in c.slices)]
    assert label_cols, "Expected at least one LABEL-terminated column"
    assert label_cols[0].terminator_label == "multi_drop"
    assert f1_cols, "F1 must be placed in some column"


# ---------------------------------------------------------------------------
# Test 3: no net → NC
# ---------------------------------------------------------------------------


def test_pin_with_no_net_returns_nc() -> None:
    """J1.1 has no net → NC with no slices."""
    mapping = _make_mapping(with_power=False)
    ir = _make_ir(
        parts=[PartRef(ref="J1", template_name="conn_2p", pin_numbers=("1", "2"))],
        nets=[],
    )
    ctx = WalkContext(
        ir=ir,
        mapping=mapping,
        slice_ownership={},
        max_symbols_per_column=10,
    )
    columns = walk_pin(ctx, connector_ref="J1", pin_id="1")
    column = columns[0]
    assert column.terminator is Terminator.NC
    assert column.slices == ()
    assert column.terminator_label is None


# ---------------------------------------------------------------------------
# Test 4: ownership — first touch wins
# ---------------------------------------------------------------------------


def test_chain_records_ownership_first_touch_wins() -> None:
    """walk_pin sets ctx.slice_ownership[('F1', 0)] = 'J1' on first placement."""
    mapping = _make_mapping(with_power=True)
    ir = _make_ir(
        parts=[
            PartRef(ref="J1", template_name="conn_2p", pin_numbers=("1", "2")),
            PartRef(ref="F1", template_name="fuse", pin_numbers=("1", "2")),
        ],
        nets=[
            NetRef(
                name="/PWR_IN",
                pins=(PinRef("J1", "1"), PinRef("F1", "1")),
            ),
            NetRef(
                name="/v24",
                pins=(PinRef("F1", "2"),),
            ),
        ],
    )
    ctx = WalkContext(
        ir=ir,
        mapping=mapping,
        slice_ownership={},
        max_symbols_per_column=10,
    )
    walk_pin(ctx, connector_ref="J1", pin_id="1")  # return value not needed
    assert ctx.slice_ownership[("F1", 0)] == "J1"
