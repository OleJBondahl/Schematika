"""Lint every real circuit this repo can produce, not just 2 hand-picked ones.

Round 1 validated `lint_elements` against exactly two hand-curated example
circuits (DOL starter, SPDT positioning). Round 2's task 1 is to broaden
that: every `electrical` example under `examples/` that produces a
`BuildResult`, the PCB bridge example, and a P&ID circuit built directly
through `PIDBuilder` (no `examples/` script uses `pid` yet, so this script
builds one).

`cable`/`harness` (`examples/08_showcase_harness.py`) and `overview`
(`examples/10_showcase_overview.py`) are deliberately excluded: neither
produces a `core.primitives.Element` tree (`cable` renders via a WireViz-
style drawing DSL; `overview` is Cytoscape/JS-based), so `lint_elements`
does not apply to them at all -- see the findings doc's "scope" section.

Run with: `uv run research/layout/deepdive-svg-geometry-linter/run_real_circuits.py`
(run from the repo root -- needs `uv sync --all-extras` first for the pcb extras).
"""

from pathlib import Path

from linter import LintReport, lint_elements, lint_pid_diagram

from schematika import (
    CIRCUIT_SPACING,
    CIRCUIT_SPACING_NARROW,
    GRID_SIZE,
    SPACING_STANDARD,
    BuildResult,
    CircuitBuilder,
    WireLabels,
    block,
    breaker,
    coil,
    contactor,
    create_initial_state,
    motor,
    no_contact,
    render_system,
    thermal_overload,
)
from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    EquipmentConfig,
    EquipmentPlacement,
    PlacementOptions,
    SpdtConfig,
    SymbolConfig,
    TerminalConfig,
    TerminalDisplayOptions,
)
from schematika.pcb import build as pcb_build
from schematika.pcb.model import ConnectorMap, PowerNetMap, SymbolMap, SymbolMapping, SymbolSlice
from schematika.pcb.symbols.power import gnd as gnd_symbol
from schematika.pcb.symbols.power import power_24v
from schematika.pid.builder import PIDBuilder
from schematika.pid.symbols import centrifugal_pump, gate_valve, heat_exchanger, tank
from schematika.project import Project

FINDINGS_DIR = Path(__file__).parent / "findings"
FINDINGS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# electrical: examples 01-05, standalone (5 circuits)
# ---------------------------------------------------------------------------


def circuit_01_single_relay():
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)
    builder.add_terminal("X1", config=TerminalConfig(poles=1))
    builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K", poles=1))
    builder.add_terminal("X2", config=TerminalConfig(poles=1))
    result = builder.build(options=BuildOptions(count=1))
    return result.circuit


def circuit_02_dol_starter():
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)
    builder.add_terminal("X1", config=TerminalConfig(poles=3))
    builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F", poles=3))
    builder.add_symbol(contactor, config=SymbolConfig(tag_prefix="Q", poles=3))
    builder.add_symbol(thermal_overload, config=SymbolConfig(tag_prefix="FT", poles=3))
    builder.add_symbol(motor, config=SymbolConfig(tag_prefix="M", poles=3))
    builder.add_terminal("X2", config=TerminalConfig(poles=3, pins=("U1", "V1", "W1")))
    wire_labels = [WireLabels.BR_2_5, WireLabels.BK_2_5, WireLabels.GY_2_5] * 4
    result = builder.build(options=BuildOptions(count=1, wire_labels=wire_labels))
    return result.circuit


def circuit_03_coil_contact_pair():
    state = create_initial_state()
    sub_spacing = 5 * GRID_SIZE
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING_NARROW)
    coil_builder.add_terminal("X1", config=TerminalConfig(poles=1))
    coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    coil_builder.add_terminal("X2", config=TerminalConfig(poles=1))
    coil_builder.build(
        options=BuildOptions(count=2, wire_labels=[WireLabels.WH_0_5, WireLabels.BK_0_5] * 2)
    )
    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=sub_spacing, y=0, spacing=CIRCUIT_SPACING_NARROW)
    contact_builder.add_terminal("X3", config=TerminalConfig(poles=1))
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
    contact_builder.add_terminal("X4", config=TerminalConfig(poles=1))
    contact_builder.build(
        options=BuildOptions(
            count=2,
            reuse_tags={"K": coil_builder.result},
            wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5] * 2,
        )
    )
    return CircuitBuilder.merge(coil_builder, contact_builder).result.circuit


