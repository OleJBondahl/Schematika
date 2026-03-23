"""Unit tests for system module."""

from schematika.electrical.model.core import Point, Port, Symbol, Vector
from schematika.electrical.model.primitives import Line
from schematika.electrical.system.system import (
    Circuit,
    add_symbol,
    merge_circuits,
    render_system,
)


def test_merge_circuits_returns_new_circuit():
    """merge_circuits should return a new Circuit, not mutate."""
    e1 = Line(start=Point(0, 0), end=Point(1, 0))
    e2 = Line(start=Point(2, 0), end=Point(3, 0))
    e3 = Line(start=Point(4, 0), end=Point(5, 0))
    e4 = Line(start=Point(6, 0), end=Point(7, 0))
    c1 = Circuit(symbols=[], elements=[e1, e2])
    c2 = Circuit(symbols=[], elements=[e3, e4])

    result = merge_circuits(c1, c2)

    # Result is a new circuit
    assert result is not c1
    assert result is not c2

    # Original circuits unchanged
    assert c1.elements == [e1, e2]
    assert c2.elements == [e3, e4]

    # Merged result correct
    assert result.elements == [e1, e2, e3, e4]


def _make_symbol(label: str, y_top: float = 0.0, y_bot: float = 10.0) -> Symbol:
    return Symbol(
        elements=[Line(Point(0, y_top), Point(0, y_bot))],
        ports={
            "1": Port("1", Point(0, y_top), Vector(0, -1)),
            "2": Port("2", Point(0, y_bot), Vector(0, 1)),
        },
        label=label,
    )


def test_circuit_default_factory():
    """Circuit() with no args has empty symbols and elements lists."""
    c = Circuit()
    assert c.symbols == []
    assert c.elements == []


def test_get_symbol_by_tag_found():
    """get_symbol_by_tag returns the symbol whose label matches."""
    c = Circuit()
    sym = _make_symbol("Q1")
    c.symbols.append(sym)
    assert c.get_symbol_by_tag("Q1") is sym


def test_get_symbol_by_tag_not_found():
    """get_symbol_by_tag returns None when no symbol has that label."""
    c = Circuit()
    c.symbols.append(_make_symbol("Q1"))
    assert c.get_symbol_by_tag("X99") is None


def test_add_symbol():
    """add_symbol translates the symbol and appends it to both lists."""
    c = Circuit()
    sym = _make_symbol("Q1")
    placed = add_symbol(c, sym, 10, 20)
    assert placed.ports["1"].position == Point(10, 20)
    assert placed.ports["2"].position == Point(10, 30)
    assert len(c.symbols) == 1
    assert len(c.elements) == 1


def test_render_system_single_circuit(tmp_path):
    """render_system writes a valid SVG file for a single Circuit."""
    c = Circuit()
    add_symbol(c, _make_symbol("Q1"), 0, 0)
    out = str(tmp_path / "test.svg")
    render_system(c, out)
    content = (tmp_path / "test.svg").read_text()
    assert (tmp_path / "test.svg").exists()
    assert "<svg" in content


def test_render_system_list_of_circuits(tmp_path):
    """render_system writes a valid SVG file for a list of Circuits."""
    c1 = Circuit()
    add_symbol(c1, _make_symbol("Q1"), 0, 0)
    c2 = Circuit()
    add_symbol(c2, _make_symbol("Q2"), 0, 20)
    out = str(tmp_path / "multi.svg")
    render_system([c1, c2], out)
    content = (tmp_path / "multi.svg").read_text()
    assert (tmp_path / "multi.svg").exists()
    assert "<svg" in content
