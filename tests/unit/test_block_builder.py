"""
Tests for BlockBuilder.
"""

from pathlib import Path

import pytest

from schematika.block.builder import BlockBuilder, BlockBuildResult
from schematika.block.diagram import render_block_diagram
from schematika.block.model import (
    AC_POWER,
    SIGNAL_CABLE,
    CableStyle,
)
from schematika.block.templates import BlockTemplate, TemplateBlock, TemplateCable
from schematika.catalog.cables import CableRegistry, CableSpec
from schematika.core.autonumbering import next_tag
from schematika.core.state import create_initial_state

# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_builder_single_block():
    builder = BlockBuilder()
    builder.add_block("psu", "24V PSU", x=50, y=80)
    result = builder.build()

    assert isinstance(result, BlockBuildResult)
    assert "psu" in result.block_map
    assert len(result.diagram.blocks) == 1


def test_builder_single_block_tag():
    builder = BlockBuilder()
    builder.add_block("psu", "24V PSU", x=50, y=80)
    result = builder.build()

    assert result.block_map["psu"] == "BLK1"


def test_builder_single_block_in_diagram():
    builder = BlockBuilder()
    builder.add_block("psu", "24V PSU", x=10, y=20)
    result = builder.build()

    assert len(result.diagram.blocks) == 1
    assert result.diagram.blocks[0].label == "24V PSU"


# ---------------------------------------------------------------------------
# Multiple blocks with relative placement
# ---------------------------------------------------------------------------


def test_builder_relative_placement():
    builder = BlockBuilder()
    builder.add_block("psu", "PSU", x=50, y=80)
    builder.add_block(
        "plc", "PLC", relative_to="psu", from_side="right", to_side="left"
    )
    result = builder.build()

    assert len(result.diagram.blocks) == 2
    assert result.block_map["psu"] == "BLK1"
    assert result.block_map["plc"] == "BLK2"


def test_builder_relative_placement_aligns_ports():
    builder = BlockBuilder()
    builder.add_block("psu", "PSU", x=100, y=100)
    builder.add_block(
        "plc", "PLC", relative_to="psu", from_side="right", to_side="left"
    )
    result = builder.build()

    psu_sym = result.diagram.blocks[0]
    plc_sym = result.diagram.blocks[1]

    psu_right = psu_sym.ports["right"].position
    plc_left = plc_sym.ports["left"].position

    assert abs(psu_right.x - plc_left.x) < 1e-6
    assert abs(psu_right.y - plc_left.y) < 1e-6


# ---------------------------------------------------------------------------
# Cable connections
# ---------------------------------------------------------------------------


def test_builder_cable_generates_elements():
    builder = BlockBuilder()
    builder.add_block("a", "Block A", x=0, y=0)
    builder.add_block("b", "Block B", x=100, y=0)
    builder.cable("a", "b", cable_type="signal")
    result = builder.build()

    # Diagram should have elements beyond just the two blocks' elements
    block_element_count = sum(len(sym.elements) for sym in result.diagram.blocks)
    assert len(result.diagram.elements) > block_element_count


def test_builder_cable_with_cable_tag_from_registry():
    registry = CableRegistry()
    spec = CableSpec(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="PSU",
        to_device="PLC",
    )
    registry.register(spec)

    builder = BlockBuilder(cable_registry=registry)
    builder.add_block("psu", "PSU", x=0, y=0)
    builder.add_block("plc", "PLC", x=100, y=0)
    builder.cable("psu", "plc", cable_tag="W0001")
    result = builder.build()

    # Should build without error and have cable elements
    block_element_count = sum(len(sym.elements) for sym in result.diagram.blocks)
    assert len(result.diagram.elements) > block_element_count


def test_builder_cable_with_inline_spec():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    builder.add_block("b", "B", x=100, y=0)
    builder.cable("a", "b", spec="2x1.5", cable_type="power_dc")
    result = builder.build()

    block_element_count = sum(len(sym.elements) for sym in result.diagram.blocks)
    assert len(result.diagram.elements) > block_element_count