def circuit_04_spdt_positioning():
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)
    spdt_gap = SPACING_STANDARD - GRID_SIZE
    phase_colors = [WireLabels.BR_1_5, WireLabels.BK_1_5]
    spdt = builder.add_spdt("K", config=SpdtConfig(poles=2))
    for i in range(2):
        p = i + 1
        wl = phase_colors[i]
        builder.add_terminal(
            "X1",
            placement=PlacementOptions(relative_to=spdt.pin(f"{p}2"), position="above", spacing=spdt_gap),
            display=TerminalDisplayOptions(label_pos="left"),
            connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X2",
            placement=PlacementOptions(relative_to=spdt.pin(f"{p}4"), position="above", spacing=spdt_gap),
            display=TerminalDisplayOptions(label_pos="right"),
            connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X3",
            placement=PlacementOptions(relative_to=spdt.pin(f"{p}1"), position="below", spacing=spdt_gap),
            display=TerminalDisplayOptions(label_pos="left"),
            connection=ConnectionOptions(wire_label=wl),
        )
    result = builder.build(options=BuildOptions(count=1))
    return result.circuit


def circuit_05_multi_builder():
    state = create_initial_state()
    sub_spacing = SPACING_STANDARD
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=2 * CIRCUIT_SPACING)
    coil_ref = coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    coil_builder.add_terminal(
        "X1", config=TerminalConfig(poles=1),
        placement=PlacementOptions(relative_to=coil_ref.pin("A1"), position="above"),
    )
    coil_builder.add_terminal(
        "X1", config=TerminalConfig(poles=1),
        placement=PlacementOptions(relative_to=coil_ref.pin("A2"), position="below"),
    )
    coil_builder.build(options=BuildOptions(count=1, wire_labels=[WireLabels.BR_1_5, WireLabels.BL_1_5]))

    block_builder = CircuitBuilder(coil_builder.state)
    block_builder.set_layout(x=sub_spacing, y=0, spacing=2 * CIRCUIT_SPACING)
    block_ref = block_builder.add_symbol(
        block,
        config=SymbolConfig(
            tag_prefix="K", pins=("y1", "y2", "t1", "t2"),
            factory_kwargs={"top_pins": ("y1", "y2"), "bottom_pins": ("t1", "t2")},
        ),
        connection=ConnectionOptions(connect_from_previous=False),
    )
    block_builder.add_reference(
        "PLC:DO1", placement=PlacementOptions(relative_to=block_ref.pin("y1"), position="above"),
        direction="up", label_pos="left",
    )
    block_builder.add_reference(
        "PLC:DO2", placement=PlacementOptions(relative_to=block_ref.pin("y2"), position="above"),
        direction="up", label_pos="right",
    )
    tm_bot = block_builder.add_terminal(
        "X2", config=TerminalConfig(poles=2),
        connection=ConnectionOptions(connect_to_next=False, connect_from_previous=False),
    )
    block_builder.connect(block_ref.pin("t1"), tm_bot.pole(0), side_a="bottom", side_b="top")
    block_builder.connect(block_ref.pin("t2"), tm_bot.pole(1), side_a="bottom", side_b="top")
    block_builder.build(
        options=BuildOptions(
            count=1, reuse_tags={"K": coil_builder.result},
            wire_labels=[WireLabels.WH_0_5] * 4,
        )
    )

    contact_builder = CircuitBuilder(block_builder.state)
    contact_builder.set_layout(x=2 * sub_spacing, y=0, spacing=2 * CIRCUIT_SPACING)
    contact_builder.add_terminal("X3", config=TerminalConfig(poles=1))
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
    contact_builder.add_terminal("X4", config=TerminalConfig(poles=1))
    contact_builder.build(
        options=BuildOptions(
            count=1, reuse_tags={"K": coil_builder.result},
            wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5],
        )
    )
    merged = CircuitBuilder.merge(coil_builder, block_builder, contact_builder)
    return merged.result.circuit


# ---------------------------------------------------------------------------
# electrical: examples 06 + 07, via Project (3 + 4 page circuits)
# ---------------------------------------------------------------------------


