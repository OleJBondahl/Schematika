"""
Example 05: Multi-Builder Merge with Block and BridgeMode

Builds three sub-circuits that share a relay tag, then merges them:
    A) Coil circuit:    Terminal -> K coil -> Terminal
    B) Block circuit:   PLC refs -> K block (custom pins) -> Terminal
    C) Contact circuit: Terminal -> K NO contact -> Terminal (reuses K tag)

Concepts taught:
    - Multi-builder pattern: separate builders for coil, block, contact
    - block symbol: custom top_pins/bottom_pins for routing
    - connect(): explicit wiring from block pins to terminal poles
    - reuse_tags: share K tag between coil and contact sub-circuits
    - CircuitBuilder.merge(): combine 3+ builders into one circuit
    - connect_from_previous=False: opt out of automatic chain wiring
    - add_reference(): PLC I/O reference arrows

Based on: auxillary_cabinet_v3/src/circuits/fan_controll.py
"""

from pathlib import Path

from schematika import (
    CIRCUIT_SPACING,
    SPACING_STANDARD,
    CircuitBuilder,
    WireLabels,
    block,
    coil,
    create_initial_state,
    no_contact,
    render_system,
)
from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    PlacementOptions,
    SymbolConfig,
    TerminalConfig,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

COIL_WIRE_LABELS = [WireLabels.BR_1_5, WireLabels.BL_1_5]
BLOCK_WIRE_LABELS = [
    WireLabels.WH_0_5,
    WireLabels.WH_0_5,
    WireLabels.WH_0_5,
    WireLabels.WH_0_5,
]
CONTACT_WIRE_LABELS = [WireLabels.RD_0_5, WireLabels.WH_0_5]


def main():
    state = create_initial_state()
    sub_spacing = SPACING_STANDARD

    # ---- Sub-circuit A: Relay coil ----
    # The coil builder drives K tag allocation (K1)
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=2 * CIRCUIT_SPACING)

    coil_ref = coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))

    # Terminals placed relative to coil pins (not in the vertical chain)
    coil_builder.add_terminal(
        "X1",
        config=TerminalConfig(poles=1),
        placement=PlacementOptions(relative_to=coil_ref.pin("A1"), position="above"),
    )
    coil_builder.add_terminal(
        "X1",
        config=TerminalConfig(poles=1),
        placement=PlacementOptions(relative_to=coil_ref.pin("A2"), position="below"),
    )

    coil_builder.build(options=BuildOptions(count=1, wire_labels=COIL_WIRE_LABELS))

    # ---- Sub-circuit B: Dynamic block (sensor I/O routing) ----
    # The block reuses K tags from the coil so it gets the same K1
    block_builder = CircuitBuilder(coil_builder.state)
    block_builder.set_layout(x=sub_spacing, y=0, spacing=2 * CIRCUIT_SPACING)

    # block with custom pins: y1,y2 on top, t1,t2 on bottom
    # connect_from_previous=False because it's not in a vertical chain
    block_ref = block_builder.add_symbol(
        block,
        config=SymbolConfig(
            tag_prefix="K",
            pins=("y1", "y2", "t1", "t2"),
            factory_kwargs={"top_pins": ("y1", "y2"), "bottom_pins": ("t1", "t2")},
        ),
        connection=ConnectionOptions(connect_from_previous=False),
    )

    # PLC reference arrows above block pins
    block_builder.add_reference(
        "PLC:DO1",
        placement=PlacementOptions(relative_to=block_ref.pin("y1"), position="above"),
        direction="up",
        label_pos="left",
    )
    block_builder.add_reference(
        "PLC:DO2",
        placement=PlacementOptions(relative_to=block_ref.pin("y2"), position="above"),
        direction="up",
        label_pos="right",
    )

    # Output terminal below the block — not auto-connected
    tm_bot = block_builder.add_terminal(
        "X2",
        config=TerminalConfig(poles=2),
        connection=ConnectionOptions(
            connect_to_next=False, connect_from_previous=False
        ),
    )

    # Explicit wiring: block bottom pins -> terminal poles
    block_builder.connect(
        block_ref.pin("t1"), tm_bot.pole(0), side_a="bottom", side_b="top"
    )
    block_builder.connect(
        block_ref.pin("t2"), tm_bot.pole(1), side_a="bottom", side_b="top"
    )

    block_builder.build(
        options=BuildOptions(
            count=1,
            reuse_tags={"K": coil_builder.result},
            wire_labels=BLOCK_WIRE_LABELS,
        )
    )

    # ---- Sub-circuit C: NO contact reusing K from coil ----
    contact_builder = CircuitBuilder(block_builder.state)
    contact_builder.set_layout(x=2 * sub_spacing, y=0, spacing=2 * CIRCUIT_SPACING)

    # Top terminal for power feed
    contact_builder.add_terminal("X3", config=TerminalConfig(poles=1))

    # NO contact — reuses K1 tag from the coil builder via reuse_tags
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))

    # Output terminal
    contact_builder.add_terminal("X4", config=TerminalConfig(poles=1))

    # reuse_tags ensures this contact gets the same K1 tag as the coil
    contact_builder.build(
        options=BuildOptions(
            count=1,
            reuse_tags={"K": coil_builder.result},
            wire_labels=CONTACT_WIRE_LABELS,
        )
    )

    # ---- Merge all three sub-circuits ----
    merged = CircuitBuilder.merge(coil_builder, block_builder, contact_builder)

    svg_path = str(OUTPUT_DIR / "05_multi_builder.svg")
    render_system(merged.result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
