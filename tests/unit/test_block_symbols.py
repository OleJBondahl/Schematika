"""
Tests for block diagram symbol factories.
"""

from schematika.block.constants import (
    BLOCK_DEFAULT_HEIGHT,
    BLOCK_DEFAULT_WIDTH,
    BLOCK_TEXT_SIZE_LABEL,
    BLOCK_TEXT_SIZE_NOTE,
    LEGEND_ENTRY_HEIGHT,
    LEGEND_LINE_SAMPLE_LENGTH,
)
from schematika.block.model import (
    AC_POWER,
    DC_CONTROL,
    SIGNAL_CABLE,
    BlockPort,
)
from schematika.block.symbols import block_symbol, legend_symbol
from schematika.core.geometry import Vector
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Symbol

# ---------------------------------------------------------------------------
# block_symbol — basic structure
# ---------------------------------------------------------------------------


def test_block_symbol_returns_symbol():
    sym = block_symbol("PSU")
    assert isinstance(sym, Symbol)


def test_block_symbol_label():
    sym = block_symbol("PSU")
    assert sym.label == "PSU"


def test_block_symbol_has_four_lines_and_one_text():
    sym = block_symbol("PSU")
    lines = [e for e in sym.elements if isinstance(e, Line)]
    texts = [e for e in sym.elements if isinstance(e, Text)]
    assert len(lines) == 4
    assert len(texts) == 1


def test_block_symbol_text_content():
    sym = block_symbol("My Block")
    texts = [e for e in sym.elements if isinstance(e, Text)]
    assert texts[0].content == "My Block"


def test_block_symbol_text_font_size():
    sym = block_symbol("X")
    texts = [e for e in sym.elements if isinstance(e, Text)]
    assert texts[0].font_size == BLOCK_TEXT_SIZE_LABEL


# ---------------------------------------------------------------------------
# block_symbol — default ports
# ---------------------------------------------------------------------------


def test_block_symbol_default_ports_exist():
    sym = block_symbol("B")
    assert "left" in sym.ports
    assert "right" in sym.ports
    assert "top" in sym.ports
    assert "bottom" in sym.ports


def test_block_symbol_default_port_positions():
    sym = block_symbol("B")
    half_w = BLOCK_DEFAULT_WIDTH / 2
    half_h = BLOCK_DEFAULT_HEIGHT / 2

    assert abs(sym.ports["left"].position.x - (-half_w)) < 1e-6
    assert abs(sym.ports["left"].position.y - 0.0) < 1e-6

    assert abs(sym.ports["right"].position.x - half_w) < 1e-6
    assert abs(sym.ports["right"].position.y - 0.0) < 1e-6

    assert abs(sym.ports["top"].position.x - 0.0) < 1e-6
    assert abs(sym.ports["top"].position.y - (-half_h)) < 1e-6

    assert abs(sym.ports["bottom"].position.x - 0.0) < 1e-6
    assert abs(sym.ports["bottom"].position.y - half_h) < 1e-6


def test_block_symbol_default_port_directions():
    sym = block_symbol("B")
    assert sym.ports["left"].direction == Vector(-1, 0)
    assert sym.ports["right"].direction == Vector(1, 0)
    assert sym.ports["top"].direction == Vector(0, -1)
    assert sym.ports["bottom"].direction == Vector(0, 1)


# ---------------------------------------------------------------------------
# block_symbol — custom ports
# ---------------------------------------------------------------------------


def test_block_symbol_custom_ports():
    custom = [
        BlockPort(id="eth1", side="left", position=0.25),
        BlockPort(id="eth2", side="left", position=0.75),
    ]
    sym = block_symbol("Switch", ports=custom)
    assert "eth1" in sym.ports
    assert "eth2" in sym.ports
    assert "left" not in sym.ports  # defaults replaced


def test_block_symbol_custom_port_position():
    custom = [BlockPort(id="top_left", side="top", position=0.25)]
    w, h = 80.0, 40.0
    sym = block_symbol("B", width=w, height=h, ports=custom)
    half_w = w / 2
    half_h = h / 2
    expected_x = -half_w + 0.25 * (2 * half_w)
    expected_y = -half_h
    assert abs(sym.ports["top_left"].position.x - expected_x) < 1e-6
    assert abs(sym.ports["top_left"].position.y - expected_y) < 1e-6


# ---------------------------------------------------------------------------
# block_symbol — custom width/height
# ---------------------------------------------------------------------------


def test_block_symbol_custom_dimensions_affect_lines():
    w, h = 60.0, 30.0
    sym = block_symbol("B", width=w, height=h)
    lines = [e for e in sym.elements if isinstance(e, Line)]
    # Top line: from (-30, -15) to (30, -15)
    top_line = lines[0]
    assert abs(top_line.start.x - (-w / 2)) < 1e-6
    assert abs(top_line.end.x - (w / 2)) < 1e-6
    assert abs(top_line.start.y - (-h / 2)) < 1e-6