def _dol_starter_page(x1: str, x2: str):
    def _build(state) -> BuildResult:
        builder = CircuitBuilder(state)
        builder.set_layout(x=0, y=0)
        builder.add_terminal(x1, config=TerminalConfig(poles=3))
        builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F", poles=3))
        builder.add_symbol(contactor, config=SymbolConfig(tag_prefix="Q", poles=3))
        builder.add_symbol(thermal_overload, config=SymbolConfig(tag_prefix="FT", poles=3))
        builder.add_symbol(motor, config=SymbolConfig(tag_prefix="M", poles=3))
        builder.add_terminal(x2, config=TerminalConfig(poles=3, pins=("U1", "V1", "W1")))
        wire_labels = [WireLabels.BR_2_5, WireLabels.BK_2_5, WireLabels.GY_2_5] * 4
        builder.build(options=BuildOptions(count=1, wire_labels=wire_labels))
        return builder.result

    return _build


def _relay_control_page(state) -> BuildResult:
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING)
    coil_builder.add_terminal("X3", config=TerminalConfig(poles=1))
    coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    coil_builder.add_terminal("X4", config=TerminalConfig(poles=1))
    coil_builder.build(options=BuildOptions(count=1, wire_labels=[WireLabels.WH_0_5, WireLabels.BK_0_5]))

    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=5 * GRID_SIZE, y=0, spacing=CIRCUIT_SPACING)
    contact_builder.add_terminal("X5", config=TerminalConfig(poles=1))
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
    contact_builder.add_terminal("X6", config=TerminalConfig(poles=1))
    contact_builder.build(
        options=BuildOptions(
            count=1, reuse_tags={"K": coil_builder.result},
            wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5],
        )
    )
    return CircuitBuilder.merge(coil_builder, contact_builder).result


def _changeover_page(state) -> BuildResult:
    builder = CircuitBuilder(state)
    builder.set_layout(x=SPACING_STANDARD, y=SPACING_STANDARD)
    gap = SPACING_STANDARD - GRID_SIZE
    phase_colors = [WireLabels.BR_1_5, WireLabels.BK_1_5]
    spdt = builder.add_spdt("K", config=SpdtConfig(poles=2))
    for i in range(2):
        p = i + 1
        wl = phase_colors[i]
        builder.add_terminal(
            "X7", placement=PlacementOptions(relative_to=spdt.pin(f"{p}2"), position="above", spacing=gap),
            display=TerminalDisplayOptions(label_pos="left"), connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X8", placement=PlacementOptions(relative_to=spdt.pin(f"{p}4"), position="above", spacing=gap),
            display=TerminalDisplayOptions(label_pos="right"), connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X9", placement=PlacementOptions(relative_to=spdt.pin(f"{p}1"), position="below", spacing=gap),
            display=TerminalDisplayOptions(label_pos="left"), connection=ConnectionOptions(wire_label=wl),
        )
    builder.build(options=BuildOptions(count=1))
    return builder.result


def _start_stop_page(state) -> BuildResult:
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=CIRCUIT_SPACING)
    coil_builder.add_terminal("X12", config=TerminalConfig(poles=1))
    coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    coil_builder.add_terminal("X13", config=TerminalConfig(poles=1))
    coil_builder.build(options=BuildOptions(count=1, wire_labels=[WireLabels.WH_0_5, WireLabels.BK_0_5]))

    contact_builder = CircuitBuilder(coil_builder.state)
    contact_builder.set_layout(x=5 * GRID_SIZE, y=0, spacing=CIRCUIT_SPACING)
    contact_builder.add_terminal("X14", config=TerminalConfig(poles=1))
    contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
    contact_builder.add_terminal("X15", config=TerminalConfig(poles=1))
    contact_builder.build(
        options=BuildOptions(
            count=1, reuse_tags={"K": coil_builder.result},
            wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5],
        )
    )
    return CircuitBuilder.merge(coil_builder, contact_builder).result


def project_06_full_cabinet():
    project = Project(title="Example Cabinet", drawing_number="EX-006", author="Schematika", project="Examples", revision="01")
    project.add_circuit("motor", _dol_starter_page("X1", "X2"))
    project.add_circuit("relay", _relay_control_page)
    project.add_circuit("changeover", _changeover_page)
    project.page("Motor Starter", "motor")
    project.page("Relay Control", "relay")
    project.page("Power Changeover", "changeover")
    project._build_all_circuits()
    return {key: r.circuit for key, r in project._results.items()}


