"""
Unit tests for PIDBuilder.
"""

from pathlib import Path

import pytest

from schematika.core.autonumbering import next_tag
from schematika.core.state import create_initial_state
from schematika.pid.builder import PIDBuilder, PIDBuildResult
from schematika.pid.diagram import render_pid
from schematika.pid.symbols import (
    centrifugal_pump,
    gate_valve,
    heat_exchanger,
    tank,
)

# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_builder_single_equipment():
    """Build with just one piece of equipment."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T")
    result = builder.build()

    assert isinstance(result, PIDBuildResult)
    assert "tank" in result.equipment_map
    assert result.equipment_map["tank"] == "T1"


def test_builder_single_equipment_in_diagram():
    """The placed symbol should be in the diagram's equipment list."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T", x=10, y=20)
    result = builder.build()

    assert len(result.diagram.equipment) == 1
    assert result.diagram.equipment[0].label == "T1"


def test_builder_chain():
    """Build a simple process chain: tank -> pump -> heat exchanger."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T", x=50, y=100)
    builder.add_equipment(
        "pump",
        centrifugal_pump,
        "P",
        relative_to="tank",
        from_port="outlet",
        to_port="inlet",
    )
    builder.add_equipment(
        "hx",
        heat_exchanger,
        "HX",
        relative_to="pump",
        from_port="outlet",
        to_port="shell_in",
    )
    builder.pipe("tank", "pump")
    builder.pipe("pump", "hx", from_port="outlet", to_port="shell_in")
    result = builder.build()

    assert len(result.equipment_map) == 3
    assert result.equipment_map["tank"] == "T1"
    assert result.equipment_map["pump"] == "P1"
    assert result.equipment_map["hx"] == "HX1"


def test_builder_with_instrument():
    """Attach an instrument to equipment."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P", x=50, y=50)
    builder.add_instrument("tt101", "TT", on_equipment="pump", on_port="outlet")
    result = builder.build()

    assert "tt101" in result.instrument_map
    assert result.instrument_map["tt101"] == "TT1"
    # Instrument should also appear in the diagram
    tags = [sym.label for sym in result.diagram.equipment]
    assert any("TT" in (t or "") for t in tags)


def test_builder_with_pipes():
    """Verify pipe elements are generated."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T", x=0, y=0)
    builder.add_equipment(
        "pump",
        centrifugal_pump,
        "P",
        relative_to="tank",
        from_port="outlet",
        to_port="inlet",
    )
    builder.pipe("tank", "pump", line_spec="2-CW-101")
    result = builder.build()

    # Diagram should have pipe elements (Lines from render_pipe)
    assert len(result.diagram.elements) > 0


def test_builder_signal_line():
    """Signal lines use dashed style."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P", x=50, y=50)
    builder.add_instrument(
        "tt101", "TT", on_equipment="pump", on_port="outlet", offset=(0, -30)
    )
    builder.signal_line("tt101", "pump", from_port="signal_out", to_port="outlet")
    result = builder.build()

    assert len(result.diagram.elements) > 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_builder_duplicate_equipment_name_raises():
    """Cannot register the same equipment name twice."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P")
    with pytest.raises(ValueError, match="already registered"):
        builder.add_equipment("pump", centrifugal_pump, "P")


def test_builder_duplicate_instrument_name_raises():
    """Cannot register the same instrument name twice."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P")
    builder.add_instrument("tt101", "TT", on_equipment="pump")
    with pytest.raises(ValueError, match="already registered"):
        builder.add_instrument("tt101", "TT", on_equipment="pump")


def test_builder_equipment_and_instrument_same_name_raises():
    """An instrument name cannot duplicate an equipment name."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P")
    with pytest.raises(ValueError, match="already registered"):
        builder.add_instrument("pump", "TT", on_equipment="pump")


def test_builder_invalid_relative_to_raises():
    """Referencing non-existent equipment as anchor raises."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P")
    with pytest.raises(ValueError, match="nonexistent"):
        builder.add_equipment("valve", gate_valve, "V", relative_to="nonexistent")


def test_builder_instrument_unknown_equipment_raises():
    """Instrument referencing unregistered equipment raises."""
    builder = PIDBuilder()
    with pytest.raises(ValueError, match="unknown equipment"):
        builder.add_instrument("tt101", "TT", on_equipment="ghost")


def test_builder_pipe_unknown_from_raises():
    """Pipe from unknown source raises at build time."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T")
    builder.pipe("ghost", "tank")
    with pytest.raises(ValueError, match="unknown equipment"):
        builder.build()


def test_builder_pipe_unknown_to_raises():
    """Pipe to unknown target raises at build time."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T")
    builder.pipe("tank", "ghost")
    with pytest.raises(ValueError, match="unknown equipment"):
        builder.build()


