"""Tests for schematika.pcb.symbols.power."""

from schematika.pcb.symbols.power import gnd, power_24v


def test_power_24v_has_single_port_named_1() -> None:
    sym = power_24v()
    assert list(sym.ports.keys()) == ["1"]


def test_power_24v_port_is_at_bottom_pointing_up() -> None:
    sym = power_24v()
    port = sym.ports["1"]
    # Port faces upward (chain enters from below)
    assert port.direction.dx == 0
    assert port.direction.dy < 0


def test_power_24v_label_visible() -> None:
    sym = power_24v()
    text_contents = [getattr(el, "content", None) for el in sym.elements]
    assert "+24V" in text_contents


def test_gnd_has_single_port_named_1() -> None:
    sym = gnd()
    assert list(sym.ports.keys()) == ["1"]


def test_gnd_port_is_at_top_pointing_up() -> None:
    sym = gnd()
    port = sym.ports["1"]
    assert port.direction.dx == 0
    # Wire enters from above; symbol hangs below the port
    assert port.direction.dy < 0


def test_gnd_label_visible() -> None:
    sym = gnd()
    text_contents = [getattr(el, "content", None) for el in sym.elements]
    assert "GND" in text_contents


def test_power_24v_line_at_port_row() -> None:
    """Horizontal line must coincide with the port row (y=0) so the chain wire ends there."""
    from schematika.core.primitives import Line

    sym = power_24v()
    lines = [el for el in sym.elements if isinstance(el, Line)]
    assert len(lines) == 1, f"Expected exactly 1 line, got {len(lines)}"
    ln = lines[0]
    # Both endpoints share the same y (horizontal line).
    assert abs(ln.start.y - ln.end.y) < 1e-9, (
        f"Line is not horizontal: start.y={ln.start.y}, end.y={ln.end.y}"
    )
    # Line is at the port row (y=0).
    port_y = sym.ports["1"].position.y
    assert abs(ln.start.y - port_y) < 1e-9, (
        f"Line y={ln.start.y} should coincide with port y={port_y}"
    )
    # Line is symmetric about x=0.
    assert abs(ln.start.x + ln.end.x) < 1e-9, (
        f"Line not centered: start.x={ln.start.x}, end.x={ln.end.x}"
    )


def test_power_24v_label_below_line() -> None:
    """Label must sit below the horizontal line by the standard symbol-to-label distance."""
    from schematika.core.constants import TERMINAL_TEXT_OFFSET_X
    from schematika.core.primitives import Line, Text

    sym = power_24v()
    lines = [el for el in sym.elements if isinstance(el, Line)]
    texts = [el for el in sym.elements if isinstance(el, Text)]
    assert lines, "Expected at least one line element"
    assert texts, "Expected at least one text element"
    line_y = lines[0].start.y
    label_y = texts[0].position.y
    expected_y = line_y + (-TERMINAL_TEXT_OFFSET_X)
    assert abs(label_y - expected_y) < 1e-9, (
        f"Label y={label_y} should be {expected_y} (line_y + standard gap -TERMINAL_TEXT_OFFSET_X={-TERMINAL_TEXT_OFFSET_X})"
    )


def test_gnd_label_below_body() -> None:
    """GND label must sit below the body, centered on x=0, mirroring +24V pattern."""
    from schematika.core.constants import TERMINAL_TEXT_OFFSET_X
    from schematika.core.primitives import Text

    sym = gnd()
    texts = [el for el in sym.elements if isinstance(el, Text)]
    assert texts, "Expected at least one text element"
    label_text = next((t for t in texts if t.content == "GND"), None)
    assert label_text is not None, "Expected GND label text"
    assert abs(label_text.position.x) < 1e-9, (
        f"GND label x={label_text.position.x} should be 0"
    )
    expected_y = -TERMINAL_TEXT_OFFSET_X
    assert abs(label_text.position.y - expected_y) < 1e-9, (
        f"GND label y={label_text.position.y} should be {expected_y}"
    )
    assert label_text.anchor == "middle", (
        f"GND label anchor={label_text.anchor!r} should be 'middle'"
    )
