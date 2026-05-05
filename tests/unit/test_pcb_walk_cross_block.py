"""Tests for cross-block CHAIN guard: when walking from J2 reaches K1 already
owned by J1, the walk terminates with LABEL without re-placing K1."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PartRef, PinRef
from schematika.pcb.model import (
    ConnectorMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)
from schematika.pcb.walk import WalkContext, build_connector_blocks, walk_pin

# ---------------------------------------------------------------------------
# Symbol factories
# ---------------------------------------------------------------------------


def _two_port_symbol() -> Symbol:
    """A minimal 2-pin symbol for relay or other parts."""
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 1), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="relay",
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_conn_4p_template = type(
    "conn_4p",
    (),
    {
        "name": "conn_4p",
        "pins": [
            SimpleNamespace(num="1"),
            SimpleNamespace(num="2"),
            SimpleNamespace(num="3"),
            SimpleNamespace(num="4"),
            SimpleNamespace(num="5"),
        ],
    },
)()

_relay_spst_template = type(
    "relay_spst",
    (),
    {
        "name": "relay_spst",
        "pins": [SimpleNamespace(num="A1"), SimpleNamespace(num="A2")],
    },
)()


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _cross_block_ctx() -> WalkContext:
    """Build a cross-block CHAIN fixture.

    Two connectors (J1, J2) both connect to the same relay (K1) via two
    different nets with the same name (/sig_a). When J1 walks first, K1 is
    placed and ownership["K1"] = "J1". When J2 walks second, it should
    encounter K1 already owned and return LABEL without re-placing.

    IR parts:
      - J1: conn_4p with pins "1","2","3","4"
      - J2: conn_4p with pins "1","2","3","4","5"
      - K1: relay_spst with pins "A1","A2"

    Nets:
      - /sig_a net #1: (J1.3, K1.A1)  — CHAIN
      - /sig_a net #2: (J2.5, K1.A1)  — CHAIN (same name, different net object)
      - /nc_k1a2: (K1.A2)             — DROPPED (single pin)

    Mapping:
      - relay_spst → SymbolMap with _two_port_symbol
      - conn_4p → ConnectorMap
      - no power nets
    """
    ir = CircuitIR(
        parts=(
            PartRef(
                ref="J1", template_name="conn_4p", pin_numbers=("1", "2", "3", "4")
            ),
            PartRef(
                ref="J2", template_name="conn_4p", pin_numbers=("1", "2", "3", "4", "5")
            ),
            PartRef(ref="K1", template_name="relay_spst", pin_numbers=("A1", "A2")),
        ),
        nets=(
            # J1.3 → K1.A1 (first net named /sig_a)
            NetRef(name="/sig_a", pins=(PinRef("J1", "3"), PinRef("K1", "A1"))),
            # J2.5 → K1.A1 (second net also named /sig_a)
            NetRef(name="/sig_a", pins=(PinRef("J2", "5"), PinRef("K1", "A1"))),
            # K1.A2 has no other pin (DROPPED)
            NetRef(name="/nc_k1a2", pins=(PinRef("K1", "A2"),)),
        ),
        nc_pins=(),
    )

    relay_slice = SymbolSlice(
        symbol=_two_port_symbol,
        pin_map={"A1": "top", "A2": "bottom"},
    )

    mapping = SymbolMapping(
        symbols=(SymbolMap(template=_relay_spst_template, slices=(relay_slice,)),),
        connectors=(ConnectorMap(template=_conn_4p_template),),
        power_nets=(),
    )

    return WalkContext(
        ir=ir,
        mapping=mapping,
        ownership={},
        max_symbols_per_column=8,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_first_walk_places_k1_and_records_ownership() -> None:
    """J1.3 walks first: K1 placed, ownership["K1"] = "J1"."""
    ctx = _cross_block_ctx()
    columns = walk_pin(ctx, connector_ref="J1", pin_id="3")
    placed_refs = [sl.part_ref for col in columns for sl in col.slices]
    assert "K1" in placed_refs, "K1 should be placed on first walk from J1"
    assert ctx.ownership.get("K1") == "J1", "K1 should be owned by J1"


def test_second_walk_returns_label_not_placing_k1() -> None:
    """J2.5 walks second: K1 already owned by J1 → LABEL terminator, K1 not placed."""
    ctx = _cross_block_ctx()
    # Simulate J1 already having walked by setting ownership.
    ctx.ownership["K1"] = "J1"
    columns = walk_pin(ctx, connector_ref="J2", pin_id="5")
    placed_refs = [sl.part_ref for col in columns for sl in col.slices]
    assert "K1" not in placed_refs, "K1 must not be placed again (already owned by J1)"
    assert any(col.terminator is Terminator.LABEL for col in columns), (
        "Should have LABEL terminator"
    )


def test_cross_block_label_preserves_net_name() -> None:
    """The LABEL terminator carries the stripped net name."""
    ctx = _cross_block_ctx()
    ctx.ownership["K1"] = "J1"
    columns = walk_pin(ctx, connector_ref="J2", pin_id="5")
    label_cols = [col for col in columns if col.terminator is Terminator.LABEL]
    assert label_cols, "Should have at least one LABEL column"
    assert label_cols[0].terminator_label == "sig_a", (
        "Label should be stripped net name"
    )


def test_end_to_end_ownership_chain() -> None:
    """Full scenario: J1 walks first, then J2 walks second; K1 owned by J1 only."""
    ctx = _cross_block_ctx()

    # First walk: J1.3 → K1.A1
    columns_j1 = walk_pin(ctx, connector_ref="J1", pin_id="3")
    placed_refs_j1 = [sl.part_ref for col in columns_j1 for sl in col.slices]
    assert "K1" in placed_refs_j1, "J1 walk should place K1"
    assert ctx.ownership["K1"] == "J1", "K1 now owned by J1"

    # Second walk: J2.5 → K1.A1 (but K1 already owned)
    columns_j2 = walk_pin(ctx, connector_ref="J2", pin_id="5")
    placed_refs_j2 = [sl.part_ref for col in columns_j2 for sl in col.slices]
    assert "K1" not in placed_refs_j2, "J2 walk must not place K1 (owned by J1)"
    assert any(col.terminator is Terminator.LABEL for col in columns_j2), (
        "J2 should terminate at LABEL"
    )
    assert ctx.ownership["K1"] == "J1", "K1 still owned by J1"


def test_intra_connector_dedup_no_duplicate_slices() -> None:
    """K1 owned by J2, re-entered via a second J2 pin — must not place K1 twice.

    Fixture: J2 has two pins both chaining into K1 via different relay pins.
    The first pin places K1 (1 slice). The second pin should find K1 already
    in placed_parts and return LABEL without emitting more slices.
    """
    relay_slice_a = SymbolSlice(
        symbol=_two_port_symbol,
        pin_map={"A1": "top", "A2": "bottom"},
    )

    _conn_2p_template = type(
        "conn_2p",
        (),
        {
            "name": "conn_2p",
            "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")],
        },
    )()

    mapping = SymbolMapping(
        symbols=(SymbolMap(template=_relay_spst_template, slices=(relay_slice_a,)),),
        connectors=(ConnectorMap(template=_conn_2p_template),),
        power_nets=(),
    )

    # J2 pin 1 → K1.A1 (CHAIN), J2 pin 2 → K1.A2 (CHAIN): same part re-entered
    ir = CircuitIR(
        parts=(
            PartRef(ref="J2", template_name="conn_2p", pin_numbers=("1", "2")),
            PartRef(ref="K1", template_name="relay_spst", pin_numbers=("A1", "A2")),
        ),
        nets=(
            NetRef(name="/net_a", pins=(PinRef("J2", "1"), PinRef("K1", "A1"))),
            NetRef(name="/net_b", pins=(PinRef("J2", "2"), PinRef("K1", "A2"))),
        ),
        nc_pins=(),
    )

    blocks, _ = build_connector_blocks(
        ir, mapping, max_symbols_per_column=8, strict_net_names=False
    )

    j2_block = next(b for b in blocks if b.connector_ref == "J2")
    all_slices = [
        sl for pc in j2_block.pin_columns for col in pc.columns for sl in col.slices
    ]
    k1_slices = [sl for sl in all_slices if sl.part_ref == "K1"]
    assert len(k1_slices) == 1, (
        f"K1 must appear exactly once (1 slice relay), got {len(k1_slices)}"
    )
