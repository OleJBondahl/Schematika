"""Characterisation tests for the 4 phase-3 helpers extracted in wave C1c."""

from __future__ import annotations

from typing import Any

import pytest

from schematika.core.exceptions import CircuitValidationError
from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.electrical.builder_models import (
    ComponentSpec,
    RealizedComponent,
    realized_to_dict,
)
from schematika.electrical.builder_phases import (
    _compute_above_or_below_position,
    _compute_placed_right_position,
    _make_factory_symbol,
    _make_terminal_symbol,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_ZERO_DIR = Vector(dx=0.0, dy=0.0)


def _make_port(x: float, y: float) -> Port:
    return Port(id="1", position=Point(x, y), direction=_ZERO_DIR)


def _make_symbol_with_port(port_key: str, x: float, y: float) -> Symbol:
    port = Port(id=port_key, position=Point(x, y), direction=_ZERO_DIR)
    return Symbol(elements=[], ports={port_key: port})


def _make_rc(
    kind: str = "symbol",
    *,
    placed_above_of: tuple | None = None,
    placed_below_of: tuple | None = None,
    placed_right_of: int | None = None,
    x_offset: float = 0.0,
    y_increment: float | None = None,
    poles: int = 1,
    pins: tuple[str, ...] = (),
    tag: str = "X1",
    symbol: Symbol | None = None,
    kwargs: dict | None = None,
) -> dict[str, Any]:
    spec = ComponentSpec(
        func=None,
        kind=kind,
        poles=poles,
        placed_above_of=placed_above_of,
        placed_below_of=placed_below_of,
        placed_right_of=placed_right_of,
        x_offset=x_offset,
        y_increment=y_increment,
        pins=pins if pins else None,
        kwargs=kwargs or {},
    )
    rc = RealizedComponent(spec=spec, tag=tag, pins=pins, y=0.0)
    d = realized_to_dict(rc)
    if symbol is not None:
        d["symbol"] = symbol
    return d


# ---------------------------------------------------------------------------
# _compute_above_or_below_position
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "sign"),
    [
        ("above", -1),
        ("below", +1),
    ],
)
@pytest.mark.parametrize(
    ("y_increment", "layout_spacing", "expected_offset"),
    [
        pytest.param(10.0, 50.0, 10.0, id="explicit-y_increment"),
        pytest.param(None, 50.0, 25.0, id="default-half-spacing"),
    ],
)
def test_compute_above_or_below_position(
    mode, sign, y_increment, layout_spacing, expected_offset
):
    ref_sym = _make_symbol_with_port("top", x=100.0, y=200.0)
    ref_rc = _make_rc(symbol=ref_sym)

    if mode == "above":
        comp_spec_kwargs = {"placed_above_of": (0, "top")}
    else:
        comp_spec_kwargs = {"placed_below_of": (0, "top")}

    component_spec = ComponentSpec(
        func=None,
        kind="symbol",
        placed_above_of=comp_spec_kwargs.get("placed_above_of"),
        placed_below_of=comp_spec_kwargs.get("placed_below_of"),
        y_increment=y_increment,
    )

    realized_components = [ref_rc]
    final_x, new_y = _compute_above_or_below_position(
        component_spec, realized_components, layout_spacing
    )

    assert final_x == pytest.approx(100.0)  # port.x + x_offset(0)
    assert new_y == pytest.approx(200.0 + sign * expected_offset)


def test_compute_above_or_below_position_raises_for_missing_port():
    ref_sym = _make_symbol_with_port("top", x=0.0, y=0.0)
    ref_rc = _make_rc(symbol=ref_sym)
    component_spec = ComponentSpec(
        func=None,
        kind="symbol",
        placed_above_of=(0, "nonexistent_port"),
    )
    with pytest.raises(CircuitValidationError):
        _compute_above_or_below_position(component_spec, [ref_rc], layout_spacing=50.0)


# ---------------------------------------------------------------------------
# _compute_placed_right_position
# ---------------------------------------------------------------------------


