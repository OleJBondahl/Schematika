"""Comprehensive tests for the Block Module V2."""

from pathlib import Path

import pytest

from schematika.block.constants import (
    BLOCK_DEFAULT_HEIGHT,
    BLOCK_GAP,
    BLOCK_MIN_WIDTH,
)
from schematika.block.diagram import BlockDiagram
from schematika.block.layout import resolve_placements, resolve_sizes
from schematika.block.model import (
    AC_POWER,
    DASHED,
    DC_CONTROL,
    ETHERNET,
    SIGNAL_CABLE,
    SOLID,
    Block,
    Cable,
    MirroredBlock,
    Placement,
)
from schematika.block.rendering import (
    render_blocks,
    render_cables,
    render_legend,
    render_notes,
)
from schematika.core.primitives import Line, Text

# ---------------------------------------------------------------------------
# Block creation and containment
# ---------------------------------------------------------------------------


class TestBlockCreation:
    def test_create_block(self):
        b = Block(label="Test")
        assert b.label == "Test"
        assert b.parent is None
        assert b.children == []
        assert b.placement is None

    def test_create_block_with_name(self):
        b = Block(label="Test", name="test")
        assert b.name == "test"

    def test_create_child_block(self):
        parent = Block(label="Parent")
        child = parent.block("Child")
        assert child.parent is parent
        assert child in parent.children
        assert child.label == "Child"

    def test_create_nested_children(self):
        root = Block(label="Root")
        mid = root.block("Mid")
        leaf = mid.block("Leaf")
        assert leaf.parent is mid
        assert mid.parent is root
        assert leaf in mid.children
        assert mid in root.children

    def test_block_with_contains(self):
        b = Block(label="Battery", contains=["LS-H", "LS-L", "LT"])
        assert b.contains == ["LS-H", "LS-L", "LT"]

    def test_block_with_style(self):
        b = Block(label="Ship", style=DASHED)
        assert b.style is DASHED
        assert b.style.dash_pattern is not None

    def test_block_default_style_is_solid(self):
        b = Block(label="X")
        assert b.style.dash_pattern is None

    def test_block_wide(self):
        b = Block(label="Wide", wide=True)
        assert b.wide is True

    def test_block_note(self):
        b = Block(label="X", note="NOTE 1")
        assert b.note == "NOTE 1"


# ---------------------------------------------------------------------------
# Placement methods and conflict detection
# ---------------------------------------------------------------------------


class TestPlacement:
    def test_below(self):
        a = Block(label="A")
        b = Block(label="B")
        result = b.below(a)
        assert result is b
        assert b.placement is not None
        assert b.placement.kind == "below"
        assert b.placement.reference is a
        assert b.placement.align == "center"

    def test_below_with_align(self):
        a = Block(label="A")
        b = Block(label="B")
        b.below(a, align="left")
        assert b.placement.align == "left"

    def test_above(self):
        a = Block(label="A")
        b = Block(label="B")
        b.above(a)
        assert b.placement.kind == "above"

    def test_right_of(self):
        a = Block(label="A")
        b = Block(label="B")
        b.right_of(a)
        assert b.placement.kind == "right_of"

    def test_left_of(self):
        a = Block(label="A")
        b = Block(label="B")
        b.left_of(a)
        assert b.placement.kind == "left_of"

    def test_placement_conflict_raises(self):
        a = Block(label="A")
        b = Block(label="B")
        b.below(a)
        with pytest.raises(ValueError, match="already has placement"):
            b.right_of(a)

    def test_placement_returns_self(self):
        a = Block(label="A")
        b = Block(label="B")
        assert b.below(a) is b


# ---------------------------------------------------------------------------
# BlockDiagram API
# ---------------------------------------------------------------------------


