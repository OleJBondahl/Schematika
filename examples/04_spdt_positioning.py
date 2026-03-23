"""
Example 04: SPDT Contact with Relative Positioning

Builds an SPDT (Single-Pole Double-Throw) changeover contact with terminals
positioned relative to specific pins:
    Terminal (above NC pin "12") --+
                                   |-- SPDT contact
    Terminal (below NO pin "14") --+

Concepts taught:
    - add_spdt(): changeover contact with COM/NC/NO branches
    - relative_to + position: place terminals above/below specific pins
    - connect(): explicit wiring between non-chain components
    - Pin references: spdt.pin("12") to target specific SPDT pins
    - Wire labels on individual connections via wire_label parameter

Based on: auxillary_cabinet_v3/src/circuits/power_switching.py
"""

from pathlib import Path

from schematika import (
    GRID_SIZE,
    SPACING_STANDARD,
    CircuitBuilder,
    WireLabels,
    create_initial_state,
    render_system,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Distance from SPDT port to the terminal center
_SPDT_PORT_GAP = SPACING_STANDARD - GRID_SIZE


def main():
    state = create_initial_state()

    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)

    # SPDT contact: pins "11" (COM), "12" (NC), "14" (NO)
    # SPDT doesn't participate in the vertical chain — it branches
    spdt = builder.add_spdt(tag_prefix="K", poles=1)

    # Terminal ABOVE the NC pin ("12") — emergency/alternate supply
    # relative_to=spdt.pin("12") positions this terminal directly above pin 12
    # connect_from_previous=True (default) auto-wires the terminal to the pin
    builder.add_terminal(
        tm_id="X1",
        relative_to=spdt.pin("12"),
        position="above",
        label_pos="left",
        spacing=_SPDT_PORT_GAP,
        wire_label=WireLabels.BR_1_5,
    )

    # Terminal ABOVE the NO pin ("14") — main supply
    builder.add_terminal(
        tm_id="X2",
        relative_to=spdt.pin("14"),
        position="above",
        label_pos="right",
        spacing=_SPDT_PORT_GAP,
        wire_label=WireLabels.BR_1_5,
    )

    # Terminal BELOW the COM pin ("11") — switched output
    builder.add_terminal(
        tm_id="X3",
        relative_to=spdt.pin("11"),
        position="below",
        label_pos="left",
        spacing=_SPDT_PORT_GAP,
        wire_label=WireLabels.BR_1_5,
    )

    result = builder.build(count=1)

    svg_path = str(OUTPUT_DIR / "04_spdt_positioning.svg")
    render_system(result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
