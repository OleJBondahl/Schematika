"""
Example 04: SPDT Contact with Relative Positioning

Builds a 2-pole changeover (SPDT) switch with terminals placed relative
to each pin using position="above" and position="below":

    X1 (NC supply)  X2 (NO supply)
         |               |
         12    14
          K1 SPDT
              11
              |
         X3 (output)

Repeated for 2 poles, showing how relative_to spreads terminals across
the multi-pole SPDT.

Concepts taught:
    - add_spdt(): multi-pole changeover contact
    - relative_to + position: place terminals above/below specific pins
    - connect_from_previous=False: break the vertical auto-wiring chain
    - wire_label on add_terminal: label individual wire segments
    - Loop-based terminal creation for multi-pole patterns
    - label_pos="left"/"right": control which side labels appear

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

# Distance from SPDT port to terminal center (standard spacing minus grid)
_SPDT_PORT_GAP = SPACING_STANDARD - GRID_SIZE

# IEC phase wire colors for each pole
PHASE_COLORS = [WireLabels.BR_1_5, WireLabels.BK_1_5]


def main():
    state = create_initial_state()

    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)

    # 2-pole SPDT changeover contact
    # IEC pins: pole 1 = 11(COM), 12(NC), 14(NO)
    #           pole 2 = 21(COM), 22(NC), 24(NO)
    spdt = builder.add_spdt("K", poles=2)

    # For each pole, place terminals above NC/NO pins and below COM pin
    for i in range(2):
        p = i + 1  # Pole number: 1, 2
        wire_color = PHASE_COLORS[i]

        # Terminal ABOVE the NC pin (e.g., pin "12" for pole 1)
        # This is the "emergency / alternate" supply input
        builder.add_terminal(
            "X1",
            relative_to=spdt.pin(f"{p}2"),  # NC pin
            position="above",
            label_pos="left",
            spacing=_SPDT_PORT_GAP,
            wire_label=wire_color,
        )

        # Terminal ABOVE the NO pin (e.g., pin "14" for pole 1)
        # This is the "main" supply input
        builder.add_terminal(
            "X2",
            relative_to=spdt.pin(f"{p}4"),  # NO pin
            position="above",
            label_pos="right",
            spacing=_SPDT_PORT_GAP,
            wire_label=wire_color,
        )

        # Terminal BELOW the COM pin (e.g., pin "11" for pole 1)
        # This is the switched output
        builder.add_terminal(
            "X3",
            relative_to=spdt.pin(f"{p}1"),  # COM pin
            position="below",
            label_pos="left",
            spacing=_SPDT_PORT_GAP,
            wire_label=wire_color,
        )

    result = builder.build(count=1)

    svg_path = str(OUTPUT_DIR / "04_spdt_positioning.svg")
    render_system(result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