def test_builder_cable_with_explicit_style():
    custom_style = CableStyle(stroke_width=2.0, color="red")
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    builder.add_block("b", "B", x=100, y=0)
    builder.cable("a", "b", style=custom_style)
    result = builder.build()

    block_element_count = sum(len(sym.elements) for sym in result.diagram.blocks)
    assert len(result.diagram.elements) > block_element_count


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------


def test_builder_add_legend():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    builder.cable("a", "a", cable_type="signal", from_port="right", to_port="left")
    builder.add_legend(300, 200)
    result = builder.build()

    # Legend adds elements to the diagram
    assert len(result.diagram.elements) > 0


def test_builder_add_legend_with_entries():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    entries = [("Power", AC_POWER), ("Signal", SIGNAL_CABLE)]
    builder.add_legend(300, 200, entries=entries)
    result = builder.build()

    assert len(result.diagram.elements) > 0


def test_builder_add_legend_with_notes():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    builder.cable("a", "a", cable_type="power_ac", from_port="right", to_port="left")
    builder.add_legend(300, 200, notes=["All cables shielded"])
    result = builder.build()

    assert len(result.diagram.elements) > 0


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_builder_add_template():
    template = BlockTemplate(
        name="ups",
        blocks=(
            TemplateBlock(role="battery", label="Battery", rel_x=0, rel_y=0),
            TemplateBlock(role="inverter", label="Inverter", rel_x=80, rel_y=0),
        ),
        cables=(
            TemplateCable(
                from_role="battery",
                to_role="inverter",
                cable_type="power_dc",
            ),
        ),
    )
    builder = BlockBuilder()
    builder.add_template(template, "ups1", x=50, y=50)
    result = builder.build()

    assert "ups1-battery" in result.block_map
    assert "ups1-inverter" in result.block_map
    assert len(result.diagram.blocks) == 2


def test_builder_add_template_with_mirror_x():
    template = BlockTemplate(
        name="ups",
        blocks=(
            TemplateBlock(role="battery", label="Battery", rel_x=0, rel_y=0),
            TemplateBlock(role="inverter", label="Inverter", rel_x=80, rel_y=0),
        ),
    )
    builder_normal = BlockBuilder()
    builder_normal.add_template(template, "n", x=100, y=100)
    result_normal = builder_normal.build()

    builder_mirror = BlockBuilder()
    builder_mirror.add_template(template, "m", x=100, y=100, mirror_x=True)
    result_mirror = builder_mirror.build()

    # Mirrored inverter x should be at 100 + (-80) = 20, normal at 100 + 80 = 180
    normal_inv = result_normal.diagram.blocks[1]
    mirror_inv = result_mirror.diagram.blocks[1]

    # The inverter block centers should differ in x
    normal_right = normal_inv.ports["right"].position.x
    mirror_right = mirror_inv.ports["right"].position.x
    assert normal_right != mirror_right


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_builder_duplicate_block_name_raises():
    builder = BlockBuilder()
    builder.add_block("psu", "PSU", x=0, y=0)
    with pytest.raises(ValueError, match="already registered"):
        builder.add_block("psu", "PSU2", x=50, y=50)


def test_builder_relative_to_nonexistent_raises():
    builder = BlockBuilder()
    with pytest.raises(ValueError, match="has not been registered"):
        builder.add_block("plc", "PLC", relative_to="ghost")


# ---------------------------------------------------------------------------
# Method chaining
# ---------------------------------------------------------------------------


def test_add_block_returns_self():
    builder = BlockBuilder()
    ret = builder.add_block("a", "A")
    assert ret is builder


def test_cable_returns_self():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    builder.add_block("b", "B", x=100, y=0)
    ret = builder.cable("a", "b")
    assert ret is builder


