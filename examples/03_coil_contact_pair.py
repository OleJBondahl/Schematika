"""
Example 03: Coil-Contact Pair with Tag Reuse and Count

Builds paired coil and contact circuits that share a relay tag:
    Coil circuit:    Terminal -> K coil -> Terminal
    Contact circuit: Terminal -> K NO contact -> Terminal

The contact circuit reuses K tags from the coil circuit so both reference
the same physical relay. Uses count=2 to generate two identical pairs,
demonstrating how autonumbering produces K1+K1 and K2+K2.

Concepts taught:
    - reuse_tags: share component tags across separate builders
    - State threading: contact_builder starts from coil_builder.state
    - count > 1: generate multiple instances with auto-incrementing tags
    - CircuitBuilder.merge(): combine separate builders into one circuit
    - Wire labels on control circuits (0.5mm² wires)

Based on: auxillary_cabinet_v3/src/circuits/valve_control.py
"""

from pathlib import Path

from schematika import (
    CIRCUIT_SPACING_NARROW,
    GRID_SIZE,
    CircuitBuilder,
    WireLabels,
    coil,
    create_initial_state,
    no_contact,
    render_system,
)
from schematika.core.options import SymbolConfig, TerminalConfig

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Wire labels for the coil side: 2 segments per instance (terminal->coil, coil->terminal)
COIL_WIRE_LABELS = [WireLabels.WH_0_5, WireLabels.BK_0_5]

# Wire labels for the contact side: 2 segments per instance
CONTACT_WIRE_LABELS = [WireLabels.RD_0_5, WireLabels.WH_0_5]

COUNT = 2


def main():
    state = create_initial_state()

    # Horizontal offset between coil and its paired contact
    sub_spacing = 5 * GRID_SIZE

    # --- Coil circuits (drives K tag allocation: K1, K2, ...) ---
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING_NARROW)

    coil_builder.add_terminal("X1", config=TerminalConfig(poles=1))
    coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    coil_builder.add_terminal("X2", config=TerminalConfig(poles=1))

    # count=2 produces two instances: K1 coil and K2 coil
    # Wire labels are repeated for each instance: 2 labels * 2 instances
    coil_builder.build(count=COUNT, wire_labels=COIL_WIRE_LABELS * COUNT)

    # --- Contact circuits (reuses K tags from coil builder) ---
    # Thread state so terminal/tag counters continue from where coil left off
    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=sub_spacing, y=0, spacing=CIRCUIT_SPACING_NARROW)

    contact_builder.add_terminal("X3", config=TerminalConfig(poles=1))
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
    contact_builder.add_terminal("X4", config=TerminalConfig(poles=1))

    # reuse_tags={"K": coil_builder.result} makes this contact use K1, K2
    # instead of allocating new K3, K4
    contact_builder.build(
        count=COUNT,
        reuse_tags={"K": coil_builder.result},
        wire_labels=CONTACT_WIRE_LABELS * COUNT,
    )

    # --- Merge both builders into a single circuit for rendering ---
    merged = CircuitBuilder.merge(coil_builder, contact_builder)

    svg_path = str(OUTPUT_DIR / "03_coil_contact_pair.svg")
    render_system(merged.result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