class TestBlockDiagramAPI:
    def test_create_root_block(self):
        d = BlockDiagram()
        msb = d.block("MSB")
        assert msb.label == "MSB"
        assert msb.parent is None
        assert msb in d.blocks

    def test_create_multiple_root_blocks(self):
        d = BlockDiagram()
        d.block("A")
        d.block("B")
        assert len(d.blocks) == 2

    def test_cable(self):
        d = BlockDiagram()
        a = d.block("A")
        b = d.block("B")
        d.cable(a, b, "4x2.5 (W0001)", AC_POWER)
        assert len(d.cables) == 1
        assert d.cables[0].label == "4x2.5 (W0001)"
        assert d.cables[0].style is AC_POWER

    def test_legend(self):
        d = BlockDiagram()
        d.legend()
        assert d._show_legend is True

    def test_notes(self):
        d = BlockDiagram()
        d.notes(["Note 1", "Note 2"])
        assert d._notes == ["Note 1", "Note 2"]

    def test_abbreviations(self):
        d = BlockDiagram()
        d.abbreviations({"LS": "Level switch"})
        assert d._abbreviations == {"LS": "Level switch"}

    def test_blocks_includes_children(self):
        d = BlockDiagram()
        parent = d.block("Parent")
        child = parent.block("Child")
        assert child in d.blocks
        assert parent in d.blocks


# ---------------------------------------------------------------------------
# Mirror
# ---------------------------------------------------------------------------


class TestMirror:
    def test_mirror_creates_copy(self):
        d = BlockDiagram()
        left = d.block("Ship compartment", name="left", style=DASHED)
        left.block("Battery pack", name="bp")

        right = d.mirror(left, name="right")
        assert isinstance(right, MirroredBlock)
        assert right.root.label == "Ship compartment"
        assert right.root.name == "right"
        assert right.root is not left

    def test_mirror_child_access(self):
        d = BlockDiagram()
        left = d.block("Ship", name="left")
        left_bp = left.block("Battery", name="bp")

        right = d.mirror(left, name="right")
        bp = right["bp"]
        assert bp.label == "Battery"
        assert bp is not left_bp

    def test_mirror_flips_left_right(self):
        d = BlockDiagram()
        left = d.block("Container", name="left")
        fd = d.block("Fire detect", name="fd")
        fd.left_of(left)

        right = d.mirror(left, name="right")
        fd_mirror = right["fd"]
        assert fd_mirror.placement.kind == "right_of"

    def test_mirror_flips_align(self):
        d = BlockDiagram()
        parent = d.block("Parent", name="parent")
        child = d.block("Child", name="child")
        child.below(parent, align="left")

        right = d.mirror(parent, name="right")
        child_mirror = right["child"]
        assert child_mirror.placement.align == "right"

    def test_mirror_invalid_name_raises(self):
        d = BlockDiagram()
        left = d.block("Ship", name="left")

        right = d.mirror(left, name="right")
        with pytest.raises(KeyError, match="No mirrored block"):
            right["nonexistent"]

    def test_mirror_adds_to_diagram(self):
        d = BlockDiagram()
        left = d.block("Ship", name="left")
        left.block("BP", name="bp")

        before = len(d.blocks)
        d.mirror(left, name="right")
        after = len(d.blocks)
        # Should have added copies of left and bp
        assert after > before


# ---------------------------------------------------------------------------
# Layout engine: sizing
# ---------------------------------------------------------------------------


class TestLayoutSizing:
    def test_leaf_block_gets_min_width(self):
        b = Block(label="X")
        resolve_sizes([b])
        assert b.width >= BLOCK_MIN_WIDTH

    def test_leaf_block_gets_default_height(self):
        b = Block(label="X")
        resolve_sizes([b])
        assert b.height == BLOCK_DEFAULT_HEIGHT

    def test_long_label_expands_width(self):
        b = Block(label="Very Long Label That Should Expand Width")
        resolve_sizes([b])
        assert b.width > BLOCK_MIN_WIDTH

    def test_contains_affects_size(self):
        b = Block(label="BP", contains=["LS-H", "LS-L", "LT", "TT", "GD"])
        resolve_sizes([b])
        assert b.height > BLOCK_DEFAULT_HEIGHT

    def test_wide_stretches_to_widest_sibling(self):
        a = Block(label="Short", wide=True)
        b = Block(label="This is a very long label for testing wide")
        resolve_sizes([a, b])
        assert a.width == b.width


