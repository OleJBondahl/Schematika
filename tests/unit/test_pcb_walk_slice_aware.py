"""Tests for slice-aware walker — each slice is its own 2-pin pass-through.

These tests verify the Task 2 rewrite of _walk_part_to_completion:
- Entering a multi-slice part places ONLY the entry slice (not all slices).
- Each slice is owned independently by the connector that entered it.
- A part with any unowned slice appears in find_floating_parts.
- A second chain reaching an already-placed slice emits a LABEL terminator.
"""

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
from schematika.pcb.walk import build_connector_blocks, find_floating_parts

# ---------------------------------------------------------------------------
# Symbol factory
# ---------------------------------------------------------------------------


def _two_port_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 1), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="relay_slice",
    )


# ---------------------------------------------------------------------------
# Template stubs
# ---------------------------------------------------------------------------

_conn_1p_template = type(
    "conn_1p",
    (),
    {"name": "conn_1p", "pins": [SimpleNamespace(num="1")]},
)()

_relay_2slice_template = type(
    "relay_2slice",
    (),
    {
        "name": "relay_2slice",
        # coil: A1, A2  |  contact: 11, 14
        "pins": [
            SimpleNamespace(num="A1"),
            SimpleNamespace(num="A2"),
            SimpleNamespace(num="11"),
            SimpleNamespace(num="14"),
        ],
    },
)()


def _relay_2slice_mapping() -> SymbolMapping:
    coil_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"A1": "top", "A2": "bottom"}
    )
    contact_slice = SymbolSlice(
        symbol=_two_port_symbol, pin_map={"11": "top", "14": "bottom"}
    )
    return SymbolMapping(
        symbols=(
            SymbolMap(
                template=_relay_2slice_template,
                slices=(coil_slice, contact_slice),
            ),
        ),
        connectors=(ConnectorMap(template=_conn_1p_template),),
        power_nets=(),
    )


# ---------------------------------------------------------------------------
# IR builder helpers
# ---------------------------------------------------------------------------


def _connector_to_relay_contact_ir() -> tuple[CircuitIR, SymbolMapping]:
    """J1[1] → K1[11] (contact slice). Coil and A2 side are NC."""
    mapping = _relay_2slice_mapping()
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(
                ref="K1",
                template_name="relay_2slice",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            # J1.1 → K1.11 (CHAIN: 2-pin)
            NetRef(name="/contact_in", pins=(PinRef("J1", "1"), PinRef("K1", "11"))),
            # K1.14 has no second pin (DROPPED)
            NetRef(name="/contact_out", pins=(PinRef("K1", "14"),)),
            # Coil pins have no nets — no NC needed, just absent
        ),
        nc_pins=(),
    )
    return ir, mapping


def _two_connectors_split_relay_ir() -> tuple[CircuitIR, SymbolMapping]:
    """J1[1] → K1[A1] (coil); J2[1] → K1[11] (contact). Each owns its slice."""
    mapping = _relay_2slice_mapping()
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(ref="J2", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(
                ref="K1",
                template_name="relay_2slice",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            # J1.1 → K1.A1 (coil entry, 2-pin CHAIN)
            NetRef(name="/coil_drive", pins=(PinRef("J1", "1"), PinRef("K1", "A1"))),
            # K1.A2 has no second pin (DROPPED)
            NetRef(name="/coil_ret", pins=(PinRef("K1", "A2"),)),
            # J2.1 → K1.11 (contact entry, 2-pin CHAIN)
            NetRef(name="/contact_in", pins=(PinRef("J2", "1"), PinRef("K1", "11"))),
            # K1.14 has no second pin (DROPPED)
            NetRef(name="/contact_out", pins=(PinRef("K1", "14"),)),
        ),
        nc_pins=(),
    )
    return ir, mapping


def _connector_to_one_relay_contact_ir() -> tuple[CircuitIR, SymbolMapping]:
    """J1[1] → K1[11] only. Coil (A1, A2) is unowned."""
    return _connector_to_relay_contact_ir()


def _two_chains_to_same_contact_slice_ir() -> tuple[CircuitIR, SymbolMapping]:
    """J1[1] → K1[11] and J2[1] → K1[14]. Both target the SAME contact slice."""
    mapping = _relay_2slice_mapping()
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(ref="J2", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(
                ref="K1",
                template_name="relay_2slice",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            # J1.1 → K1.11 (contact slice entry)
            NetRef(name="/contact_in", pins=(PinRef("J1", "1"), PinRef("K1", "11"))),
            # J2.1 → K1.14 (other end of same contact slice)
            NetRef(name="/contact_out", pins=(PinRef("J2", "1"), PinRef("K1", "14"))),
            # Coil pins absent (no net)
        ),
        nc_pins=(),
    )
    return ir, mapping


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_walker_enters_relay_at_contact_walks_only_contact_slice() -> None:
    """K1 has 2 slices (coil + contact). Entering at pin 11 places ONLY contact slice."""
    ir, mapping = _connector_to_relay_contact_ir()
    blocks, _ = build_connector_blocks(
        ir, mapping, max_symbols_per_column=4, strict_net_names=False
    )
    j_block = next(b for b in blocks if b.connector_ref == "J1")
    pin_columns = j_block.pin_columns[0]  # pin 1
    placed = [s for col in pin_columns.columns for s in col.slices]
    refs_indices = {(s.part_ref, s.slice_index) for s in placed}
    # Only ONE K1 slice should have been placed (the contact slice containing pin 11).
    k1_slices = {(r, i) for r, i in refs_indices if r == "K1"}
    assert len(k1_slices) == 1, f"Expected 1 K1 slice, got {k1_slices}"
    # The placed slice must be contact slice (index 1) containing pins 11 and 14.
    _, contact_slice_idx = next(iter(k1_slices))
    assert contact_slice_idx == 1, (
        f"Expected contact slice (index 1), got {contact_slice_idx}"
    )


