"""
Example 06: Full Cabinet — Project API with Real Circuits and PDF

Uses the Project API to combine multiple circuits into a multi-page PDF:
    - Registers terminal definitions
    - Adds a DOL starter, coil-contact pair, and SPDT circuit
    - Defines schematic pages and a terminal report
    - Compiles everything to PDF

Concepts taught:
    - Project: top-level declarative API for complete drawing sets
    - Terminal: named terminal definitions for terminal reports
    - add_circuit: register circuit builder functions
    - page: assign circuits to PDF pages
    - terminal_report: auto-generated terminal allocation table
    - build: compile SVGs + CSVs into multi-page PDF

Requires the [pdf] extra: pip install schematika[pdf]

Based on: auxillary_cabinet_v3/src/cabinet.py
"""

from pathlib import Path

from schematika import (
    CIRCUIT_SPACING_NARROW,
    GRID_SIZE,
    SPACING_STANDARD,
    BuildResult,
    CircuitBuilder,
    Project,
    Terminal,
    WireLabels,
    breaker,
    coil,
    contactor,
    no_contact,
    thermal_overload,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# --- Circuit builder functions ---
# Each receives state and returns a BuildResult.
# These are simplified versions of the real circuits from examples 02-04.


def dol_starter(state) -> BuildResult:
    """3-phase DOL motor starter with wire labels."""
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    builder.add_terminal(tm_id="X1", poles=3)
    builder.add_symbol(breaker, tag_prefix="F", poles=3)
    builder.add_symbol(contactor, tag_prefix="Q", poles=3)
    builder.add_symbol(thermal_overload, tag_prefix="F", poles=3)
    builder.add_terminal(tm_id="X2", poles=3, pins=("L1", "L2", "L3"))

    wire_labels = [
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,
    ] * 4

    builder.build(count=1, wire_labels=wire_labels)
    return builder.result


def relay_control(state) -> BuildResult:
    """Coil + contact pair sharing the K tag, with wire labels."""
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING_NARROW)

    coil_builder.add_terminal(tm_id="X3", poles=1)
    coil_builder.add_symbol(coil, tag_prefix="K")
    coil_builder.add_terminal(tm_id="X4", poles=1)
    coil_builder.build(count=1, wire_labels=[WireLabels.WH_0_5, WireLabels.BK_0_5])

    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=5 * GRID_SIZE, y=0, spacing=CIRCUIT_SPACING_NARROW)

    contact_builder.add_terminal(tm_id="X5", poles=1)
    contact_builder.add_symbol(no_contact, tag_prefix="K")
    contact_builder.add_terminal(tm_id="X6", poles=1)
    contact_builder.build(
        count=1,
        reuse_tags={"K": coil_builder.result},
        wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5],
    )

    return CircuitBuilder.merge(coil_builder, contact_builder).result


def spdt_circuit(state) -> BuildResult:
    """SPDT changeover with terminals on NC/NO/COM pins."""
    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)

    gap = SPACING_STANDARD - GRID_SIZE

    spdt = builder.add_spdt(tag_prefix="K", poles=1)

    builder.add_terminal(
        tm_id="X7",
        relative_to=spdt.pin("12"),
        position="above",
        spacing=gap,
        wire_label=WireLabels.BR_1_5,
    )
    builder.add_terminal(
        tm_id="X8",
        relative_to=spdt.pin("14"),
        position="above",
        spacing=gap,
        wire_label=WireLabels.BR_1_5,
    )
    builder.add_terminal(
        tm_id="X9",
        relative_to=spdt.pin("11"),
        position="below",
        spacing=gap,
        wire_label=WireLabels.BR_1_5,
    )

    builder.build(count=1)
    return builder.result


def main():
    # Verify create_initial_state isn't needed here — Project handles it internally
    project = Project(
        title="Example Cabinet",
        drawing_number="EX-006",
        author="Schematika",
        project="Examples",
        revision="01",
    )

    # Register terminal definitions — these appear in the terminal report
    project.terminals(
        Terminal("X1", "Main Power 400V"),
        Terminal("X2", "Motor Cable"),
        Terminal("X3", "Control Power 24V"),
        Terminal("X4", "Control Ground"),
        Terminal("X5", "Switched 230V"),
        Terminal("X6", "Valve Output"),
        Terminal("X7", "Emergency Supply"),
        Terminal("X8", "Main Supply"),
        Terminal("X9", "Switched Output"),
    )

    # Register circuit builder functions — each receives state, returns BuildResult
    project.add_circuit("motor", dol_starter)
    project.add_circuit("relay", relay_control)
    project.add_circuit("changeover", spdt_circuit)

    # Define pages — each page can show one or more circuits
    project.page("Motor Starter", "motor")
    project.page("Relay Control", "relay")
    project.page("Power Changeover", "changeover")
    project.terminal_report()

    # Build: generates SVGs, terminal CSVs, and compiles to PDF
    pdf_path = str(OUTPUT_DIR / "06_full_cabinet.pdf")
    project.build(pdf_path, temp_dir=str(OUTPUT_DIR / "temp"))

    print(f"Compiled PDF: {pdf_path}")


if __name__ == "__main__":
    main()
