"""Tests for bottom-terminator walker behaviour (TDD for feat/bottom-terminator)."""

import logging
from types import SimpleNamespace

import pytest

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PartRef, PinRef
from schematika.pcb.errors import BottomTerminatorOrphanNetError
from schematika.pcb.model import (
    ConnectorMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)
from schematika.pcb.walk import build_connector_blocks

# ---------------------------------------------------------------------------
# Shared symbol / template stubs
# ---------------------------------------------------------------------------

_normal_conn_template = type(
    "conn_normal",
    (),
    {
        "name": "conn_normal",
        "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")],
    },
)()

_bottom_conn_template = type(
    "conn_bottom",
    (),
    {
        "name": "conn_bottom",
        "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")],
    },
)()

_bottom_conn_template_2 = type(
    "conn_bottom_2",
    (),
    {
        "name": "conn_bottom_2",
        "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")],
    },
)()

_relay_template = type(
    "relay",
    (),
    {
        "name": "relay",
        "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")],
    },
)()


def _relay_symbol(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label=label or "relay",
    )


def _mapping(*, bottom_conn_as_bottom_terminator: bool = True) -> SymbolMapping:
    relay_slice = SymbolSlice(
        symbol=_relay_symbol,
        pin_map={"1": "top", "2": "bottom"},
    )
    return SymbolMapping(
        symbols=(SymbolMap(template=_relay_template, slices=(relay_slice,)),),
        connectors=(
            ConnectorMap(template=_normal_conn_template),
            ConnectorMap(
                template=_bottom_conn_template,
                bottom_terminator=bottom_conn_as_bottom_terminator,
            ),
            ConnectorMap(
                template=_bottom_conn_template_2,
                bottom_terminator=True,
            ),
        ),
        power_nets=(),
    )


def _make_ir(parts, nets) -> CircuitIR:
    return CircuitIR(parts=tuple(parts), nets=tuple(nets), nc_pins=())


# ---------------------------------------------------------------------------
# Test 1: flagged connector is skipped in connector_blocks
# ---------------------------------------------------------------------------


def test_bottom_terminator_connector_skipped_in_blocks() -> None:
    """Connector flagged as bottom_terminator=True must not appear in connector_blocks."""
    mapping = _mapping()
    ir = _make_ir(
        parts=[
            PartRef(
                ref="J1",
                template_name="conn_normal",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="J7",
                template_name="conn_bottom",
                pin_numbers=("1", "2"),
                description=None,
            ),
        ],
        nets=[],
    )
    blocks, _ = build_connector_blocks(
        ir,
        mapping,
        max_symbols_per_column=2,
        strict_net_names=False,
    )
    block_refs = {b.connector_ref for b in blocks}
    assert "J1" in block_refs
    assert "J7" not in block_refs


# ---------------------------------------------------------------------------
# Test 2: orphan net raises BottomTerminatorOrphanNetError
# ---------------------------------------------------------------------------


def test_orphan_net_raises_error() -> None:
    """Net where no part is reachable from a normal connector raises error.

    K1 is only connected to J7 (bottom_terminator) and J8 (bottom_terminator).
    There is no path from K1 to any normal connector, so build must raise.
    """
    mapping = _mapping()
    ir = _make_ir(
        parts=[
            PartRef(
                ref="J1",
                template_name="conn_normal",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="J7",
                template_name="conn_bottom",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="J8",
                template_name="conn_bottom_2",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="K1",
                template_name="relay",
                pin_numbers=("1", "2"),
                description=None,
            ),
        ],
        nets=[
            # K1.1 only connects to J7 (bottom-terminator) — orphan.
            NetRef(
                name="/orphan_net",
                pins=(PinRef("J7", "1"), PinRef("K1", "1")),
            ),
            # K1.2 only connects to J8 (bottom-terminator) — K1 is completely isolated.
            NetRef(
                name="/orphan_net_2",
                pins=(PinRef("J8", "1"), PinRef("K1", "2")),
            ),
            # J1 exists but has no connection to K1 — it connects to something else
            NetRef(
                name="/normal_net",
                pins=(PinRef("J1", "1"),),
            ),
        ],
    )
    with pytest.raises(BottomTerminatorOrphanNetError) as exc_info:
        build_connector_blocks(
            ir,
            mapping,
            max_symbols_per_column=2,
            strict_net_names=False,
        )
    assert "orphan_net" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 3: chain entering normal connector and exiting via bottom-terminator pin
