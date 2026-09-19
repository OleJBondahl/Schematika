"""Tests for `core.geometry_lint`: the five wire-geometry checks, the
Finding/LintReport data model, and the `lint_elements`/`lint_build_result`
entry points -- including integration checks against real circuits from all
three domains that can produce a `core.primitives.Element` tree."""

from __future__ import annotations

from types import SimpleNamespace

from schematika import (
    CircuitBuilder,
    breaker,
    contactor,
    create_initial_state,
    motor,
    thermal_overload,
)
from schematika.core.geometry import Point, Style
from schematika.core.geometry_lint import (
    Finding,
    LintReport,
    check_near_alignment,
    check_orthogonal_wires,
    check_redundant_jogs,
    check_text_wire_collisions,
    check_wire_symbol_collisions,
    collect_wire_geometry,
    lint_build_result,
    lint_elements,
)
from schematika.core.options import (
    BuildOptions,
    EquipmentConfig,
    EquipmentPlacement,
    SymbolConfig,
    TerminalConfig,
)
from schematika.core.primitives import Group, Line, Text
from schematika.core.symbol import Symbol
from schematika.electrical.validation import validate_electrical
from schematika.pcb.model import Column, ConnectorBlock, PinColumns, Terminator
from schematika.pcb.render import render_connector_block
from schematika.pid.builder import PIDBuilder
from schematika.pid.symbols import centrifugal_pump, tank

_STYLE = Style(stroke="black", fill="none")


def _line(x1: float, y1: float, x2: float, y2: float) -> Line:
    return Line(Point(x1, y1), Point(x2, y2), _STYLE)


def _text(content: str, x: float, y: float, rotation: float = 0.0) -> Text:
    return Text(content=content, position=Point(x, y), style=_STYLE, rotation=rotation)


# ---------------------------------------------------------------------------
# Check 1: orthogonality
# ---------------------------------------------------------------------------


def test_orthogonal_wire_passes() -> None:
    assert check_orthogonal_wires([_line(0, 0, 0, 10)]) == []
    assert check_orthogonal_wires([_line(0, 0, 10, 0)]) == []


def test_crooked_wire_flagged() -> None:
    findings = check_orthogonal_wires([_line(0, 0, 10, 1)])
    assert len(findings) == 1
    assert findings[0].kind == "non_orthogonal_wire"
    assert findings[0].severity == "error"
    assert findings[0].weight > 0


# ---------------------------------------------------------------------------
# Check 2: text/wire collision
# ---------------------------------------------------------------------------


def test_text_on_wire_flagged() -> None:
    wire = _line(0, 0, 0, 20)
    label = _text("X1", x=0.0, y=10.0)
    findings = check_text_wire_collisions([wire], [label])
    assert findings != []
    assert findings[0].kind == "text_wire_collision"


def test_text_clear_of_wire_not_flagged() -> None:
    wire = _line(0, 0, 0, 20)
    label = _text("X1", x=50.0, y=10.0)
    assert check_text_wire_collisions([wire], [label]) == []


# ---------------------------------------------------------------------------
# Check 3: wire/symbol collision
# ---------------------------------------------------------------------------


def test_wire_through_symbol_footprint_flagged() -> None:
    """Regression: `route_wires` once produced a wire that ran straight
    through an unrelated symbol's box -- invisible to every other check
    because it was orthogonal and didn't cross any text."""
    wire = _line(0.0, 5.0, 20.0, 5.0)
    obstacle = (5.0, 0.0, 15.0, 10.0)
    findings = check_wire_symbol_collisions([wire], [obstacle])
    assert len(findings) == 1
    assert findings[0].kind == "wire_symbol_collision"


def test_wire_terminating_at_symbol_edge_not_flagged() -> None:
    """A wire ending exactly at a port on a symbol's boundary is a normal
    connection, not a collision -- it touches the bbox edge, never the
    interior."""
    wire = _line(0.0, 5.0, 5.0, 5.0)
    obstacle = (5.0, 0.0, 15.0, 10.0)
    assert check_wire_symbol_collisions([wire], [obstacle]) == []


# ---------------------------------------------------------------------------
# Check 4: near-alignment
# ---------------------------------------------------------------------------


