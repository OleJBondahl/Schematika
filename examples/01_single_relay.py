"""
Example 01: Single Relay Circuit — Minimal Schematika Circuit

Builds the simplest possible circuit: two terminals connected through a
relay coil symbol.  Demonstrates the core workflow:

    1. Create autonumbering state
    2. Instantiate CircuitBuilder with state
    3. Configure layout (origin, spacing)
    4. Add terminals and symbols to the vertical chain
    5. Build the circuit (returns BuildResult)
    6. Render to SVG

API concepts: CircuitBuilder, add_terminal, add_symbol, build, render_system
"""

from pathlib import Path

from schematika import (
    CircuitBuilder,
    coil,
    create_initial_state,
    render_system,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    # 1. Create shared autonumbering state — tracks tag counters (K1, K2, ...)
    state = create_initial_state()

    # 2. Create a builder and configure its layout origin
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    # 3. Build a vertical chain: terminal → coil → terminal
    #    add_terminal auto-connects to the previous component in the chain
    builder.add_terminal(tm_id="X1", poles=1)
    builder.add_symbol(coil, tag_prefix="K", poles=1)
    builder.add_terminal(tm_id="X2", poles=1)

    # 4. Build produces a BuildResult (circuit, updated state, used terminals)
    result = builder.build(count=1)

    # 5. Render the circuit to SVG
    svg_path = str(OUTPUT_DIR / "01_single_relay.svg")
    render_system(result.circuit, svg_path)
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
