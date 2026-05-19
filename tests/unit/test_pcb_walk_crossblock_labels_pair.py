"""Both ends of a cross-block CHAIN must emit a LABEL terminator.

Fixture: two connectors J1, J2 each wired through their own relay, with a
shared net name /sig_a appearing as the exit of both relays:

    J1.1 --/coil_in--> K1.A1
    K1.A2 --/sig_a-->  (label — 3-pin bus shared with K2.A2 and another stub)

    J2.1 --/drive_b--> K2.A1
    K2.A2 --/sig_a-->  (same label net)

After build_connector_blocks: J1's block has a LABEL "sig_a" AND J2's block
also has a LABEL "sig_a". Both ends must be visible.

The bug: K1's walk adds "/sig_a" to ctx.visited_nets. When K2's walk later
processes K2.A2 → /sig_a, the visited_nets check skips it, so J2 emits NC
instead of LABEL.
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
from schematika.pcb.walk import build_connector_blocks

# ---------------------------------------------------------------------------
# Symbol factories
# ---------------------------------------------------------------------------


def _two_port_symbol(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 1), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label=label or "relay",
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_conn_1p_template = type(
    "conn_1p",
    (),
    {"name": "conn_1p", "pins": [SimpleNamespace(num="1")]},
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
# Test
# ---------------------------------------------------------------------------


def test_chain_via_relay_emits_label_at_both_ends() -> None:
    """Both J1 and J2 must emit LABEL 'sig_a' even though /sig_a hits visited_nets
    during J1's walk before J2 has a chance to process it."""
    relay_slice = SymbolSlice(
        symbol=_two_port_symbol,
        pin_map={"A1": "top", "A2": "bottom"},
    )
    mapping = SymbolMapping(
        symbols=(SymbolMap(template=_relay_spst_template, slices=(relay_slice,)),),
        connectors=(ConnectorMap(template=_conn_1p_template),),
        power_nets=(),
    )

    # /sig_a has 3 pins: K1.A2, K2.A2, and a stub ref "S1.1" (makes it LABEL-class)
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(ref="J2", template_name="conn_1p", pin_numbers=("1",)),
            PartRef(ref="K1", template_name="relay_spst", pin_numbers=("A1", "A2")),
            PartRef(ref="K2", template_name="relay_spst", pin_numbers=("A1", "A2")),
        ),
        nets=(
            # J1.1 → K1.A1 (CHAIN: 2-pin net)
            NetRef(name="/coil_in", pins=(PinRef("J1", "1"), PinRef("K1", "A1"))),
            # J2.1 → K2.A1 (CHAIN: 2-pin net)
            NetRef(name="/drive_b", pins=(PinRef("J2", "1"), PinRef("K2", "A1"))),
            # /sig_a: 3-pin net (LABEL class) — exits of both K1 and K2
            NetRef(
                name="/sig_a",
                pins=(PinRef("K1", "A2"), PinRef("K2", "A2"), PinRef("K1", "A2")),
            ),
        ),
        nc_pins=(),
    )

    blocks, _ = build_connector_blocks(
        ir, mapping, max_symbols_per_column=8, strict_net_names=False
    )

    j1_block = next(b for b in blocks if b.connector_ref == "J1")
    j2_block = next(b for b in blocks if b.connector_ref == "J2")

    j1_labels = {
        col.terminator_label
        for pc in j1_block.pin_columns
        for col in pc.columns
        if col.terminator is Terminator.LABEL
    }
    j2_labels = {
        col.terminator_label
        for pc in j2_block.pin_columns
        for col in pc.columns
        if col.terminator is Terminator.LABEL
    }

    assert "sig_a" in j1_labels, f"J1 missing label 'sig_a': {j1_labels}"
    assert "sig_a" in j2_labels, f"J2 missing label 'sig_a': {j2_labels}"