def project_07_showcase_cabinet():
    project = Project(title="Showcase Cabinet", drawing_number="EX-007", author="Schematika", project="Examples", revision="01")
    project.add_circuit("motor1", _dol_starter_page("X1", "X2"))
    project.add_circuit("motor2", _dol_starter_page("X10", "X11"))
    project.add_circuit("start_stop", _start_stop_page)
    project.add_circuit("changeover", _changeover_page)
    project.page("Motor 1", "motor1")
    project.page("Motor 2", "motor2")
    project.page("Start/Stop Station", "start_stop")
    project.page("Power Changeover", "changeover")
    project._build_all_circuits()
    return {key: r.circuit for key, r in project._results.items()}


# ---------------------------------------------------------------------------
# pcb: example 09's interface board (1 page circuit)
# ---------------------------------------------------------------------------


def pcb_09_interface_board():
    import skidl
    from skidl import Circuit as SkidlCircuit
    from skidl import Net, Part, Pin

    circuit = SkidlCircuit()
    conn_template = Part(
        name="conn_4p", ref_prefix="J", pins=[Pin(num=str(i), name="") for i in range(1, 5)],
        dest=skidl.TEMPLATE, tool=skidl.SKIDL,
    )
    fuse_template = Part(
        name="fuse", ref_prefix="F", pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE, tool=skidl.SKIDL,
    )
    relay_template = Part(
        name="relay_spst", ref_prefix="K", pins=[Pin(num="A1", name=""), Pin(num="A2", name="")],
        dest=skidl.TEMPLATE, tool=skidl.SKIDL,
    )
    j1 = conn_template(ref="J1", circuit=circuit)
    j2 = conn_template(ref="J2", circuit=circuit)
    f1 = fuse_template(ref="F1", circuit=circuit)
    k1 = relay_template(ref="K1", circuit=circuit)
    vcc = Net("+24V", circuit=circuit)
    gnd = Net("GND", circuit=circuit)
    sig_in = Net("SIG_IN", circuit=circuit)
    sig_out = Net("SIG_OUT", circuit=circuit)
    vcc += j1["1"], f1["1"]
    sig_in += j1["2"], k1["A1"]
    gnd += j1["3"], k1["A2"], j1["4"]
    sig_out += f1["2"], j2["1"]

    from schematika.electrical.symbols import coil as coil_symbol
    from schematika.electrical.symbols import fuse as fuse_symbol

    def _fuse_sym(label: str = "", **_kwargs):
        return fuse_symbol(label=label)

    def _relay_sym(label: str = "", **_kwargs):
        return coil_symbol(label=label, pins=("A1", "A2"))

    mapping = SymbolMapping(
        symbols=(
            SymbolMap(template=fuse_template, slices=(SymbolSlice(symbol=_fuse_sym, pin_map={"1": "1", "2": "2"}),)),
            SymbolMap(template=relay_template, slices=(SymbolSlice(symbol=_relay_sym, pin_map={"A1": "A1", "A2": "A2"}),)),
        ),
        connectors=(ConnectorMap(template=conn_template),),
        power_nets=(
            PowerNetMap(canonical_name="GND", symbol=gnd_symbol),
            PowerNetMap(canonical_name="+24V", symbol=power_24v),
        ),
    )
    result = pcb_build(circuit, mapping, page_size=(250.0, 200.0))

    project = Project(title="Interface Board", drawing_number="EX-009", author="Schematika", project="Examples", revision="01")
    project.add_pcb(result)
    project._build_all_circuits()
    return {key: r.circuit for key, r in project._results.items()}


# ---------------------------------------------------------------------------
# pid: no examples/ script uses PIDBuilder yet -- build one directly.
# Tank -> pump -> heat exchanger -> gate valve, with a temperature and a
# pressure instrument, deliberately including one off-axis pipe (forces a
# Manhattan bend) to exercise the orthogonal/jog checks, not just a straight
# run.
# ---------------------------------------------------------------------------