# ---------------------------------------------------------------------------
# Layout engine: placement resolution
# ---------------------------------------------------------------------------


class TestLayoutPlacement:
    def test_below_placement(self):
        a = Block(label="A")
        b = Block(label="B")
        b.below(a)
        resolve_sizes([a, b])
        resolve_placements([a, b])
        assert b.y == pytest.approx(a.y + a.height + BLOCK_GAP)

    def test_above_placement(self):
        a = Block(label="A")
        b = Block(label="B")
        # Place a first, then b above a
        b.above(a)
        resolve_sizes([a, b])
        resolve_placements([a, b])
        assert b.y == pytest.approx(a.y - b.height - BLOCK_GAP)

    def test_right_of_placement(self):
        a = Block(label="A")
        b = Block(label="B")
        b.right_of(a)
        resolve_sizes([a, b])
        resolve_placements([a, b])
        assert b.x == pytest.approx(a.x + a.width + BLOCK_GAP)
        assert b.y == pytest.approx(a.y)

    def test_left_of_placement(self):
        a = Block(label="A")
        b = Block(label="B")
        b.left_of(a)
        resolve_sizes([a, b])
        resolve_placements([a, b])
        assert b.x == pytest.approx(a.x - b.width - BLOCK_GAP)

    def test_below_align_left(self):
        a = Block(label="A")
        b = Block(label="B")
        b.below(a, align="left")
        resolve_sizes([a, b])
        resolve_placements([a, b])
        assert b.x == pytest.approx(a.x)

    def test_below_align_right(self):
        a = Block(label="A")
        b = Block(label="B")
        b.below(a, align="right")
        resolve_sizes([a, b])
        resolve_placements([a, b])
        assert b.x == pytest.approx(a.x + a.width - b.width)

    def test_cycle_detection(self):
        a = Block(label="A")
        b = Block(label="B")
        a.placement = Placement(kind="below", reference=b)
        b.placement = Placement(kind="below", reference=a)
        resolve_sizes([a, b])
        with pytest.raises(ValueError, match="cycle"):
            resolve_placements([a, b])


# ---------------------------------------------------------------------------
# Cable bundling
# ---------------------------------------------------------------------------


class TestCableBundling:
    def test_single_cable_renders(self):
        a = Block(label="A", x=0, y=0, width=40, height=25)
        b = Block(label="B", x=100, y=0, width=40, height=25)
        cables = [Cable(a, b, "W001", AC_POWER)]
        elements = render_cables(cables, [a, b])
        lines = [e for e in elements if isinstance(e, Line)]
        assert len(lines) >= 1

    def test_multiple_cables_same_pair_bundled(self):
        a = Block(label="A", x=0, y=0, width=40, height=25)
        b = Block(label="B", x=100, y=0, width=40, height=25)
        cables = [
            Cable(a, b, "W001", AC_POWER),
            Cable(a, b, "W002", SIGNAL_CABLE),
            Cable(a, b, "W003", DC_CONTROL),
        ]
        elements = render_cables(cables, [a, b])
        lines = [e for e in elements if isinstance(e, Line)]
        # Should have 3 cable lines (one per cable)
        assert len(lines) == 3

    def test_cable_labels_rendered(self):
        a = Block(label="A", x=0, y=0, width=40, height=25)
        b = Block(label="B", x=100, y=0, width=40, height=25)
        cables = [Cable(a, b, "4x2.5 (W001)", AC_POWER)]
        elements = render_cables(cables, [a, b])
        texts = [e for e in elements if isinstance(e, Text)]
        assert any("W001" in t.content for t in texts)


# ---------------------------------------------------------------------------
# Rendering produces SVG elements
# ---------------------------------------------------------------------------


