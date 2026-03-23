"""
Example 05: Full Cabinet — Project API with Multiple Circuits + PDF

Uses the Project API to combine multiple circuits into a multi-page PDF:
    - Registers terminal definitions
    - Adds a relay coil circuit and a DOL motor starter circuit
    - Defines pages (schematic pages + terminal report)
    - Compiles everything to PDF

Demonstrates the top-level declarative workflow for complete drawing sets.

API concepts: Project, add_circuit, terminals, page, terminal_report, build

Requires the [pdf] extra: pip install schematika[pdf]
"""

from pathlib import Path

from schematika import (
    BuildResult,
    CircuitBuilder,
    Project,
    Terminal,
    breaker,
    coil,
    contactor,
    motor,
    no_contact,
    thermal_overload,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# --- Circuit builder functions ---
# Each receives state and returns a BuildResult.


def relay_circuit(state) -> BuildResult:
    """Coil + contact pair sharing the K tag."""
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=100)
    coil_builder.add_terminal(tm_id="X1", poles=1)
    coil_builder.add_symbol(coil, tag_prefix="K", poles=1)
    coil_builder.add_terminal(tm_id="X2", poles=1)
    coil_builder.build(count=1)

    contact = CircuitBuilder(coil_builder.state)
    contact.set_layout(x=120, y=0, spacing=100)
    contact.add_terminal(tm_id="X1", poles=1)
    contact.add_symbol(no_contact, tag_prefix="K", poles=1)
    contact.add_terminal(tm_id="X2", poles=1)
    contact.build(count=1, reuse_tags={"K": coil_builder.result})

    return CircuitBuilder.merge(coil_builder, contact).result


def motor_circuit(state) -> BuildResult:
    """3-phase DOL motor starter."""
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=150)

    builder.add_terminal(tm_id="X3", poles=3)
    builder.add_symbol(breaker, tag_prefix="F", poles=3)
    builder.add_symbol(contactor, tag_prefix="Q", poles=3)
    builder.add_symbol(thermal_overload, tag_prefix="F", poles=3)
    builder.add_symbol(motor, tag_prefix="M", poles=3)
    builder.add_terminal(tm_id="X4", poles=3)

    builder.build(count=1)

    return builder.result


def main():
    # Create a Project — the top-level declarative API
    project = Project(
        title="Example Cabinet",
        drawing_number="EX-005",
        author="Schematika",
        project="Examples",
        revision="01",
    )

    # Register terminal definitions (used in terminal reports)
    project.terminals(
        Terminal("X1", "Control Power 24V"),
        Terminal("X2", "Control Ground"),
        Terminal("X3", "Motor Power 400V"),
        Terminal("X4", "Motor Cable"),
    )

    # Register circuits — each builder_fn receives state, returns BuildResult
    project.add_circuit("relay", relay_circuit)
    project.add_circuit("motor", motor_circuit)

    # Define pages for the PDF
    project.page("Relay Control", "relay")
    project.page("Motor Starter", "motor")
    project.terminal_report()

    # Build: generates SVGs, terminal CSVs, and compiles to PDF
    pdf_path = str(OUTPUT_DIR / "05_full_cabinet.pdf")
    project.build(pdf_path, temp_dir=str(OUTPUT_DIR / "temp"))

    print(f"Compiled PDF: {pdf_path}")


if __name__ == "__main__":
    main()