def test_near_alignment_flags_one_finding_not_combinatorial() -> None:
    """A single point drifting off a shared rail should produce one finding,
    not one per pair against every other point on that rail (regression: the
    naive pairwise version over-reports by a combinatorial factor)."""
    points = [Point(10.0, y) for y in (0, 20, 40, 60)] + [Point(10.3, 80.0)]
    findings = check_near_alignment(points, tolerance=0.5)
    assert len(findings) == 1
    assert findings[0].kind == "near_misaligned_pins"


def test_exact_alignment_not_flagged() -> None:
    points = [Point(10.0, 0.0), Point(10.0, 20.0), Point(10.0, 40.0)]
    assert check_near_alignment(points, tolerance=0.5) == []


# ---------------------------------------------------------------------------
# Check 5: redundant jogs
# ---------------------------------------------------------------------------


def test_junction_not_treated_as_redundant_jog() -> None:
    """Three segments meeting at one point (a T-junction/bus tap) must not be
    fused into one fictitious chain and flagged as a redundant jog."""
    drop = _line(0, 0, 0, 10)
    tap_a = _line(0, 10, 10, 10)
    tap_b = _line(0, 10, 0, 20)
    assert check_redundant_jogs([drop, tap_a, tap_b]) == []


def test_redundant_jog_flagged_when_unobstructed() -> None:
    # A 3-segment staircase between (0,0) and (10,10) with no obstacle in the
    # way of the simpler single-bend route.
    chain = [_line(0, 0, 5, 0), _line(5, 0, 5, 10), _line(5, 10, 10, 10)]
    findings = check_redundant_jogs(chain)
    assert findings != []
    assert findings[0].kind == "redundant_jog_candidate"


def test_redundant_jog_suppressed_when_obstacle_justifies_it() -> None:
    chain = [_line(0, 0, 5, 0), _line(5, 0, 5, 10), _line(5, 10, 10, 10)]
    # Obstacle blocks both single-bend candidates between (0,0) and (10,10).
    obstacle = (0.0, 0.0, 10.0, 10.0)
    assert check_redundant_jogs(chain, obstacles=(obstacle,)) == []


# ---------------------------------------------------------------------------
# collect_wire_geometry: Symbol-boundary exclusion
# ---------------------------------------------------------------------------


def test_collect_wire_geometry_excludes_symbol_interior_lines() -> None:
    """A Symbol's interior Line (e.g. a breaker's diagonal isolator blade) is
    glyph artwork, not a wire, and must not be treated as one."""
    glyph = Symbol(elements=[_line(0, 0, 10, 7)], ports={}, label=None)
    wire = _line(0, 0, 0, 20)
    wires, _texts, obstacles = collect_wire_geometry([glyph, wire])
    assert wires == [wire]
    assert len(obstacles) == 1


def test_collect_wire_geometry_recurses_into_group() -> None:
    grouped_wire = _line(0, 0, 0, 20)
    group = Group(elements=[grouped_wire])
    wires, _texts, _obstacles = collect_wire_geometry([group])
    assert wires == [grouped_wire]


# ---------------------------------------------------------------------------
# Finding / LintReport data model
# ---------------------------------------------------------------------------


def test_lint_report_cost_sums_finding_weights() -> None:
    findings = (
        Finding(
            kind="a", severity="error", message="m1", location=Point(0, 0), weight=2.0
        ),
        Finding(
            kind="b", severity="warn", message="m2", location=Point(1, 1), weight=1.5
        ),
    )
    report = LintReport(findings=findings)
    assert report.cost == 3.5


def test_lint_report_by_kind_counts_findings() -> None:
    findings = (
        Finding(
            kind="a", severity="error", message="m1", location=Point(0, 0), weight=1.0
        ),
        Finding(
            kind="a", severity="error", message="m2", location=Point(0, 0), weight=1.0
        ),
        Finding(
            kind="b", severity="warn", message="m3", location=Point(0, 0), weight=1.0
        ),
    )
    report = LintReport(findings=findings)
    assert report.by_kind() == {"a": 2, "b": 1}


def test_lint_elements_returns_empty_report_for_clean_geometry() -> None:
    report = lint_elements([_line(0, 0, 0, 10)])
    assert report.findings == ()
    assert report.cost == 0.0


