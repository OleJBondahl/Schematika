"""Tests for schematika.overview.layout.compute_device_positions."""

from schematika.overview.extract import graph_from_input
from schematika.overview.inputs import OverviewInput, OverviewWire
from schematika.overview.layout import compute_device_positions


def _inp(wires, *, field=frozenset(), term=frozenset()):
    return OverviewInput(
        wires=tuple(OverviewWire(a=a, b=b, label=lbl) for a, b, lbl in wires),
        field_device_tags=field,
        terminal_tags=term,
        title="T",
    )


def test_layout_is_deterministic() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None), ("X2..1", "M2..1", None)],
        field={"M1", "M2"},
        term={"X1", "X2"},
    )
    g = graph_from_input(inp)
    result1 = {d.id: (d.x, d.y) for d in compute_device_positions(g).devices}
    result2 = {d.id: (d.x, d.y) for d in compute_device_positions(g).devices}
    assert result1 == result2


def test_field_column_right_of_terminal_column() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None)],
        field={"M1"},
        term={"X1"},
    )
    g = graph_from_input(inp)
    placed = {d.id: d for d in compute_device_positions(g).devices}
    assert placed["M1"].x > placed["X1"].x


def test_internal_left_of_terminal() -> None:
    # K1 is class "K" (internal), X1 is class "X" (terminal)
    inp = _inp(
        [("K1..1", "X1..1", None)],
        term={"X1"},
    )
    g = graph_from_input(inp)
    placed = {d.id: d for d in compute_device_positions(g).devices}
    assert placed["K1"].x < placed["X1"].x


def test_layout_does_not_raise_on_unknown_class() -> None:
    # Classes W and Z are not in any zone
    inp = _inp([("W1..1", "Z9..1", None)])
    g = graph_from_input(inp)
    # Must not raise
    compute_device_positions(g)


def test_terminals_ordered_by_anchor() -> None:
    # X1 connects to M1 (earlier field device), X2 connects to M2 (later).
    # After layout, X1 (lower anchor) should have a smaller y than X2.
    inp = _inp(
        [("X1..1", "M1..1", None), ("X2..1", "M2..1", None)],
        field={"M1", "M2"},
        term={"X1", "X2"},
    )
    g = graph_from_input(inp)
    placed = {d.id: d for d in compute_device_positions(g).devices}

    # Confirm anchors were set
    assert placed["X1"].anchor is not None
    assert placed["X2"].anchor is not None

    # The terminal with the smaller anchor should have the smaller y
    if placed["X1"].anchor < placed["X2"].anchor:
        assert placed["X1"].y < placed["X2"].y, (
            f"X1 anchor={placed['X1'].anchor} < X2 anchor={placed['X2'].anchor} "
            f"but X1.y={placed['X1'].y} >= X2.y={placed['X2'].y}"
        )
    else:
        assert placed["X2"].y < placed["X1"].y, (
            f"X2 anchor={placed['X2'].anchor} < X1 anchor={placed['X1'].anchor} "
            f"but X2.y={placed['X2'].y} >= X1.y={placed['X1'].y}"
        )
