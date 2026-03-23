"""
Example 02: DOL Motor Starter — Multi-Pole 3-Phase Circuit

Builds a standard Direct-On-Line motor starter:
    Terminal (3P) → Circuit Breaker (3P) → Contactor (3P) →
    Thermal Overload (3P) → Motor (3P) → Terminal (3P)

Demonstrates multi-pole components and standard IEC pin sets.

API concepts: poles, pins (CB_3P_PINS, CONTACTOR_3P_PINS, etc.), multi-pole chain
"""

from pathlib import Path

from schematika import (
    CB_3P_PINS,
    CONTACTOR_3P_PINS,
    THERMAL_OVERLOAD_PINS,
    CircuitBuilder,
    circuit_breaker_symbol,
    contactor_symbol,
    create_initial_state,
    render_system,
    thermal_overload_symbol,
    three_pole_motor_symbol,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    state = create_initial_state()

    builder = CircuitBuilder(state)
    # spacing = horizontal distance between instances when count > 1
    builder.set_layout(x=0, y=0, spacing=150)

    # Top terminal — 3-pole power input
    builder.add_terminal(tm_id="X1", poles=3)

    # 3-pole circuit breaker with IEC pin labels (1-2, 3-4, 5-6)
    builder.add_symbol(circuit_breaker_symbol, tag_prefix="F", poles=3, pins=CB_3P_PINS)

    # 3-pole contactor with IEC pin labels (L1-T1, L2-T2, L3-T3)
    builder.add_symbol(
        contactor_symbol, tag_prefix="Q", poles=3, pins=CONTACTOR_3P_PINS
    )

    # 3-pole thermal overload relay
    builder.add_symbol(
        thermal_overload_symbol,
        tag_prefix="F",
        poles=3,
        pins=THERMAL_OVERLOAD_PINS,
    )

    # 3-pole motor
    builder.add_symbol(three_pole_motor_symbol, tag_prefix="M", poles=3)

    # Bottom terminal — motor cable connection
    builder.add_terminal(tm_id="X2", poles=3)

    result = builder.build(count=1)

    svg_path = str(OUTPUT_DIR / "02_dol_starter.svg")
    render_system(result.circuit, svg_path)
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
