"""
Example 04: Power Supply Circuit — PSU Symbol with Dynamic Block

Builds a power supply circuit:
    Terminal (2P: L, N) → 2-pole Circuit Breaker → PSU symbol → Terminal (2P: 24V, GND)

The PSU symbol is a specialized dynamic block with fixed pins:
    Top: L, N, PE  |  Bottom: 24V, GND

Demonstrates the psu_symbol (a pre-configured dynamic_block_symbol),
multi-pole terminals, and custom pin configurations.

API concepts: psu_symbol, two_pole_circuit_breaker_symbol, CB_2P_PINS
"""

from pathlib import Path

from schematika import (
    CB_2P_PINS,
    CircuitBuilder,
    create_initial_state,
    psu_symbol,
    render_system,
    two_pole_circuit_breaker_symbol,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    state = create_initial_state()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=150)

    # Input terminal — 2 poles for L and N
    builder.add_terminal(tm_id="X1", poles=2)

    # 2-pole circuit breaker protecting the PSU input
    builder.add_symbol(
        two_pole_circuit_breaker_symbol,
        tag_prefix="F",
        poles=2,
        pins=CB_2P_PINS,
    )

    # PSU symbol — fixed pins: top (L, N, PE), bottom (24V, GND)
    # The builder auto-connects the 2 poles from the breaker above
    builder.add_symbol(psu_symbol, tag_prefix="U", poles=2)

    # Output terminal — 2 poles for 24V and GND
    builder.add_terminal(tm_id="X3", poles=2)

    result = builder.build(count=1)

    svg_path = str(OUTPUT_DIR / "04_psu_circuit.svg")
    render_system(result.circuit, svg_path)
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
