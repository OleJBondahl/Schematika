"""
Example 07: Showcase Cabinet — a small original "MCC panel" demo

Extends example 06's cabinet with a second motor starter and a
self-latching start/stop station, purely for the project's GitHub
showcase (see showcase/electrical.html). Not derived from any real
customer panel.

Pages:
    1. Motor 1 (DOL starter)
    2. Motor 2 (DOL starter)
    3. Start/Stop Station (self-latching coil + seal-in contact)
    4. Power Changeover (SPDT, from example 04)

Concepts taught:
    - Same as example 06 (Project, Terminal, add_circuit, page,
      terminal_report), plus a second independent DOL starter and a
      self-latching (seal-in) control circuit.
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
from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    PlacementOptions,
    SpdtConfig,
    SymbolConfig,
    TerminalConfig,
    TerminalDisplayOptions,
)
from schematika.project import Project

SHOWCASE_DIR = Path(__file__).parent.parent / "showcase" / "assets" / "electrical"
SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)


def dol_starter(x1: str, x2: str):
    """3-phase DOL motor starter: X1 -> F -> Q -> FT -> M -> X2.

    Tag numbers (F1/F2, Q1/Q2, ...) come from the shared autonumbering
    state Project threads through circuits in registration order — see
    `Project._build_all_circuits` (`self._state = result.state` after
    each circuit) — so two calls with the same tag_prefix correctly
    number sequentially without an explicit counter here.
    """

    def _build(state) -> BuildResult:
        builder = CircuitBuilder(state)
        builder.set_layout(x=0, y=0)
        builder.add_terminal(x1, config=TerminalConfig(poles=3))
        builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F", poles=3))
        builder.add_symbol(contactor, config=SymbolConfig(tag_prefix="Q", poles=3))
        builder.add_symbol(
            thermal_overload, config=SymbolConfig(tag_prefix="FT", poles=3)
        )
        builder.add_symbol(motor, config=SymbolConfig(tag_prefix="M", poles=3))
        builder.add_terminal(
            x2, config=TerminalConfig(poles=3, pins=("U1", "V1", "W1"))
        )
        wire_labels = [
            WireLabels.BR_2_5,
            WireLabels.BK_2_5,
            WireLabels.GY_2_5,
        ] * 4
        builder.build(options=BuildOptions(count=1, wire_labels=wire_labels))
        return builder.result

    return _build


def start_stop_station(state) -> BuildResult:
    """Self-latching start/stop: X12(start NO) -> K1(coil) -> X13; seal-in NO contact reuses K1.

    Left:  X12 -> K1(coil) -> X13
    Right: X14 -> K1(NO seal-in contact) -> X15  (reuses K1 tag)
    """
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING)
    coil_builder.add_terminal("X12", config=TerminalConfig(poles=1))
    coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    coil_builder.add_terminal("X13", config=TerminalConfig(poles=1))
    coil_builder.build(
        options=BuildOptions(
            count=1, wire_labels=[WireLabels.WH_0_5, WireLabels.BK_0_5]
        )
    )

    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=5 * GRID_SIZE, y=0, spacing=CIRCUIT_SPACING)
    contact_builder.add_terminal("X14", config=TerminalConfig(poles=1))
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
    contact_builder.add_terminal("X15", config=TerminalConfig(poles=1))
    contact_builder.build(
        options=BuildOptions(
            count=1,
            reuse_tags={"K": coil_builder.result},
            wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5],
        )
    )
    return CircuitBuilder.merge(coil_builder, contact_builder).result


def changeover_switch(state) -> BuildResult:
    """2-pole SPDT changeover — identical to example 06's, reused verbatim."""
    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)
    gap = SPACING_STANDARD - GRID_SIZE
    phase_colors = [WireLabels.BR_1_5, WireLabels.BK_1_5]
    spdt = builder.add_spdt("K", config=SpdtConfig(poles=2))
    for i in range(2):
        p = i + 1
        wl = phase_colors[i]
        builder.add_terminal(
            "X7",
            placement=PlacementOptions(
                relative_to=spdt.pin(f"{p}2"), position="above", spacing=gap
            ),
            display=TerminalDisplayOptions(label_pos="left"),
            connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X8",
            placement=PlacementOptions(
                relative_to=spdt.pin(f"{p}4"), position="above", spacing=gap
            ),
            display=TerminalDisplayOptions(label_pos="right"),
            connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X9",
            placement=PlacementOptions(
                relative_to=spdt.pin(f"{p}1"), position="below", spacing=gap
            ),
            display=TerminalDisplayOptions(label_pos="left"),
            connection=ConnectionOptions(wire_label=wl),
        )
    builder.build(options=BuildOptions(count=1))
    return builder.result


def main():
    project = Project(
        title="Showcase Cabinet",
        drawing_number="EX-007",
        author="Schematika",
        project="Examples",
        revision="01",
    )
    project.terminals(
        Terminal("X1", "Main Power 400V (Motor 1)"),
        Terminal("X2", "Motor 1 Cable"),
        Terminal("X10", "Main Power 400V (Motor 2)"),
        Terminal("X11", "Motor 2 Cable"),
        Terminal("X12", "Start Button"),
        Terminal("X13", "Control Ground"),
        Terminal("X14", "Seal-in Feed"),
        Terminal("X15", "Seal-in Return"),
        Terminal("X7", "Emergency Supply"),
        Terminal("X8", "Main Supply"),
        Terminal("X9", "Switched Output"),
    )
    project.add_circuit("motor1", dol_starter("X1", "X2"))
    project.add_circuit("motor2", dol_starter("X10", "X11"))
    project.add_circuit("start_stop", start_stop_station)
    project.add_circuit("changeover", changeover_switch)

    project.page("Motor 1", "motor1")
    project.page("Motor 2", "motor2")
    project.page("Start/Stop Station", "start_stop")
    project.page("Power Changeover", "changeover")
    project.terminal_report()

    project.build_svgs(str(SHOWCASE_DIR))
    print(f"Wrote SVGs to {SHOWCASE_DIR}")


if __name__ == "__main__":
    main()