# ---------------------------------------------------------------------------
# lint_build_result: duck-typed dispatch
# ---------------------------------------------------------------------------


def test_lint_build_result_dispatches_on_elements_attribute() -> None:
    fake_result = SimpleNamespace(elements=[_line(0, 0, 10, 1)])
    report = lint_build_result(fake_result)
    assert report.findings[0].kind == "non_orthogonal_wire"


def test_lint_build_result_dispatches_on_circuit_attribute() -> None:
    fake_result = SimpleNamespace(
        circuit=SimpleNamespace(elements=[_line(0, 0, 10, 1)])
    )
    report = lint_build_result(fake_result)
    assert report.findings[0].kind == "non_orthogonal_wire"


def test_lint_build_result_dispatches_on_diagram_attribute() -> None:
    fake_result = SimpleNamespace(
        diagram=SimpleNamespace(elements=[_line(0, 0, 10, 1)])
    )
    report = lint_build_result(fake_result)
    assert report.findings[0].kind == "non_orthogonal_wire"


# ---------------------------------------------------------------------------
# Integration: real circuits from every domain that produces an Element tree.
# ---------------------------------------------------------------------------


def _build_dol_starter_circuit():
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)
    builder.add_terminal("X1", config=TerminalConfig(poles=3))
    builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F", poles=3))
    builder.add_symbol(contactor, config=SymbolConfig(tag_prefix="Q", poles=3))
    builder.add_symbol(thermal_overload, config=SymbolConfig(tag_prefix="FT", poles=3))
    builder.add_symbol(motor, config=SymbolConfig(tag_prefix="M", poles=3))
    builder.add_terminal("X2", config=TerminalConfig(poles=3, pins=("U1", "V1", "W1")))
    return builder.build(options=BuildOptions(count=1))


def test_real_electrical_circuit_has_zero_wire_geometry_findings() -> None:
    """Proves the checks generalize past synthetic cases: a real, correctly
    built circuit should have no orthogonality/collision/alignment/jog
    findings."""
    result = _build_dol_starter_circuit()
    assert lint_build_result(result).findings == ()


def test_validate_electrical_passes_on_real_circuit() -> None:
    result = validate_electrical(_build_dol_starter_circuit().circuit)
    assert result.passed
    assert result.warnings == []


def test_real_pid_diagram_has_zero_wire_geometry_findings() -> None:
    """Regression for the fixed PIDBuilder flattening bug (pid/builder.py):
    a lone tank's own rectangular outline must not be mistaken for a wire
    with a redundant jog now that equipment Symbols are preserved, not
    flattened, in `diagram.elements`."""
    builder = PIDBuilder()
    builder.add_equipment(
        "tank",
        config=EquipmentConfig(factory=tank, tag_prefix="T"),
        placement=EquipmentPlacement(x=50, y=100),
    )
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=120, y=100),
    )
    result = builder.build()
    assert lint_build_result(result).findings == ()


def test_pid_diagram_still_catches_a_real_crooked_wire() -> None:
    """The equipment-glyph exclusion must not blind the checks to genuine
    pipe defects appended alongside real equipment."""
    builder = PIDBuilder()
    builder.add_equipment(
        "tank",
        config=EquipmentConfig(factory=tank, tag_prefix="T"),
        placement=EquipmentPlacement(x=50, y=100),
    )
    result = builder.build()
    result.diagram.elements.append(_line(0, 0, 10, 1))
    findings = lint_build_result(result).findings
    assert any(f.kind == "non_orthogonal_wire" for f in findings)


def test_real_pcb_nc_terminator_has_zero_wire_geometry_findings() -> None:
    """Regression for the fixed pcb/render.py bug: the NC X-mark's diagonal
    lines and label, now wrapped in a glyph Symbol, must not be mistaken for
    a crooked wire or a text/wire collision."""
    block = ConnectorBlock(
        connector_ref="J1",
        functional_label=None,
        pin_columns=(
            PinColumns(
                pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),)
            ),
        ),
    )
    circuit = render_connector_block(block)
    assert lint_elements(circuit.elements).findings == ()