def test_block_symbol_custom_fill():
    sym = block_symbol("B", fill="#eee")
    lines = [e for e in sym.elements if isinstance(e, Line)]
    # Fill is on the rect style, but lines use stroke; fill is set on style
    assert lines[0].style.fill == "#eee"


# ---------------------------------------------------------------------------
# legend_symbol — basic
# ---------------------------------------------------------------------------


def test_legend_symbol_returns_symbol():
    entries = [("AC Power", AC_POWER)]
    sym = legend_symbol(entries)
    assert isinstance(sym, Symbol)


def test_legend_symbol_label():
    entries = [("AC Power", AC_POWER)]
    sym = legend_symbol(entries)
    assert sym.label == "legend"


def test_legend_symbol_no_ports():
    entries = [("Signal", SIGNAL_CABLE)]
    sym = legend_symbol(entries)
    assert sym.ports == {}


def test_legend_symbol_elements_per_entry():
    entries = [("AC Power", AC_POWER), ("DC Control", DC_CONTROL)]
    sym = legend_symbol(entries)
    lines = [e for e in sym.elements if isinstance(e, Line)]
    texts = [e for e in sym.elements if isinstance(e, Text)]
    # Each entry produces one line sample + one text label
    assert len(lines) == 2
    assert len(texts) == 2


def test_legend_symbol_line_sample_length():
    entries = [("Signal", SIGNAL_CABLE)]
    sym = legend_symbol(entries)
    lines = [e for e in sym.elements if isinstance(e, Line)]
    line = lines[0]
    assert abs(line.start.x - 0.0) < 1e-6
    assert abs(line.end.x - LEGEND_LINE_SAMPLE_LENGTH) < 1e-6


def test_legend_symbol_text_position():
    entries = [("Signal", SIGNAL_CABLE)]
    sym = legend_symbol(entries)
    texts = [e for e in sym.elements if isinstance(e, Text)]
    expected_x = LEGEND_LINE_SAMPLE_LENGTH + BLOCK_TEXT_SIZE_NOTE
    assert abs(texts[0].position.x - expected_x) < 1e-6


def test_legend_symbol_line_style_matches_cable():
    entries = [("AC Power", AC_POWER)]
    sym = legend_symbol(entries)
    lines = [e for e in sym.elements if isinstance(e, Line)]
    assert lines[0].style.stroke == AC_POWER.color
    assert abs(lines[0].style.stroke_width - AC_POWER.stroke_width) < 1e-6


# ---------------------------------------------------------------------------
# legend_symbol — with notes
# ---------------------------------------------------------------------------


def test_legend_symbol_with_notes_appends_text():
    entries = [("Signal", SIGNAL_CABLE)]
    notes = ["Note 1", "Note 2"]
    sym = legend_symbol(entries, notes=notes)
    texts = [e for e in sym.elements if isinstance(e, Text)]
    # 1 entry text + 2 note texts = 3
    assert len(texts) == 3


def test_legend_symbol_note_content():
    entries = [("Signal", SIGNAL_CABLE)]
    notes = ["All cables shielded"]
    sym = legend_symbol(entries, notes=notes)
    texts = [e for e in sym.elements if isinstance(e, Text)]
    note_text = texts[-1]
    assert note_text.content == "All cables shielded"


def test_legend_symbol_note_font_size():
    entries = [("Signal", SIGNAL_CABLE)]
    notes = ["A note"]
    sym = legend_symbol(entries, notes=notes)
    texts = [e for e in sym.elements if isinstance(e, Text)]
    note_text = texts[-1]
    assert note_text.font_size == BLOCK_TEXT_SIZE_NOTE


def test_legend_symbol_no_notes():
    entries = [("Signal", SIGNAL_CABLE)]
    sym = legend_symbol(entries, notes=None)
    texts = [e for e in sym.elements if isinstance(e, Text)]
    assert len(texts) == 1  # only entry label


def test_legend_symbol_entry_vertical_spacing():
    entries = [("A", AC_POWER), ("B", DC_CONTROL), ("C", SIGNAL_CABLE)]
    sym = legend_symbol(entries)
    lines = [e for e in sym.elements if isinstance(e, Line)]
    # Second entry line should be at y = LEGEND_ENTRY_HEIGHT
    assert abs(lines[1].start.y - LEGEND_ENTRY_HEIGHT) < 1e-6
    # Third entry line should be at y = 2 * LEGEND_ENTRY_HEIGHT
    assert abs(lines[2].start.y - 2 * LEGEND_ENTRY_HEIGHT) < 1e-6