def pid_process_train():
    builder = PIDBuilder()
    builder.add_equipment("tank", config=EquipmentConfig(factory=tank, tag_prefix="T"), placement=EquipmentPlacement(x=0, y=0))
    builder.add_equipment(
        "pump", config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(relative_to="tank", from_port="outlet", to_port="inlet"),
    )
    builder.add_equipment(
        "hx", config=EquipmentConfig(factory=heat_exchanger, tag_prefix="E"),
        # Deliberately off-axis relative to the pump's outlet so the pipe
        # between them needs a Manhattan bend, not a straight run.
        placement=EquipmentPlacement(x=200, y=80),
    )
    builder.add_equipment(
        "valve", config=EquipmentConfig(factory=gate_valve, tag_prefix="V"),
        placement=EquipmentPlacement(relative_to="hx", from_port="tube_out", to_port="in"),
    )
    builder.add_instrument("tt101", "TT", on_equipment="hx", on_port="tube_out", offset=(0, -35))
    builder.add_instrument("pt101", "PT", on_equipment="pump", on_port="outlet", offset=(0, 35))
    builder.pipe("tank", "pump", line_spec="2-CW-101")
    builder.pipe("pump", "hx", to_port="tube_in", line_spec="2-CW-102")
    builder.pipe("hx", "valve", from_port="tube_out", to_port="in", line_spec="2-CW-103")
    builder.signal_line("tt101", "hx", from_port="signal_out", to_port="tube_out")
    result = builder.build()
    return result.diagram


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def format_report(name: str, report: LintReport) -> str:
    lines = [f"=== {name} ===", f"total findings: {len(report.findings)}  cost: {report.cost:.2f}"]
    for kind, count in sorted(report.by_kind().items()):
        lines.append(f"  {kind}: {count}")
    for f in report.findings:
        lines.append(f"    [{f.severity}] {f.kind} @ {f.location}: {f.message}")
    return "\n".join(lines)


def main() -> None:
    cases: dict[str, list] = {}

    cases["01_single_relay"] = circuit_01_single_relay().elements
    cases["02_dol_starter"] = circuit_02_dol_starter().elements
    cases["03_coil_contact_pair"] = circuit_03_coil_contact_pair().elements
    cases["04_spdt_positioning"] = circuit_04_spdt_positioning().elements
    cases["05_multi_builder"] = circuit_05_multi_builder().elements

    for key, circuit in project_06_full_cabinet().items():
        cases[f"06_full_cabinet[{key}]"] = circuit.elements
    for key, circuit in project_07_showcase_cabinet().items():
        cases[f"07_showcase_cabinet[{key}]"] = circuit.elements
    for key, circuit in pcb_09_interface_board().items():
        cases[f"09_showcase_pcb[{key}]"] = circuit.elements

    reports = []
    total_findings = 0
    for name, elements in cases.items():
        report = lint_elements(elements)
        total_findings += len(report.findings)
        text = format_report(name, report)
        print(text)
        print()
        reports.append(text)

    # pid needs `lint_pid_diagram`, not raw `lint_elements` -- see the
    # findings doc + `linter.py::lint_pid_diagram`'s docstring for why
    # `PIDBuilder.build()` flattening equipment symbols into `diagram.elements`
    # makes the naive call produce false positives that the electrical/pcb
    # cases above don't have.
    pid_diagram = pid_process_train()
    naive_pid = lint_elements(pid_diagram.elements)
    fixed_pid = lint_pid_diagram(pid_diagram)
    total_findings += len(fixed_pid.findings)
    pid_text = (
        format_report("pid_process_train -- naive lint_elements(diagram.elements)", naive_pid)
        + "\n\n"
        + format_report("pid_process_train -- lint_pid_diagram(diagram) [use this one]", fixed_pid)
    )
    print(pid_text)
    print()
    reports.append(pid_text)

    summary = (
        f"TOTAL (electrical x12 + pcb x1 + pid x1, using the correct entry "
        f"point per domain): {len(cases) + 1} circuits, {total_findings} findings"
    )
    print(summary)
    reports.append(summary)

    (FINDINGS_DIR / "real_circuits.txt").write_text("\n\n".join(reports), encoding="utf-8")
    print(f"\nWrote {FINDINGS_DIR / 'real_circuits.txt'}")


if __name__ == "__main__":
    main()
