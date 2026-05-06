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


def test_power_24v_body_above_port() -> None:
    """+24V: the triangle body must extend UPWARD (lower Y) from the port.

    Port is the chain-bottom connection; all geometric elements that form
    the body must have Y coordinates <= port.position.y.
    """
    from schematika.core.primitives import Line

    sym = power_24v()
    port_y = sym.ports["1"].position.y

    body_lines = [el for el in sym.elements if isinstance(el, Line)]
    assert body_lines, "Expected body lines for triangle"
    for ln in body_lines:
        assert ln.start.y <= port_y + 1e-9, (
            f"Line start y={ln.start.y} is below port y={port_y}"
        )
        assert ln.end.y <= port_y + 1e-9, (
            f"Line end y={ln.end.y} is below port y={port_y}"
        )


def test_power_24v_horizontal_line_at_top() -> None:
    """Horizontal line must be above the port (lower Y) and span the full width."""
    from schematika.core.primitives import Line

    sym = power_24v()
    lines = [el for el in sym.elements if isinstance(el, Line)]
    assert len(lines) == 1, f"Expected exactly 1 line, got {len(lines)}"
    ln = lines[0]
    # Both endpoints share the same y (horizontal line).
    assert abs(ln.start.y - ln.end.y) < 1e-9, (
        f"Line is not horizontal: start.y={ln.start.y}, end.y={ln.end.y}"
    )
    # Line is above the port (lower y value).
    port_y = sym.ports["1"].position.y
    assert ln.start.y < port_y, f"Line y={ln.start.y} should be above port y={port_y}"
    # Line is symmetric about x=0.
    assert abs(ln.start.x + ln.end.x) < 1e-9, (
        f"Line not centered: start.x={ln.start.x}, end.x={ln.end.x}"
    )


def test_power_24v_label_between_line_and_port() -> None:
    """Label y must be strictly between the horizontal line y and the port y."""
    from schematika.core.primitives import Line, Text

    sym = power_24v()
    lines = [el for el in sym.elements if isinstance(el, Line)]
    texts = [el for el in sym.elements if isinstance(el, Text)]
    assert lines, "Expected at least one line element"
    assert texts, "Expected at least one text element"
    line_y = lines[0].start.y
    port_y = sym.ports["1"].position.y
    label_y = texts[0].position.y
    assert line_y < label_y < port_y, (
        f"Label y={label_y} should be between line y={line_y} and port y={port_y}"
    )
