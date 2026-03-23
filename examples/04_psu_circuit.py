"""
Example 04: Power Supply Circuit — PSU Symbol with Dynamic Block

Builds a power supply circuit:
    Terminal (2P: L, N) → 2-pole Circuit Breaker → PSU symbol → Terminal (2P: 24V, GND)

The PSU symbol is a specialized dynamic block with fixed pins:
    Top: L, N, PE  |  Bottom: 24V, GND

Demonstrates the psu symbol (a pre-configured block), multi-pole terminals,
and the unified breaker with poles=2.

API concepts: psu, breaker (poles=2)
"""

from pathlib import Path

from schematika import (
    CircuitBuilder,
    breaker,
    create_initial_state,
    psu,
    render_system,
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
    builder.add_symbol(breaker, tag_prefix="F", poles=2)

    # PSU symbol — fixed pins: top (L, N, PE), bottom (24V, GND)
    # The builder auto-connects the 2 poles from the breaker above
    builder.add_symbol(psu, tag_prefix="U", poles=2)

    # Output terminal — 2 poles for 24V and GND
    builder.add_terminal(tm_id="X3", poles=2)

    result = builder.build(count=1)

    svg_path = str(OUTPUT_DIR / "04_psu_circuit.svg")
    render_system(result.circuit, svg_path)
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
