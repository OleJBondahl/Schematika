"""Tests for the wire-geometry checks: orthogonality, near-alignment,
text/wire collision, and redundant jogs."""

from __future__ import annotations

from schematika import (
    CircuitBuilder,
    breaker,
    contactor,
    create_initial_state,
    motor,
    thermal_overload,
)
from schematika.core.geometry import Point, Style
from schematika.core.options import BuildOptions, SymbolConfig, TerminalConfig
from schematika.core.primitives import Group, Line, Text
from schematika.core.symbol import Symbol
from schematika.core.validation import (
    check_near_alignment,
    check_orthogonal_wires,
    check_redundant_jogs,
    check_text_wire_collisions,
    check_wire_geometry,
    collect_wire_geometry,
)
from schematika.electrical.validation import validate_electrical

_STYLE = Style(stroke="black", fill="none")


def _line(x1: float, y1: float, x2: float, y2: float) -> Line:
    return Line(Point(x1, y1), Point(x2, y2), _STYLE)


def _text(content: str, x: float, y: float, rotation: float = 0.0) -> Text:
    return Text(content=content, position=Point(x, y), style=_STYLE, rotation=rotation)


def test_orthogonal_wire_passes() -> None:
    assert check_orthogonal_wires([_line(0, 0, 0, 10)]) == []
    assert check_orthogonal_wires([_line(0, 0, 10, 0)]) == []


def test_crooked_wire_flagged() -> None:
    warnings = check_orthogonal_wires([_line(0, 0, 10, 1)])
    assert len(warnings) == 1


def test_text_on_wire_flagged() -> None:
    wire = _line(0, 0, 0, 20)
    label = _text("X1", x=0.0, y=10.0)
    assert check_text_wire_collisions([wire], [label]) != []


def test_text_clear_of_wire_not_flagged() -> None:
    wire = _line(0, 0, 0, 20)
    label = _text("X1", x=50.0, y=10.0)
    assert check_text_wire_collisions([wire], [label]) == []


def test_near_alignment_flags_one_warning_not_combinatorial() -> None:
    """A single point drifting off a shared rail should produce one warning,
    not one per pair against every other point on that rail (regression: the
    naive pairwise version over-reports by a combinatorial factor)."""
    points = [Point(10.0, y) for y in (0, 20, 40, 60)] + [Point(10.3, 80.0)]
    warnings = check_near_alignment(points, tolerance=0.5)
    assert len(warnings) == 1


def test_exact_alignment_not_flagged() -> None:
    points = [Point(10.0, 0.0), Point(10.0, 20.0), Point(10.0, 40.0)]
    assert check_near_alignment(points, tolerance=0.5) == []


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
    assert check_redundant_jogs(chain) != []


def test_redundant_jog_suppressed_when_obstacle_justifies_it() -> None:
    chain = [_line(0, 0, 5, 0), _line(5, 0, 5, 10), _line(5, 10, 10, 10)]
    # Obstacle blocks both single-bend candidates between (0,0) and (10,10).
    obstacle = (0.0, 0.0, 10.0, 10.0)
    assert check_redundant_jogs(chain, obstacles=(obstacle,)) == []


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
    return builder.build(options=BuildOptions(count=1)).circuit


def test_real_circuit_has_zero_wire_geometry_findings() -> None:
    """A real, correctly-built circuit should have no orthogonality/collision/
    alignment/jog findings -- proves the checks generalize past synthetic
    cases, not just that they can be made to pass on contrived input."""
    circuit = _build_dol_starter_circuit()
    assert check_wire_geometry(circuit.elements) == []


def test_validate_electrical_passes_on_real_circuit() -> None:
    circuit = _build_dol_starter_circuit()
    result = validate_electrical(circuit)
    assert result.passed
    assert result.warnings == []
