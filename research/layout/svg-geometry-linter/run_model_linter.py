"""Run the geometry linter against real Schematika output, two ways.

For each example circuit below, this script:

1. Builds the circuit through the real `schematika` API (same calls as the
   `examples/0X_*.py` scripts) and lints `result.circuit.elements` directly
   -- the pre-render geometry model.
2. Renders that same circuit to SVG via `render_system` and lints the SVG
   text with a regex-based extractor -- the post-render path.
3. Prints both `LintReport`s so the two approaches can be compared.

Run with: `uv run research/layout/svg-geometry-linter/run_model_linter.py`
(run from the repo root of this worktree -- needs the `schematika` package
installed, i.e. `uv sync` first).
"""

from pathlib import Path

from linter import LintReport, lint_elements, lint_svg_text

from schematika import (
    GRID_SIZE,
    SPACING_STANDARD,
    CircuitBuilder,
    WireLabels,
    breaker,
    contactor,
    create_initial_state,
    motor,
    render_system,
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

OUT_DIR = Path(__file__).parent / "examples"
FINDINGS_DIR = Path(__file__).parent / "findings"
OUT_DIR.mkdir(exist_ok=True)
FINDINGS_DIR.mkdir(exist_ok=True)


def build_dol_starter():
    """3-phase DOL motor starter -- identical to `examples/02_dol_starter.py`."""
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    builder.add_terminal("X1", config=TerminalConfig(poles=3))
    builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F", poles=3))
    builder.add_symbol(contactor, config=SymbolConfig(tag_prefix="Q", poles=3))
    builder.add_symbol(thermal_overload, config=SymbolConfig(tag_prefix="FT", poles=3))
    builder.add_symbol(motor, config=SymbolConfig(tag_prefix="M", poles=3))
    builder.add_terminal("X2", config=TerminalConfig(poles=3, pins=("U1", "V1", "W1")))

    wire_labels = [
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,
        WireLabels.BR_2_5,
        WireLabels.BK_2_5,
        WireLabels.GY_2_5,
    ]
    result = builder.build(options=BuildOptions(count=1, wire_labels=wire_labels))
    return result.circuit


def build_spdt_positioning():
    """2-pole SPDT with relative "above"/"below" placement -- identical to
    `examples/04_spdt_positioning.py`, the track most likely to produce
    near-misaligned pins since terminals are offset from ports by a
    computed spacing rather than placed on an absolute grid."""
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
            placement=PlacementOptions(
                relative_to=spdt.pin(f"{p}2"), position="above", spacing=spdt_gap
            ),
            display=TerminalDisplayOptions(label_pos="left"),
            connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X2",
            placement=PlacementOptions(
                relative_to=spdt.pin(f"{p}4"), position="above", spacing=spdt_gap
            ),
            display=TerminalDisplayOptions(label_pos="right"),
            connection=ConnectionOptions(wire_label=wl),
        )
        builder.add_terminal(
            "X3",
            placement=PlacementOptions(
                relative_to=spdt.pin(f"{p}1"), position="below", spacing=spdt_gap
            ),
            display=TerminalDisplayOptions(label_pos="left"),
            connection=ConnectionOptions(wire_label=wl),
        )

    result = builder.build(options=BuildOptions(count=1))
    return result.circuit


def format_report(name: str, report: LintReport) -> str:
    lines = [f"=== {name} ===", f"total findings: {len(report.findings)}  cost: {report.cost:.2f}"]
    for kind, count in sorted(report.by_kind().items()):
        lines.append(f"  {kind}: {count}")
    for f in report.findings:
        lines.append(f"    [{f.severity}] {f.kind} @ {f.location}: {f.message}")
    return "\n".join(lines)


def run_case(name: str, circuit) -> str:
    svg_path = OUT_DIR / f"{name}.svg"
    render_system(circuit, str(svg_path), width="auto", height="auto")

    model_report = lint_elements(circuit.elements)
    svg_report = lint_svg_text(svg_path.read_text(encoding="utf-8"))

    out = [
        format_report(f"{name} -- pre-render model (Circuit.elements)", model_report),
        format_report(f"{name} -- post-render SVG text (regex)", svg_report),
        (
            f"model vs svg-text finding count: "
            f"{len(model_report.findings)} vs {len(svg_report.findings)}"
        ),
    ]
    return "\n\n".join(out)


def main() -> None:
    cases = {
        "dol_starter": build_dol_starter(),
        "spdt_positioning": build_spdt_positioning(),
    }
    reports = []
    for name, circuit in cases.items():
        report_text = run_case(name, circuit)
        print(report_text)
        print()
        reports.append(report_text)

    (FINDINGS_DIR / "findings.txt").write_text("\n\n".join(reports), encoding="utf-8")
    print(f"Wrote {FINDINGS_DIR / 'findings.txt'}")


if __name__ == "__main__":
    main()
