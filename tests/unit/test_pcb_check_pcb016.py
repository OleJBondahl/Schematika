"""Tests for PCB016 - zero-overlap check."""

from __future__ import annotations

from schematika.core.geometry import Point, Style, Vector
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Port, Symbol
from schematika.electrical.system.system import Circuit
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb016_overlap import check
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    Page,
    PCBBuildResult,
    PinColumns,
    SymbolMapping,
    Terminator,
)

_WIRE_STYLE = Style(stroke="black", fill="none", stroke_width=0.25)
_TEXT_STYLE = Style(stroke="none", fill="black")


def _mapping() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())


def _nc_block(ref: str, n_pins: int) -> ConnectorBlock:
    pcs = tuple(
        PinColumns(
            pin_id=str(i + 1),
            columns=(Column(slices=(), terminator=Terminator.NC),),
        )
        for i in range(n_pins)
    )
    return ConnectorBlock(connector_ref=ref, functional_label=None, pin_columns=pcs)


def _result_with_pages(
    blocks: list[ConnectorBlock],
    pages: list[Page],
) -> PCBBuildResult:
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=tuple(blocks),
        floating_parts=(),
        pages=tuple(pages),
        mapping=_mapping(),
        layout=LayoutSpec(),
        page_size=(250.0, 297.0),
    )


def _check_circuit_on_result(circuit: Circuit) -> tuple:
    """Inject a pre-built Circuit into the check via monkey-patching."""
    import schematika.pcb.checks.pcb016_overlap as mod
    from schematika.pcb.model import Page as PageModel

    original = mod._build_page_circuit

    def fake_build(_result: PCBBuildResult, _page: PageModel) -> Circuit:
        return circuit

    mod._build_page_circuit = fake_build  # ty: ignore[invalid-assignment]
    try:
        result = PCBBuildResult(
            state=create_initial_state(),
            connector_blocks=(),
            floating_parts=(),
            pages=(Page(title="P1", placements=()),),
            mapping=_mapping(),
            layout=LayoutSpec(),
        )
        return check(result)
    finally:
        mod._build_page_circuit = original


# ---------------------------------------------------------------------------
# Full render pipeline tests
# ---------------------------------------------------------------------------


def test_pcb016_passes_on_clean_two_block_layout() -> None:
    """Two non-overlapping connector blocks on one page - no findings."""
    layout = LayoutSpec()
    j1 = _nc_block("J1", 2)
    j2 = _nc_block("J2", 2)
    block_width = layout.side_padding_mm * 2 + 2 * layout.pin_spacing_mm  # 30mm
    gap = layout.inter_block_gap_mm  # 20mm

    pages = [
        Page(
            title="Page 1",
            placements=(
                ("J1", 0.0, 30.0),
                ("J2", block_width + gap, 30.0),
            ),
        )
    ]
    result = _result_with_pages([j1, j2], pages)
    issues = check(result)
    assert issues == (), f"Expected no issues, got: {issues}"


def test_pcb016_flags_two_symbols_overlapping() -> None:
    """Two connector blocks placed at the same origin - symbol overlap - ERROR."""
    j1 = _nc_block("J1", 2)
    j2 = _nc_block("J2", 2)

    pages = [
        Page(
            title="Page 1",
            placements=(
                ("J1", 0.0, 30.0),
                ("J2", 0.0, 30.0),
            ),
        )
    ]
    result = _result_with_pages([j1, j2], pages)
    issues = check(result)
    assert any(f.code == "PCB016" for f in issues), f"Expected PCB016, got: {issues}"
    assert all(f.severity.value == "error" for f in issues)


def test_pcb016_passes_on_empty_pages() -> None:
    result = _result_with_pages([], [])
    assert check(result) == ()


# ---------------------------------------------------------------------------
# Direct Circuit construction tests
# ---------------------------------------------------------------------------


def test_pcb016_flags_two_wires_crossing() -> None:
    """Two perpendicular wires that cross - wire-wire ERROR."""
    circuit = Circuit()
    circuit.elements.append(Line(Point(0, 5), Point(10, 5), _WIRE_STYLE))
    circuit.elements.append(Line(Point(5, 0), Point(5, 10), _WIRE_STYLE))

    issues = _check_circuit_on_result(circuit)
    assert any(f.code == "PCB016" for f in issues), f"No PCB016 found: {issues}"


