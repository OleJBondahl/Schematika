"""
Example 02: DOL Motor Starter with Wire Labels

Builds a real 3-phase Direct-On-Line motor starter with IEC wire labels:
    Terminal (3P) -> Breaker (3P) -> Contactor (3P) ->
    Thermal Overload (3P) -> Terminal (3P)

Concepts taught:
    - Wire labels: IEC color+gauge annotations on vertical wires
    - WireLabels constants: pre-defined IEC 60757 color/cross-section pairs
    - Multi-pole components: poles=3 auto-selects IEC pin configurations
    - Terminal pin labels: pins=("L1","L2","L3") for named output poles

Based on: auxillary_cabinet_v3/src/circuits/pump_circuit.py
"""

from pathlib import Path

from schematika import (
    CircuitBuilder,
    WireLabels,
    breaker,
    contactor,
    create_initial_state,
    motor,
    render_system,
    thermal_overload,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Wire labels: one per vertical wire segment (12 total for this circuit).
# The label count must EXACTLY match the number of vertical wires, or
# WireLabelMismatchError is raised. Count wires by examining the rendered SVG.
WIRE_LABELS = [
    # Terminal -> Breaker (3 poles: brown, black, grey — 2.5mm²)
    WireLabels.BR_2_5,
    WireLabels.BK_2_5,
    WireLabels.GY_2_5,
    # Breaker -> Contactor
    WireLabels.BR_2_5,
    WireLabels.BK_2_5,
    WireLabels.GY_2_5,
    # Contactor -> Thermal Overload -> Motor -> Terminal
    # (some segments are internal to multi-pole symbols)
    WireLabels.BR_2_5,
    WireLabels.BK_2_5,
    WireLabels.GY_2_5,
    WireLabels.BR_2_5,
    WireLabels.BK_2_5,
    WireLabels.GY_2_5,
]


def main():
    state = create_initial_state()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    # Top terminal — 3-phase power input
    builder.add_terminal("X1", poles=3)

    # 3-pole circuit breaker
    builder.add_symbol(breaker, tag_prefix="F", poles=3)

    # 3-pole contactor
    builder.add_symbol(contactor, tag_prefix="Q", poles=3)

    # 3-pole thermal overload relay (IEC tag prefix: FT)
    builder.add_symbol(thermal_overload, tag_prefix="FT", poles=3)

    # 3-phase motor
    builder.add_symbol(motor, tag_prefix="M", poles=3)

    # Output terminal — named poles for motor cable
    builder.add_terminal("X2", poles=3, pins=("U1", "V1", "W1"))

    # wire_labels assigns IEC color+gauge annotations to each vertical wire
    result = builder.build(count=1, wire_labels=WIRE_LABELS)

    svg_path = str(OUTPUT_DIR / "02_dol_starter.svg")
    render_system(result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