class TestRendering:
    def test_render_blocks_produces_lines_and_text(self):
        b = Block(label="Test", x=10, y=10, width=40, height=25)
        elements = render_blocks([b])
        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 4  # rectangle
        assert len(texts) >= 1  # label

    def test_render_block_with_contains(self):
        b = Block(
            label="BP",
            x=10,
            y=10,
            width=60,
            height=50,
            contains=["LS-H", "LS-L"],
        )
        elements = render_blocks([b])
        texts = [e for e in elements if isinstance(e, Text)]
        tag_texts = [t for t in texts if t.content in ("LS-H", "LS-L")]
        assert len(tag_texts) == 2

    def test_render_block_with_note(self):
        b = Block(label="X", x=10, y=10, width=40, height=25, note="NOTE 1")
        elements = render_blocks([b])
        texts = [e for e in elements if isinstance(e, Text)]
        assert any("NOTE 1" in t.content for t in texts)

    def test_render_block_dashed_style(self):
        b = Block(label="X", x=10, y=10, width=40, height=25, style=DASHED)
        elements = render_blocks([b])
        lines = [e for e in elements if isinstance(e, Line)]
        assert all(line.style.stroke_dasharray is not None for line in lines)

    def test_render_legend(self):
        elements = render_legend([AC_POWER, SIGNAL_CABLE])
        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 2
        assert len(texts) == 2

    def test_render_legend_deduplicates(self):
        elements = render_legend([AC_POWER, AC_POWER, AC_POWER])
        lines = [e for e in elements if isinstance(e, Line)]
        assert len(lines) == 1

    def test_render_notes(self):
        elements = render_notes(["Note 1", "Note 2"], None)
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(texts) == 2

    def test_render_abbreviations(self):
        elements = render_notes(None, {"LS": "Level switch", "LT": "Level transmitter"})
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(texts) == 2
        assert any("LS" in t.content for t in texts)

    def test_render_notes_with_abbreviations(self):
        elements = render_notes(["Note 1"], {"LS": "Level switch"})
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(texts) == 2


# ---------------------------------------------------------------------------
# BlockStyle constants
# ---------------------------------------------------------------------------


class TestBlockStyleConstants:
    def test_solid_style(self):
        assert SOLID.dash_pattern is None
        assert SOLID.fill == "none"

    def test_dashed_style(self):
        assert DASHED.dash_pattern is not None

    def test_cable_styles(self):
        assert AC_POWER.color == "magenta"
        assert DC_CONTROL.color == "#CCCC00"
        assert SIGNAL_CABLE.color == "blue"
        assert ETHERNET.dash_pattern is not None


# ---------------------------------------------------------------------------
# Full integration: create diagram -> render -> SVG file exists
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_simple_diagram_renders(self, tmp_path):
        d = BlockDiagram()
        msb = d.block("MSB 400VAC")
        esb = d.block("ESB 230VAC")
        esb.below(msb)
        d.cable(msb, esb, "4x95 (W001)", AC_POWER)

        svg_path = str(tmp_path / "test.svg")
        d.render(svg_path)

        assert Path(svg_path).exists()
        content = Path(svg_path).read_text()
        assert "<svg" in content

    def test_diagram_with_containers(self, tmp_path):
        d = BlockDiagram()
        ship = d.block("Ship compartment", style=DASHED)
        bp = ship.block("Battery pack", contains=["LS-H", "LS-L"])
        pc = ship.block("Power cabinet")
        pc.right_of(bp)

        svg_path = str(tmp_path / "containers.svg")
        d.render(svg_path)
        assert Path(svg_path).exists()

    def test_diagram_with_legend_and_notes(self, tmp_path):
        d = BlockDiagram()
        a = d.block("A")
        b = d.block("B")
        b.right_of(a)
        d.cable(a, b, "W001", AC_POWER)
        d.cable(a, b, "W002", SIGNAL_CABLE)
        d.legend()
        d.notes(["1) Subject to calculations"])
        d.abbreviations({"LS": "Level switch"})

        svg_path = str(tmp_path / "full.svg")
        d.render(svg_path)
        assert Path(svg_path).exists()

    def test_diagram_with_mirror(self, tmp_path):
        d = BlockDiagram()
        msb = d.block("MSB")
        left = d.block("Left system", name="left")
        left_bp = left.block("Battery", name="bp")
        left.below(msb, align="left")

        # Mirror flips align="left" -> align="right" automatically
        right = d.mirror(left, name="right")
        assert right.root.placement.align == "right"

        d.cable(msb, left_bp, "W001", AC_POWER)
        d.cable(msb, right["bp"], "W002", AC_POWER)

        svg_path = str(tmp_path / "mirror.svg")
        d.render(svg_path)
        assert Path(svg_path).exists()

    def test_elements_property(self):
        d = BlockDiagram()
        a = d.block("A")
        b = d.block("B")
        b.right_of(a)
        elements = d.elements
        assert len(elements) > 0

    def test_multiple_cable_bundles(self, tmp_path):
        d = BlockDiagram()
        a = d.block("A")
        b = d.block("B")
        b.right_of(a)
        d.cable(a, b, "W001", AC_POWER)
        d.cable(a, b, "W002", SIGNAL_CABLE)
        d.cable(a, b, "W003", DC_CONTROL)
        d.cable(a, b, "W004", ETHERNET)

        svg_path = str(tmp_path / "bundle.svg")
        d.render(svg_path)
        assert Path(svg_path).exists()


