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


def test_power_24v_triangle_points_up() -> None:
    """Triangle apex must be at lower Y than the base (visually upward-pointing)."""
    from schematika.core.primitives import Line

    sym = power_24v()
    lines = [el for el in sym.elements if isinstance(el, Line)]
    # apex is at the single shared endpoint of two lines.
    # Find the point with the minimum Y (highest on screen = apex of upward triangle).
    all_ys = [pt.y for ln in lines for pt in (ln.start, ln.end)]
    min_y = min(all_ys)
    max_y = max(all_ys)
    port_y = sym.ports["1"].position.y
    # Port must be at the base (highest Y = lowest on screen).
    assert abs(port_y - max_y) < 1e-6 or port_y >= max_y - 1e-6, (
        f"Port y={port_y} should be at or near base (max_y={max_y}) for upward triangle"
    )
    # Apex must be above port (lower Y).
    assert min_y < port_y, f"Apex y={min_y} should be above port y={port_y}"


def test_power_24v_apex_is_solitary_top_vertex() -> None:
    """The apex is the unique vertex with min y; base is the two vertices with max y.

    Locks in the upward-pointing geometry: the apex (lone topmost vertex) must
    sit ABOVE the base (two vertices sharing the same max y).
    """
    from schematika.core.primitives import Line

    sym = power_24v()
    lines = [el for el in sym.elements if isinstance(el, Line)]
    pts = [pt for ln in lines for pt in (ln.start, ln.end)]
    ys = [pt.y for pt in pts]
    min_y, max_y = min(ys), max(ys)
    # base: two distinct points at max y; apex: exactly one point at min y.
    base_xs = sorted({pt.x for pt in pts if abs(pt.y - max_y) < 1e-9})
    apex_xs = sorted({pt.x for pt in pts if abs(pt.y - min_y) < 1e-9})
    assert len(base_xs) == 2, f"Expected 2 distinct base x's, got {base_xs}"
    assert len(apex_xs) == 1, f"Expected 1 apex x, got {apex_xs}"
    # Port must be at base-center.
    port_y = sym.ports["1"].position.y
    assert abs(port_y - max_y) < 1e-9, f"Port y={port_y} should be at base y={max_y}"