def test_add_legend_returns_self():
    builder = BlockBuilder()
    ret = builder.add_legend(0, 0)
    assert ret is builder


def test_add_template_returns_self():
    template = BlockTemplate(
        name="t",
        blocks=(TemplateBlock(role="x", label="X"),),
    )
    builder = BlockBuilder()
    ret = builder.add_template(template, "p")
    assert ret is builder


def test_builder_method_chaining():
    builder = BlockBuilder()
    result = (
        builder.add_block("a", "A", x=0, y=0)
        .add_block("b", "B", relative_to="a", from_side="right", to_side="left")
        .cable("a", "b", cable_type="signal")
        .build()
    )
    assert isinstance(result, BlockBuildResult)


# ---------------------------------------------------------------------------
# State threading
# ---------------------------------------------------------------------------


def test_builder_state_threading():
    state = create_initial_state()

    b1 = BlockBuilder(state)
    b1.add_block("a", "A")
    r1 = b1.build()

    b2 = BlockBuilder(r1.state)
    b2.add_block("b", "B")
    r2 = b2.build()

    assert r1.block_map["a"] == "BLK1"
    assert r2.block_map["b"] == "BLK2"


def test_builder_state_override_in_build():
    state_a = create_initial_state()
    state_b = create_initial_state()

    # Advance state_b so next BLK tag is BLK2
    state_b, _ = next_tag(state_b, "BLK")

    builder = BlockBuilder(state_a)
    builder.add_block("x", "X")
    result = builder.build(state=state_b)

    assert result.block_map["x"] == "BLK2"


def test_builder_custom_tag_prefix():
    builder = BlockBuilder()
    builder.add_block("psu", "PSU", tag_prefix="PWR")
    result = builder.build()

    assert result.block_map["psu"] == "PWR1"


def test_builder_explicit_tag():
    builder = BlockBuilder()
    builder.add_block("psu", "PSU", tag="U1")
    result = builder.build()

    assert result.block_map["psu"] == "U1"


# ---------------------------------------------------------------------------
# Block map
# ---------------------------------------------------------------------------


def test_block_map_contains_all_blocks():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    builder.add_block("b", "B", x=100, y=0)
    builder.add_block("c", "C", x=200, y=0)
    result = builder.build()

    assert set(result.block_map.keys()) == {"a", "b", "c"}
    assert result.block_map["a"] == "BLK1"
    assert result.block_map["b"] == "BLK2"
    assert result.block_map["c"] == "BLK3"


# ---------------------------------------------------------------------------
# Placement geometry
# ---------------------------------------------------------------------------


def test_global_offset_applied():
    builder = BlockBuilder()
    builder.add_block("a", "A", x=0, y=0)
    r_base = builder.build(x=0, y=0)

    builder2 = BlockBuilder()
    builder2.add_block("a", "A", x=0, y=0)
    r_shifted = builder2.build(x=50, y=30)

    pos_base = r_base.diagram.blocks[0].ports["right"].position
    pos_shifted = r_shifted.diagram.blocks[0].ports["right"].position

    assert abs((pos_shifted.x - pos_base.x) - 50) < 1e-6
    assert abs((pos_shifted.y - pos_base.y) - 30) < 1e-6


# ---------------------------------------------------------------------------
# Integration: render to SVG
# ---------------------------------------------------------------------------


def test_builder_render_integration(tmp_path):
    builder = BlockBuilder()
    (
        builder.add_block("psu", "24V PSU", x=50, y=80)
        .add_block(
            "plc",
            "PLC",
            relative_to="psu",
            from_side="right",
            to_side="left",
        )
        .cable("psu", "plc", cable_type="power_dc")
    )
    result = builder.build()

    svg_path = str(tmp_path / "test_block.svg")
    render_block_diagram(result.diagram, svg_path)

    assert Path(svg_path).exists()
    content = Path(svg_path).read_text()
    assert "<svg" in content