# ---------------------------------------------------------------------------
# Corner placement
# ---------------------------------------------------------------------------


def _make_parent_with_child(
    child_w: float = 30, child_h: float = 20
) -> tuple[Block, Block]:
    """Create a parent (100x80 at 10,10) with one child block."""
    parent = Block(label="Parent", x=10, y=10, width=100, height=80)
    child = Block(label="Child", parent=parent, width=child_w, height=child_h)
    parent.children.append(child)
    return parent, child


class TestCornerPlacement:
    def test_inside_top_left(self):
        parent, child = _make_parent_with_child()
        child.place(corner="top-left", inside=True)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x)
        assert child.y == pytest.approx(parent.y)

    def test_inside_top_right(self):
        parent, child = _make_parent_with_child()
        child.place(corner="top-right", inside=True)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + parent.width - child.width)
        assert child.y == pytest.approx(parent.y)

    def test_inside_bottom_left(self):
        parent, child = _make_parent_with_child()
        child.place(corner="bottom-left", inside=True)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x)
        assert child.y == pytest.approx(parent.y + parent.height - child.height)

    def test_inside_bottom_right(self):
        parent, child = _make_parent_with_child()
        child.place(corner="bottom-right", inside=True)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + parent.width - child.width)
        assert child.y == pytest.approx(parent.y + parent.height - child.height)

    def test_inside_center(self):
        parent, child = _make_parent_with_child()
        child.place(corner="center", inside=True)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + parent.width / 2 - child.width / 2)
        assert child.y == pytest.approx(parent.y + parent.height / 2 - child.height / 2)

    def test_outside_top_left(self):
        parent, child = _make_parent_with_child()
        child.place(corner="top-left", inside=False)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x)
        assert child.y == pytest.approx(parent.y - child.height)

    def test_outside_top_right(self):
        parent, child = _make_parent_with_child()
        child.place(corner="top-right", inside=False)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + parent.width - child.width)
        assert child.y == pytest.approx(parent.y - child.height)

    def test_outside_bottom_left(self):
        parent, child = _make_parent_with_child()
        child.place(corner="bottom-left", inside=False)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x)
        assert child.y == pytest.approx(parent.y + parent.height)

    def test_outside_bottom_right(self):
        parent, child = _make_parent_with_child()
        child.place(corner="bottom-right", inside=False)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + parent.width - child.width)
        assert child.y == pytest.approx(parent.y + parent.height)

    def test_with_padding(self):
        parent, child = _make_parent_with_child()
        child.place(corner="top-left", inside=True, padding=5.0)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + 5.0)
        assert child.y == pytest.approx(parent.y + 5.0)

    def test_outside_with_padding(self):
        parent, child = _make_parent_with_child()
        child.place(corner="bottom-right", inside=False, padding=3.0)
        resolve_sizes([parent, child])
        resolve_placements([parent, child])
        assert child.x == pytest.approx(parent.x + parent.width - child.width - 3.0)
        assert child.y == pytest.approx(parent.y + parent.height)

    def test_place_conflict_raises(self):
        _parent, child = _make_parent_with_child()
        child.place(corner="top-left")
        with pytest.raises(ValueError, match="already has placement"):
            child.place(corner="top-right")

    def test_place_then_below_conflict_raises(self):
        _parent, child = _make_parent_with_child()
        other = Block(label="Other")
        child.place(corner="top-left")
        with pytest.raises(ValueError, match="already has placement"):
            child.below(other)

    def test_place_returns_self(self):
        _parent, child = _make_parent_with_child()
        result = child.place(corner="center")
        assert result is child