# ---------------------------------------------------------------------------


def test_bottom_terminator_emits_pin_at_bottom_terminator() -> None:
    """Chain: J1.1 → K1 → net exiting to J7.2 emits PIN_AT_BOTTOM with label 'J7:2'."""
    mapping = _mapping()
    ir = _make_ir(
        parts=[
            PartRef(
                ref="J1",
                template_name="conn_normal",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="J7",
                template_name="conn_bottom",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="K1",
                template_name="relay",
                pin_numbers=("1", "2"),
                description=None,
            ),
        ],
        nets=[
            # J1.1 → K1.1 (chain, 2 pins)
            NetRef(
                name="/entry_net",
                pins=(PinRef("J1", "1"), PinRef("K1", "1")),
            ),
            # K1.2 → J7.2 (chain, 2 pins, but J7 is bottom_terminator)
            NetRef(
                name="/bottom_net",
                pins=(PinRef("K1", "2"), PinRef("J7", "2")),
            ),
        ],
    )
    blocks, _ = build_connector_blocks(
        ir,
        mapping,
        max_symbols_per_column=10,
        strict_net_names=False,
    )
    # Find J1's block
    j1_block = next(b for b in blocks if b.connector_ref == "J1")
    # Pin 1's columns
    pin1_cols = next(pc for pc in j1_block.pin_columns if pc.pin_id == "1")
    # Find column with PIN_AT_BOTTOM terminator
    pin_at_bottom_cols = [
        c for c in pin1_cols.columns if c.terminator is Terminator.PIN_AT_BOTTOM
    ]
    assert pin_at_bottom_cols, (
        f"Expected PIN_AT_BOTTOM column; got terminators: "
        f"{[c.terminator for c in pin1_cols.columns]}"
    )
    col = pin_at_bottom_cols[0]
    assert col.terminator_label == "J7:2", (
        f"Expected 'J7:2', got {col.terminator_label!r}"
    )
    assert col.chain_net_name is not None, (
        "chain_net_name must be set on PIN_AT_BOTTOM column"
    )


# ---------------------------------------------------------------------------
# Test 4: duplicate PIN_AT_BOTTOM on same page emits warning
# ---------------------------------------------------------------------------


def test_duplicate_pin_at_bottom_warning(caplog) -> None:
    """Two chains on same page with same PIN_AT_BOTTOM label emit a warning."""

    mapping = _mapping()
    ir = _make_ir(
        parts=[
            PartRef(
                ref="J1",
                template_name="conn_normal",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="J7",
                template_name="conn_bottom",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="K1",
                template_name="relay",
                pin_numbers=("1", "2"),
                description=None,
            ),
            PartRef(
                ref="K2",
                template_name="relay",
                pin_numbers=("1", "2"),
                description=None,
            ),
        ],
        nets=[
            # J1.1 → K1.1; K1.2 → J7.2
            NetRef(
                name="/chain_a_in",
                pins=(PinRef("J1", "1"), PinRef("K1", "1")),
            ),
            NetRef(
                name="/chain_a_out",
                pins=(PinRef("K1", "2"), PinRef("J7", "2")),
            ),
            # J1.2 → K2.1; K2.2 → J7.2 (same pin!)
            NetRef(
                name="/chain_b_in",
                pins=(PinRef("J1", "2"), PinRef("K2", "1")),
            ),
            NetRef(
                name="/chain_b_out",
                pins=(PinRef("K2", "2"), PinRef("J7", "2")),
            ),
        ],
    )
    with caplog.at_level(logging.WARNING):
        _blocks, _ = build_connector_blocks(
            ir,
            mapping,
            max_symbols_per_column=10,
            strict_net_names=False,
        )
    # Check that a warning was emitted mentioning J7:2
    warning_messages = [
        r.message for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any("J7:2" in str(m) for m in warning_messages), (
        f"Expected warning about duplicate J7:2, got: {warning_messages}"
    )
