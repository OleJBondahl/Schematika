"""
Example 03: Control Circuit — Relay Coil + Contact with Tag Reuse

Builds two separate circuits that share the same relay tag:
    Circuit A (coil):    terminal → K coil → terminal
    Circuit B (contact): terminal → K NO contact → terminal

The contact circuit reuses the K tag from the coil circuit via reuse_tags,
so both circuits reference the same physical relay (e.g., K1).

API concepts: state threading, reuse_tags, BuildResult, cross-circuit references
"""

from pathlib import Path

from schematika import (
    CircuitBuilder,
    coil,
    create_initial_state,
    no_contact,
    render_system,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    state = create_initial_state()

    # --- Circuit A: Coil circuit ---
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=100)

    coil_builder.add_terminal(tm_id="X1", poles=1)
    coil_builder.add_symbol(coil, tag_prefix="K", poles=1)
    coil_builder.add_terminal(tm_id="X2", poles=1)

    # Build the coil circuit — this allocates K1
    coil_builder.build(count=1)

    # --- Circuit B: Contact circuit ---
    # Thread state from coil builder so tag counters continue correctly
    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=120, y=0, spacing=100)

    contact_builder.add_terminal(tm_id="X3", poles=1)
    contact_builder.add_symbol(no_contact, tag_prefix="K", poles=1)
    contact_builder.add_terminal(tm_id="X4", poles=1)

    # reuse_tags: the "K" prefix reuses tags from the coil BuildResult,
    # so this contact gets K1 (matching the coil) instead of allocating K2
    contact_builder.build(
        count=1,
        reuse_tags={"K": coil_builder.result},
    )

    # Render both circuits to separate SVG files
    coil_svg = str(OUTPUT_DIR / "03_coil_circuit.svg")
    render_system(coil_builder.circuit, coil_svg)
    print(f"Rendered coil circuit:    {coil_svg}")

    contact_svg = str(OUTPUT_DIR / "03_contact_circuit.svg")
    render_system(contact_builder.circuit, contact_svg)
    print(f"Rendered contact circuit: {contact_svg}")


if __name__ == "__main__":
    main()