# ---------------------------------------------------------------------------
# next_to placement
# ---------------------------------------------------------------------------


class TestNextToPlacement:
    def test_next_to_basic(self):
        parent = Block(label="Parent", x=10, y=10, width=200, height=100)
        a = Block(label="A", parent=parent, width=30, height=20)
        b = Block(label="B", parent=parent, width=30, height=20)
        parent.children.extend([a, b])
        a.place(corner="top-left")
        b.next_to(a)
        resolve_sizes([parent, a, b])
        resolve_placements([parent, a, b])
        assert b.x == pytest.approx(a.x + a.width + BLOCK_GAP)
        assert b.y == pytest.approx(a.y)

    def test_next_to_custom_gap(self):
        parent = Block(label="Parent", x=10, y=10, width=200, height=100)
        a = Block(label="A", parent=parent, width=30, height=20)
        b = Block(label="B", parent=parent, width=30, height=20)
        parent.children.extend([a, b])
        a.place(corner="top-left")
        b.next_to(a, gap=5.0)
        resolve_sizes([parent, a, b])
        resolve_placements([parent, a, b])
        assert b.x == pytest.approx(a.x + a.width + 5.0)

    def test_next_to_chain(self):
        parent = Block(label="Parent", x=0, y=0, width=300, height=100)
        a = Block(label="A", parent=parent, width=30, height=20)
        b = Block(label="B", parent=parent, width=30, height=20)
        c = Block(label="C", parent=parent, width=30, height=20)
        parent.children.extend([a, b, c])
        a.place(corner="top-left")
        b.next_to(a)
        c.next_to(b)
        resolve_sizes([parent, a, b, c])
        resolve_placements([parent, a, b, c])
        assert b.x == pytest.approx(a.x + a.width + BLOCK_GAP)
        assert c.x == pytest.approx(b.x + b.width + BLOCK_GAP)
        assert a.y == pytest.approx(b.y)
        assert b.y == pytest.approx(c.y)

    def test_next_to_conflict_raises(self):
        a = Block(label="A")
        b = Block(label="B")
        b.next_to(a)
        with pytest.raises(ValueError, match="already has placement"):
            b.right_of(a)

    def test_next_to_returns_self(self):
        a = Block(label="A")
        b = Block(label="B")
        result = b.next_to(a)
        assert result is b


# ---------------------------------------------------------------------------
# Block rotation
# ---------------------------------------------------------------------------


class TestBlockRotation:
    def test_block_rotation_default(self):
        b = Block(label="X")
        assert b.rotation == 0.0

    def test_block_rotation_set(self):
        b = Block(label="X", rotation=90)
        assert b.rotation == 90.0

    def test_block_rotation_preserved_in_render(self):
        b = Block(label="Rotated", x=10, y=10, width=40, height=25, rotation=90)
        elements = render_blocks([b])
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(texts) >= 1
        label_text = [t for t in texts if t.content == "Rotated"]
        assert len(label_text) == 1
        assert label_text[0].rotation == 90