def test_pcb016_exempts_wires_sharing_single_endpoint() -> None:
    """Two wires sharing exactly one endpoint - exempt, no issue."""
    circuit = Circuit()
    circuit.elements.append(Line(Point(0, 0), Point(5, 0), _WIRE_STYLE))
    circuit.elements.append(Line(Point(5, 0), Point(10, 0), _WIRE_STYLE))

    issues = _check_circuit_on_result(circuit)
    wire_issues = [f for f in issues if f.code == "PCB016"]
    assert not wire_issues, f"Expected no wire issues, got: {wire_issues}"


def test_pcb016_flags_text_on_wire() -> None:
    """A Text whose bbox overlaps a wire - text-wire ERROR."""
    circuit = Circuit()
    circuit.elements.append(Line(Point(0, 5), Point(20, 5), _WIRE_STYLE))
    circuit.elements.append(
        Text(
            content="NET",
            position=Point(10, 5),
            anchor="middle",
            font_size=3.0,
            style=_TEXT_STYLE,
        )
    )

    issues = _check_circuit_on_result(circuit)
    assert any(f.code == "PCB016" for f in issues), f"No PCB016 found: {issues}"


def test_pcb016_exempts_intra_symbol_pin_labels() -> None:
    """Pin labels inside a placed symbol body are NOT top-level Text elements.

    They live inside the Symbol's own .elements list and must not be flagged.
    PCB016 only inspects top-level circuit.elements.
    """
    from schematika.core.parts import box
    from schematika.core.primitives import Text as PrimText

    circuit = Circuit()
    internal_texts = [
        PrimText(content="1", position=Point(5, 8), font_size=3.5, style=_TEXT_STYLE),
        PrimText(content="2", position=Point(15, 8), font_size=3.5, style=_TEXT_STYLE),
    ]
    sym = Symbol(
        elements=[box(Point(10, 5), 20, 10), *internal_texts],
        ports={
            "1": Port("1", Point(5, 10), Vector(0, 1)),
            "2": Port("2", Point(15, 10), Vector(0, 1)),
        },
        label="J1",
    )
    circuit.symbols.append(sym)
    circuit.elements.append(sym)

    issues = _check_circuit_on_result(circuit)
    assert not issues, f"Internal texts should not be flagged, got: {issues}"


def test_pcb016_flags_text_symbol_overlap() -> None:
    """A free-floating Text whose bbox overlaps a symbol - text-symbol ERROR."""
    from schematika.core.parts import box

    circuit = Circuit()
    sym = Symbol(
        elements=[box(Point(5, 5), 10, 10)],
        ports={"out": Port("1", Point(5, 10), Vector(0, 1))},
        label="SYM",
    )
    circuit.symbols.append(sym)
    circuit.elements.append(sym)
    circuit.elements.append(
        Text(
            content="LABEL",
            position=Point(5, 5),
            anchor="middle",
            font_size=3.0,
            style=_TEXT_STYLE,
        )
    )

    issues = _check_circuit_on_result(circuit)
    assert any(f.code == "PCB016" for f in issues), f"No PCB016 found: {issues}"


def test_pcb016_no_false_positives_adjacent_symbols() -> None:
    """Symbols placed edge-to-edge (touching, not overlapping) - no issue."""
    from schematika.core.parts import box

    circuit = Circuit()
    sym_a = Symbol(
        elements=[box(Point(5, 5), 10, 10)],
        ports={"out": Port("1", Point(5, 10), Vector(0, 1))},
        label="A",
    )
    sym_b = Symbol(
        elements=[box(Point(15, 5), 10, 10)],
        ports={"out": Port("1", Point(15, 10), Vector(0, 1))},
        label="B",
    )
    for sym in (sym_a, sym_b):
        circuit.symbols.append(sym)
        circuit.elements.append(sym)

    issues = _check_circuit_on_result(circuit)
    sym_issues = [f for f in issues if "overlaps symbol" in f.message]
    assert not sym_issues, f"Adjacent symbols wrongly flagged: {sym_issues}"