def test_relay_coil_and_contact_owned_by_different_chains() -> None:
    """J1[1] → K1[A1] (coil); J2[1] → K1[11] (contact). Each chain owns its own slice."""
    ir, mapping = _two_connectors_split_relay_ir()
    _blocks, ownership = build_connector_blocks(
        ir, mapping, max_symbols_per_column=4, strict_net_names=False
    )
    # Coil slice owned by J1, contact slice owned by J2.
    j1_owned = {k for k, v in ownership.items() if v == "J1"}
    j2_owned = {k for k, v in ownership.items() if v == "J2"}
    assert ("K1", 0) in j1_owned, (
        f"Coil slice should be owned by J1; J1 owns: {j1_owned}"
    )
    assert ("K1", 1) in j2_owned, (
        f"Contact slice should be owned by J2; J2 owns: {j2_owned}"
    )
    # They are NOT the same connector.
    coil_owner = ownership[("K1", 0)]
    contact_owner = ownership[("K1", 1)]
    assert coil_owner != contact_owner, (
        "Coil and contact must be owned by different connectors"
    )


def test_relay_unowned_slice_not_in_floating_when_partially_placed() -> None:
    """K1's contact slice is wired; coil (A1, A2) is unowned.

    With the 'all-unowned' semantics, K1 must NOT appear in floating because
    its contact slice IS owned by J1.
    """
    ir, mapping = _connector_to_one_relay_contact_ir()
    _blocks, ownership = build_connector_blocks(
        ir, mapping, max_symbols_per_column=4, strict_net_names=False
    )
    floating = find_floating_parts(ir, mapping, ownership)
    # K1 has contact slice placed → NOT fully floating.
    assert not any(fp.part_ref == "K1" for fp in floating), (
        f"K1 must NOT be in floating (contact slice is owned); floating={[f.part_ref for f in floating]}"
    )


def test_find_floating_parts_excludes_partially_placed() -> None:
    """K1 with slice 0 (contact) owned and slice 1 (coil) unowned is NOT floating."""
    ir, mapping = _connector_to_one_relay_contact_ir()
    _blocks, ownership = build_connector_blocks(
        ir, mapping, max_symbols_per_column=4, strict_net_names=False
    )
    # Verify contact slice IS owned.
    assert ("K1", 1) in ownership, "Expected contact slice (index 1) to be owned"
    # Verify coil slice is NOT owned.
    assert ("K1", 0) not in ownership, "Expected coil slice (index 0) to be unowned"

    floating = find_floating_parts(ir, mapping, ownership)
    floating_refs = [fp.part_ref for fp in floating]
    # K1 must not appear because at least one slice is owned.
    assert "K1" not in floating_refs, (
        f"Partially-placed K1 must not appear in floating; got {floating_refs}"
    )


def test_fully_unowned_part_still_floating() -> None:
    """K1 in an IR with NO chains at all → all slices unowned → K1 is floating."""
    ir, mapping = _connector_to_one_relay_contact_ir()
    # Pass an empty ownership dict — as if no chain was walked.
    floating = find_floating_parts(ir, mapping, slice_ownership={})
    assert any(fp.part_ref == "K1" for fp in floating), (
        f"Fully-unowned K1 must appear in floating; got {[f.part_ref for f in floating]}"
    )


def test_slice_label_emitted_when_already_owned_by_other_chain() -> None:
    """J1[1]→K1[11] places contact slice. J2[1]→K1[14] reaches same slice → LABEL."""
    ir, mapping = _two_chains_to_same_contact_slice_ir()
    blocks, _ = build_connector_blocks(
        ir, mapping, max_symbols_per_column=4, strict_net_names=False
    )
    # J1 walks first (declaration order). J2 reaches same slice → LABEL.
    j2_block = next(b for b in blocks if b.connector_ref == "J2")
    cols = j2_block.pin_columns[0].columns
    assert any(c.terminator is Terminator.LABEL for c in cols), (
        f"J2 block should emit LABEL (slice already owned by J1); terminators={[c.terminator for c in cols]}"
    )