def test_compute_placed_right_position_direct():
    # rc[0] has x_offset=30, no placed_right_of chain
    ref_rc = _make_rc(x_offset=30.0, placed_right_of=None)
    component_spec = ComponentSpec(
        func=None,
        kind="symbol",
        placed_right_of=0,
        x_offset=10.0,
    )
    final_x = _compute_placed_right_position(component_spec, [ref_rc], x=100.0)
    # x + ref_x_offset + component_spec.x_offset = 100 + 30 + 10 = 140
    assert final_x == pytest.approx(140.0)


def test_compute_placed_right_position_chained():
    # rc[0]: x_offset=20, no chain
    # rc[1]: placed_right_of=0, x_offset=15  → absolute = 20+15 = 35
    # component: placed_right_of=1, x_offset=5 → final = x + 35 + 5 = 140
    rc0 = _make_rc(x_offset=20.0, placed_right_of=None)
    rc1 = _make_rc(x_offset=15.0, placed_right_of=0)
    component_spec = ComponentSpec(
        func=None,
        kind="symbol",
        placed_right_of=1,
        x_offset=5.0,
    )
    final_x = _compute_placed_right_position(component_spec, [rc0, rc1], x=100.0)
    assert final_x == pytest.approx(140.0)


# ---------------------------------------------------------------------------
# _make_terminal_symbol
# ---------------------------------------------------------------------------


def test_make_terminal_symbol_single_pole():
    component_spec = ComponentSpec(
        func=None,
        kind="terminal",
        poles=1,
        kwargs={"tm_id": 1, "label_pos": "right"},
    )
    rc = _make_rc(kind="terminal", poles=1, pins=("X1",), tag="1")
    sym = _make_terminal_symbol("1", rc, component_spec)
    assert isinstance(sym, Symbol)
    # single-pole terminal has 4 ports (numeric IDs + semantic aliases)
    assert len(sym.ports) == 4


def test_make_terminal_symbol_multi_pole():
    component_spec = ComponentSpec(
        func=None,
        kind="terminal",
        poles=3,
        kwargs={"tm_id": 1},
    )
    rc = _make_rc(kind="terminal", poles=3, pins=("X1", "X2", "X3"), tag="1")
    sym = _make_terminal_symbol("1", rc, component_spec)
    assert isinstance(sym, Symbol)
    # multi-pole terminal has 2 * poles ports
    assert len(sym.ports) == 6


# ---------------------------------------------------------------------------
# _make_factory_symbol
# ---------------------------------------------------------------------------


def _dummy_factory(tag: str, *, label: str = "") -> Symbol:
    """Minimal factory for testing; no pins, no poles."""
    return Symbol(elements=[], ports={}, label=tag)


def _poles_aware_factory(tag: str, *, poles: int = 1) -> Symbol:
    """Factory that accepts poles — should receive it via inspect forwarding."""
    port = Port(id="out", position=Point(0.0, 0.0), direction=_ZERO_DIR)
    return Symbol(elements=[], ports={"out": port}, label=f"{tag}-p{poles}")


def test_make_factory_symbol_basic():
    component_spec = ComponentSpec(
        func=_dummy_factory,
        kind="symbol",
        tag_prefix="K",
        kwargs={"label": "test"},
    )
    rc = _make_rc(kind="symbol", tag="K1")
    sym = _make_factory_symbol("K1", rc, component_spec)
    assert isinstance(sym, Symbol)
    assert sym.label == "K1"


def test_make_factory_symbol_poles_forwarded_via_inspect():
    component_spec = ComponentSpec(
        func=_poles_aware_factory,
        kind="symbol",
        tag_prefix="K",
        poles=3,
        kwargs={},
    )
    rc = _make_rc(kind="symbol", tag="K1", poles=3)
    sym = _make_factory_symbol("K1", rc, component_spec)
    assert isinstance(sym, Symbol)
    # poles was forwarded → label reflects it
    assert sym.label == "K1-p3"