def test_builder_bad_port_on_placement_raises():
    """Placement referencing a non-existent port raises at build time."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T")
    builder.add_equipment(
        "pump",
        centrifugal_pump,
        "P",
        relative_to="tank",
        from_port="nonexistent_port",
        to_port="inlet",
    )
    with pytest.raises(ValueError):
        builder.build()


# ---------------------------------------------------------------------------
# Method chaining
# ---------------------------------------------------------------------------


def test_builder_method_chaining():
    """All mutating methods return self for chaining; build() returns result."""
    builder = PIDBuilder()
    result = (
        builder.add_equipment("tank", tank, "T")
        .add_equipment(
            "pump",
            centrifugal_pump,
            "P",
            relative_to="tank",
            from_port="outlet",
            to_port="inlet",
        )
        .pipe("tank", "pump")
        .build()
    )
    assert isinstance(result, PIDBuildResult)


def test_add_equipment_returns_self():
    builder = PIDBuilder()
    ret = builder.add_equipment("tank", tank, "T")
    assert ret is builder


def test_add_instrument_returns_self():
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P")
    ret = builder.add_instrument("tt101", "TT", on_equipment="pump")
    assert ret is builder


def test_pipe_returns_self():
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T")
    builder.add_equipment(
        "pump",
        centrifugal_pump,
        "P",
        relative_to="tank",
        from_port="outlet",
        to_port="inlet",
    )
    ret = builder.pipe("tank", "pump")
    assert ret is builder


def test_signal_line_returns_self():
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P")
    builder.add_instrument("tt101", "TT", on_equipment="pump")
    ret = builder.signal_line("tt101", "pump", from_port="signal_out", to_port="outlet")
    assert ret is builder


# ---------------------------------------------------------------------------
# State threading
# ---------------------------------------------------------------------------


def test_builder_state_threading():
    """State is threaded through — tag numbers increment across builders."""
    state = create_initial_state()

    b1 = PIDBuilder(state)
    b1.add_equipment("p1", centrifugal_pump, "P")
    r1 = b1.build()

    b2 = PIDBuilder(r1.state)
    b2.add_equipment("p2", centrifugal_pump, "P")
    r2 = b2.build()

    assert r1.equipment_map["p1"] == "P1"
    assert r2.equipment_map["p2"] == "P2"


def test_builder_state_override_in_build():
    """State override in build() takes precedence over builder's state."""
    state_a = create_initial_state()
    state_b = create_initial_state()

    # Advance state_b so next P tag is P2
    state_b, _ = next_tag(state_b, "P")

    builder = PIDBuilder(state_a)
    builder.add_equipment("pump", centrifugal_pump, "P")
    result = builder.build(state=state_b)

    assert result.equipment_map["pump"] == "P2"


# ---------------------------------------------------------------------------
# Placement geometry
# ---------------------------------------------------------------------------


def test_placement_aligns_ports():
    """After port-to-port placement the anchor port and child port coincide."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T", x=100, y=100)
    builder.add_equipment(
        "pump",
        centrifugal_pump,
        "P",
        relative_to="tank",
        from_port="outlet",
        to_port="inlet",
    )
    result = builder.build()

    tank_sym = result.diagram.equipment[0]
    pump_sym = result.diagram.equipment[1]

    tank_outlet = tank_sym.ports["outlet"].position
    pump_inlet = pump_sym.ports["inlet"].position

    assert abs(tank_outlet.x - pump_inlet.x) < 1e-6
    assert abs(tank_outlet.y - pump_inlet.y) < 1e-6


def test_global_offset_applied():
    """Global (x, y) offset in build() shifts all absolute positions."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T", x=0, y=0)
    result_no_offset = builder.build(x=0, y=0)

    builder2 = PIDBuilder()
    builder2.add_equipment("tank", tank, "T", x=0, y=0)
    result_with_offset = builder2.build(x=50, y=30)

    pos_base = result_no_offset.diagram.equipment[0].ports["outlet"].position
    pos_shifted = result_with_offset.diagram.equipment[0].ports["outlet"].position

    assert abs((pos_shifted.x - pos_base.x) - 50) < 1e-6
    assert abs((pos_shifted.y - pos_base.y) - 30) < 1e-6


def test_two_absolute_roots():
    """Two pieces of equipment with no relative_to are both placed independently."""
    builder = PIDBuilder()
    builder.add_equipment("tank1", tank, "T", x=0, y=0)
    builder.add_equipment("tank2", tank, "T", x=200, y=0)
    result = builder.build()

    assert len(result.diagram.equipment) == 2
    assert result.equipment_map["tank1"] == "T1"
    assert result.equipment_map["tank2"] == "T2"


# ---------------------------------------------------------------------------
# Integration: render to SVG
# ---------------------------------------------------------------------------


def test_builder_render_integration(tmp_path):
    """Full pipeline: build + render to SVG file."""
    builder = PIDBuilder()
    builder.add_equipment("tank", tank, "T", x=50, y=80)
    builder.add_equipment(
        "pump",
        centrifugal_pump,
        "P",
        relative_to="tank",
        from_port="outlet",
        to_port="inlet",
    )
    builder.pipe("tank", "pump")
    result = builder.build()

    svg_path = str(tmp_path / "test_pid.svg")
    render_pid(result.diagram, svg_path)

    assert Path(svg_path).exists()
    content = Path(svg_path).read_text()
    assert "<svg" in content


def test_builder_full_pipeline_with_instrument(tmp_path):
    """Full pipeline including instrument bubble renders without error."""
    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P", x=60, y=60)
    builder.add_instrument(
        "tt101",
        "TT",
        on_equipment="pump",
        on_port="outlet",
        offset=(0, -35),
    )
    builder.signal_line("tt101", "pump", from_port="signal_out", to_port="outlet")
    result = builder.build()

    svg_path = str(tmp_path / "pid_instrument.svg")
    render_pid(result.diagram, svg_path)

    assert Path(svg_path).exists()
    content = Path(svg_path).read_text()
    assert "<svg" in content
    assert "TT" in content
