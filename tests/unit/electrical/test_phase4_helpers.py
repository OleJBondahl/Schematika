"""Characterisation tests for the 4 phase-4 helpers extracted in wave C1d."""

from __future__ import annotations

from typing import Any

import pytest

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.electrical.builder_models import (
    ComponentSpec,
    PlannedConnection,
    RealizedComponent,
    realized_to_dict,
)
from schematika.electrical.builder_phases import (
    _get_endpoint_symbols,
    _render_manual_connections,
    _render_matching_connections,
    _render_planned_chain_connections,
)
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Line
from schematika.electrical.system.system import Circuit

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ZERO_DIR = Vector(dx=0.0, dy=0.0)


def _make_port(port_id: str, x: float, y: float) -> Port:
    return Port(id=port_id, position=Point(x, y), direction=_ZERO_DIR)


def _make_symbol(*ports: tuple[str, float, float]) -> Symbol:
    port_map = {
        pid: Port(id=pid, position=Point(x, y), direction=_ZERO_DIR)
        for pid, x, y in ports
    }
    return Symbol(elements=[], ports=port_map)


def _make_rc(
    *,
    pins: tuple[str, ...] = (),
    symbol: Symbol | None = None,
    wire_labels_above: list[str] | None = None,
    tag: str = "X1",
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    spec = ComponentSpec(
        func=None,
        kind="symbol",
        pins=pins if pins else None,
        wire_labels_above=wire_labels_above,
        kwargs=kwargs,
    )
    rc = RealizedComponent(spec=spec, tag=tag, pins=pins, y=0.0)
    d = realized_to_dict(rc)
    if symbol is not None:
        d["symbol"] = symbol
    return d


# ---------------------------------------------------------------------------
# _get_endpoint_symbols — parametrized table
# ---------------------------------------------------------------------------


def _two_rc_list() -> list[dict[str, Any]]:
    sym_a = _make_symbol(("1", 0.0, 0.0))
    sym_b = _make_symbol(("2", 10.0, 0.0))
    return [_make_rc(symbol=sym_a, tag="A"), _make_rc(symbol=sym_b, tag="B")]


@pytest.mark.parametrize(
    ("idx_a", "idx_b", "comp_a_has_symbol", "comp_b_has_symbol", "expect_none"),
    [
        pytest.param(0, 1, True, True, False, id="both-valid"),
        pytest.param(2, 1, True, True, True, id="idx_a-oob"),
        pytest.param(0, 2, True, True, True, id="idx_b-oob"),
        pytest.param(0, 1, False, True, True, id="comp_a-no-symbol"),
        pytest.param(0, 1, True, False, True, id="comp_b-no-symbol"),
    ],
)
def test_get_endpoint_symbols(
    idx_a, idx_b, comp_a_has_symbol, comp_b_has_symbol, expect_none
):
    rcs = _two_rc_list()
    # Selectively remove "symbol" keys to simulate missing symbols
    if not comp_a_has_symbol and len(rcs) > 0:
        rcs[0].pop("symbol", None)
    if not comp_b_has_symbol and len(rcs) > 1:
        rcs[1].pop("symbol", None)

    result = _get_endpoint_symbols(rcs, idx_a, idx_b)

    if expect_none:
        assert result is None
    else:
        assert result is not None
        sym_a, sym_b = result
        assert isinstance(sym_a, Symbol)
        assert isinstance(sym_b, Symbol)


# ---------------------------------------------------------------------------
# _render_manual_connections
# ---------------------------------------------------------------------------


def test_render_manual_connections_direct_line():
    sym_a = _make_symbol(("1", 0.0, 0.0))
    sym_b = _make_symbol(("1", 10.0, 0.0))
    rcs = [
        _make_rc(symbol=sym_a, pins=("1",), tag="A"),
        _make_rc(symbol=sym_b, pins=("1",), tag="B"),
    ]
    c = Circuit()
    style = standard_style()
    manual = [(0, 0, 1, 0, "bottom", "top")]
    _render_manual_connections(c, rcs, manual, {}, style)
    lines = [e for e in c.elements if isinstance(e, Line)]
    assert len(lines) == 1
    assert lines[0].start == Point(0.0, 0.0)
    assert lines[0].end == Point(10.0, 0.0)


def test_render_manual_connections_vertical_wire_label():
    # Vertical line: both ports share same X → label should be appended
    sym_a = _make_symbol(("1", 5.0, 0.0))
    sym_b = _make_symbol(("1", 5.0, 20.0))
    rcs = [
        _make_rc(symbol=sym_a, pins=("1",), tag="A"),
        _make_rc(symbol=sym_b, pins=("1",), tag="B"),
    ]
    c = Circuit()
    style = standard_style()
    manual = [(0, 0, 1, 0, "bottom", "top")]
    connection_wire_labels = {0: "L1"}
    _render_manual_connections(c, rcs, manual, connection_wire_labels, style)
    # Should have 1 Line + 1 wire label text element
    lines = [e for e in c.elements if isinstance(e, Line)]
    non_lines = [e for e in c.elements if not isinstance(e, Line)]
    assert len(lines) == 1
    assert len(non_lines) == 1  # the wire label text element


def test_render_manual_connections_horizontal_no_label():
    # Horizontal line: X differs → label NOT appended even if provided
    sym_a = _make_symbol(("1", 0.0, 10.0))
    sym_b = _make_symbol(("1", 50.0, 10.0))
    rcs = [
        _make_rc(symbol=sym_a, pins=("1",), tag="A"),
        _make_rc(symbol=sym_b, pins=("1",), tag="B"),
    ]
    c = Circuit()
    style = standard_style()
    manual = [(0, 0, 1, 0, "bottom", "top")]
    connection_wire_labels = {0: "L2"}
    _render_manual_connections(c, rcs, manual, connection_wire_labels, style)
    lines = [e for e in c.elements if isinstance(e, Line)]
    non_lines = [e for e in c.elements if not isinstance(e, Line)]
    assert len(lines) == 1
    assert len(non_lines) == 0  # no label for horizontal


# ---------------------------------------------------------------------------
# _render_matching_connections
# ---------------------------------------------------------------------------


def test_render_matching_connections_common_pins():
    # Two components sharing pins "A" and "B"
    sym_a = _make_symbol(("A", 0.0, 0.0), ("B", 0.0, 5.0))
    sym_b = _make_symbol(("A", 10.0, 0.0), ("B", 10.0, 5.0))
    rcs = [
        _make_rc(symbol=sym_a, pins=("A", "B"), tag="X1"),
        _make_rc(symbol=sym_b, pins=("A", "B"), tag="X2"),
    ]
    c = Circuit()
    style = standard_style()
    matching = [(0, 1, None, "right", "left")]
    _render_matching_connections(c, rcs, matching, style)
    lines = [e for e in c.elements if isinstance(e, Line)]
    assert len(lines) == 2


def test_render_matching_connections_with_pin_filter():
    sym_a = _make_symbol(("A", 0.0, 0.0), ("B", 0.0, 5.0))
    sym_b = _make_symbol(("A", 10.0, 0.0), ("B", 10.0, 5.0))
    rcs = [
        _make_rc(symbol=sym_a, pins=("A", "B"), tag="X1"),
        _make_rc(symbol=sym_b, pins=("A", "B"), tag="X2"),
    ]
    c = Circuit()
    style = standard_style()
    matching: list[tuple[int, int, list[str] | None, str, str]] = [
        (0, 1, ["A"], "right", "left")
    ]
    _render_matching_connections(c, rcs, matching, style)
    lines = [e for e in c.elements if isinstance(e, Line)]
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# _render_planned_chain_connections
# ---------------------------------------------------------------------------


def test_render_planned_chain_no_labels():
    # Two symbols reachable via draw_wire; kind="chain", no labels
    from schematika.electrical.symbols.contacts import no_contact

    sym_a = no_contact("K1")
    sym_b = no_contact("K2")
    rcs = [
        _make_rc(symbol=sym_a, tag="K1"),
        _make_rc(symbol=sym_b, tag="K2"),
    ]
    c = Circuit()
    planned = [PlannedConnection(source_idx=0, target_idx=1, kind="chain")]
    _render_planned_chain_connections(c, rcs, planned, has_per_connection_labels=False)
    # draw_wire should produce at least one element
    assert len(c.elements) >= 1


def test_render_planned_chain_skips_non_chain():
    from schematika.electrical.symbols.contacts import no_contact

    sym_a = no_contact("K1")
    sym_b = no_contact("K2")
    rcs = [
        _make_rc(symbol=sym_a, tag="K1"),
        _make_rc(symbol=sym_b, tag="K2"),
    ]
    c = Circuit()
    planned = [PlannedConnection(source_idx=0, target_idx=1, kind="manual")]
    _render_planned_chain_connections(c, rcs, planned, has_per_connection_labels=False)
    # Non-chain entries are skipped; nothing added
    assert len(c.elements) == 0


def test_render_planned_chain_with_wire_labels_above():
    from schematika.electrical.symbols.contacts import no_contact

    sym_a = no_contact("K1")
    sym_b = no_contact("K2")
    rcs_b = _make_rc(symbol=sym_b, tag="K2", wire_labels_above=["N1"])
    rcs = [_make_rc(symbol=sym_a, tag="K1"), rcs_b]
    c = Circuit()
    planned = [PlannedConnection(source_idx=0, target_idx=1, kind="chain")]
    _render_planned_chain_connections(c, rcs, planned, has_per_connection_labels=True)
    # Lines plus wire label text element(s)
    non_lines = [e for e in c.elements if not isinstance(e, Line)]
    assert len(non_lines) >= 1
