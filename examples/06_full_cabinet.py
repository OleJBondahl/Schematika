"""
Example 06: Full Cabinet — Project API combining all example circuits

Uses the Project API to combine circuits from examples 02-05 into a
multi-page A3 PDF with title block and terminal report.

Pages:
    1. Motor Starter  (from example 02 — DOL starter with wire labels)
    2. Relay Control   (from example 03 — coil + contact pair)
    3. Power Changeover (from example 04 — SPDT with relative positioning)
    4. Terminal Report  (auto-generated from all circuits)

Concepts taught:
    - Project: top-level API for complete drawing sets
    - Terminal: named terminal definitions for reports
    - add_circuit: register circuit builder functions
    - page: assign circuits to PDF pages
    - terminal_report: auto-generated terminal allocation table
    - build: compile SVGs + CSVs into multi-page PDF
    - Composing real circuits into a project

Requires the [pdf] extra: pip install schematika[pdf]

Based on: auxillary_cabinet_v3/src/cabinet.py
"""

from pathlib import Path

from schematika import (
    CIRCUIT_SPACING,
    GRID_SIZE,
    SPACING_STANDARD,
    BuildResult,
    CircuitBuilder,
    Terminal,
    WireLabels,
    breaker,
    coil,
    contactor,
    motor,
    no_contact,
    thermal_overload,
)
from schematika.project import Project

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Circuit builder functions — each receives state, returns BuildResult.
# These match the standalone examples 02-04 exactly.
# ---------------------------------------------------------------------------


def dol_starter(state) -> BuildResult:
    """3-phase DOL motor starter (example 02).

    X1 -> F1(breaker) -> Q1(contactor) -> FT1(thermal) -> M1(motor) -> X2
    """
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    builder.add_terminal("X1", poles=3)
    builder.add_symbol(breaker, tag_prefix="F", poles=3)
    builder.add_symbol(contactor, tag_prefix="Q", poles=3)
    builder.add_symbol(thermal_overload, tag_prefix="FT", poles=3)
    builder.add_symbol(motor, tag_prefix="M", poles=3)
    builder.add_terminal("X2", poles=3, pins=("U1", "V1", "W1"))

    # 12 vertical wires: 3 poles × 4 visible segments
    wire_labels = [
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,  # X1→F1
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,  # F1→Q1
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,  # →FT1→M1
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,  # →X2
    ]

    builder.build(count=1, wire_labels=wire_labels)
    return builder.result


def relay_control(state) -> BuildResult:
    """Coil + NO contact pair sharing K tag (example 03).

    Left:  X3 -> K1(coil) -> X4
    Right: X5 -> K1(NO contact) -> X6  (reuses K1 tag from coil)
    """
    # Coil sub-circuit
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING)
    coil_builder.add_terminal("X3", poles=1)
    coil_builder.add_symbol(coil, tag_prefix="K")
    coil_builder.add_terminal("X4", poles=1)
    coil_builder.build(count=1, wire_labels=[WireLabels.WH_0_5, WireLabels.BK_0_5])

    # Contact sub-circuit — reuses K1 tag
    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=5 * GRID_SIZE, y=0, spacing=CIRCUIT_SPACING)
    contact_builder.add_terminal("X5", poles=1)
    contact_builder.add_symbol(no_contact, tag_prefix="K")
    contact_builder.add_terminal("X6", poles=1)
    contact_builder.build(
        count=1,
        reuse_tags={"K": coil_builder.result},
        wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5],
    )

    return CircuitBuilder.merge(coil_builder, contact_builder).result


def changeover_switch(state) -> BuildResult:
    """2-pole SPDT changeover with relative positioning (example 04).

    Per pole: X7(NC above) + X8(NO above) -> K2(SPDT) -> X9(COM below)
    """
    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)

    gap = SPACING_STANDARD - GRID_SIZE
    phase_colors = [WireLabels.BR_1_5, WireLabels.BK_1_5]

    spdt = builder.add_spdt("K", poles=2)

    for i in range(2):
        p = i + 1
        wl = phase_colors[i]

        builder.add_terminal(
            "X7",
            relative_to=spdt.pin(f"{p}2"),
            position="above",
            label_pos="left",
            spacing=gap,
            wire_label=wl,
        )
        builder.add_terminal(
            "X8",
            relative_to=spdt.pin(f"{p}4"),
            position="above",
            label_pos="right",
            spacing=gap,
            wire_label=wl,
        )
        builder.add_terminal(
            "X9",
            relative_to=spdt.pin(f"{p}1"),
            position="below",
            label_pos="left",
            spacing=gap,
            wire_label=wl,
        )

    builder.build(count=1)
    return builder.result


# ---------------------------------------------------------------------------
# Project assembly
# ---------------------------------------------------------------------------


def main():
    project = Project(
        title="Example Cabinet",
        drawing_number="EX-006",
        author="Schematika",
        project="Examples",
        revision="01",
    )

    # Terminal definitions — appear in the terminal report
    project.terminals(
        Terminal("X1", "Main Power 400V"),
        Terminal("X2", "Motor Cable"),
        Terminal("X3", "Control Power 24V"),
        Terminal("X4", "Control Ground"),
        Terminal("X5", "Switched 230V"),
        Terminal("X6", "Feedback Output"),
        Terminal("X7", "Emergency Supply"),
        Terminal("X8", "Main Supply"),
        Terminal("X9", "Switched Output"),
    )

    # Register circuit builder functions
    project.add_circuit("motor", dol_starter)
    project.add_circuit("relay", relay_control)
    project.add_circuit("changeover", changeover_switch)

    # Define pages
    project.page("Motor Starter", "motor")
    project.page("Relay Control", "relay")
    project.page("Power Changeover", "changeover")
    project.terminal_report()

    # Compile to PDF
    pdf_path = str(OUTPUT_DIR / "06_full_cabinet.pdf")
    project.build(pdf_path, temp_dir=str(OUTPUT_DIR / "temp"))
    print(f"Compiled PDF: {pdf_path}")


if __name__ == "__main__":
    main()
