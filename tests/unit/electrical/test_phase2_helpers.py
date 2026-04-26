"""Characterisation tests for the 4 phase-2 helpers extracted in wave C1b."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from schematika.electrical import create_initial_state
from schematika.electrical.builder_models import (
    ComponentSpec,
    RealizedComponent,
    realized_to_dict,
)
from schematika.electrical.builder_phases import (
    _register_connection_pair,
    _register_linear_connections,
    _register_manual_connections,
    _should_auto_connect,
)

if TYPE_CHECKING:
    from schematika.electrical.model.constants import Side

# ---------------------------------------------------------------------------
# Helpers for building minimal realized-component dicts
# ---------------------------------------------------------------------------


def _make_comp(
    kind: str,
    tag: str = "X1",
    pins: tuple[str, ...] = (),
    *,
    connect_to_next: bool = True,
    placed_right_of: int | None = None,
    placed_above_of: tuple | None = None,
    placed_below_of: tuple | None = None,
    connection_side: Side | None = None,
    poles: int = 1,
) -> dict[str, Any]:
    spec = ComponentSpec(
        func=None,
        kind=kind,
        poles=poles,
        connect_to_next=connect_to_next,
        placed_right_of=placed_right_of,
        placed_above_of=placed_above_of,
        placed_below_of=placed_below_of,
        connection_side=connection_side,
        pins=pins if pins else None,
    )
    rc = RealizedComponent(spec=spec, tag=tag, pins=pins, y=0.0)
    return realized_to_dict(rc)


# ---------------------------------------------------------------------------
# _should_auto_connect
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("connect_to_next", "right", "above", "below", "expected"),
    [
        # connect_to_next=False -> always False
        (False, None, None, None, False),
        (False, 0, None, None, False),
        # connect_to_next=True, no placement -> True
        (True, None, None, None, True),
        # connect_to_next=True, placed_right_of set -> False
        (True, 0, None, None, False),
        # connect_to_next=True, placed_above_of set -> False
        (True, None, (0, "top"), None, False),
        # connect_to_next=True, placed_below_of set -> False
        (True, None, None, (0, "bottom"), False),
    ],
)
def test_should_auto_connect(connect_to_next, right, above, below, expected):
    curr = _make_comp("symbol", connect_to_next=connect_to_next)
    next_comp = _make_comp(
        "symbol",
        placed_right_of=right,
        placed_above_of=above,
        placed_below_of=below,
    )
    assert _should_auto_connect(curr, next_comp) == expected


# ---------------------------------------------------------------------------
# _register_connection_pair -- 5 arms + no-op fall-through
# ---------------------------------------------------------------------------


@pytest.fixture
def state():
    return create_initial_state()


@pytest.mark.parametrize(
    ("kind_from", "kind_to", "pins_from", "pins_to", "expect_wire", "should_mutate"),
    [
        # terminal x symbol -> wire with registry pin from comp_from, mutates
        ("terminal", "symbol", ("T1",), (), True, True),
        # terminal x reference -> wire with registry pin from comp_from, mutates
        ("terminal", "reference", ("T1",), (), True, True),
        # symbol x terminal -> wire with registry pin from comp_to, mutates
        ("symbol", "terminal", (), ("T2",), True, True),
        # reference x terminal -> wire with registry pin from comp_to, mutates
        ("reference", "terminal", (), ("T2",), True, True),
        # reference x symbol, comp_from has pins -> uses existing pin, mutates
        ("reference", "symbol", ("R1",), (), True, True),
        # reference x symbol, comp_from has NO pins -> allocates, mutates
        ("reference", "symbol", (), (), True, True),
        # symbol x reference, comp_to has pins -> uses existing pin, mutates
        ("symbol", "reference", (), ("R2",), True, True),
        # symbol x reference, comp_to has NO pins -> allocates, mutates
        ("symbol", "reference", (), (), True, True),
        # symbol x symbol -> plain wire, no log_connection, no mutation
        ("symbol", "symbol", (), (), True, False),
        # terminal x terminal -> no-op (None), no mutation
        ("terminal", "terminal", ("T1",), ("T2",), False, False),
    ],
)
def test_register_connection_pair_arms(
    state, kind_from, kind_to, pins_from, pins_to, expect_wire, should_mutate
):
    comp_from = _make_comp(kind_from, tag="A1", pins=pins_from)
    comp_to = _make_comp(kind_to, tag="B1", pins=pins_to)
    state_before = state
    state_after, wire = _register_connection_pair(
        state,
        comp_from,
        "pin_a",
        None,
        0,
        comp_to,
        "pin_b",
        None,
        0,
    )
    if expect_wire:
        assert wire is not None
        assert len(wire) == 4
        assert wire[0] == "A1"
        assert wire[2] == "B1"
    else:
        assert wire is None
    # Verify state mutation for arms that call log_connection
    if should_mutate:
        assert state_after != state_before
    else:
        assert state_after is state_before


def test_register_connection_pair_ref_sym_uses_existing_pin(state):
    """reference x symbol: when comp_from has pins, the first pin is used in the wire."""
    comp_from = _make_comp("reference", tag="REF1", pins=("existing_pin",))
    comp_to = _make_comp("symbol", tag="SYM1")
    _, wire = _register_connection_pair(
        state, comp_from, "p_from", None, 0, comp_to, "p_to", None, 0
    )
    assert wire is not None
    assert wire[1] == "existing_pin"


def test_register_connection_pair_ref_sym_allocates_when_no_pins(state):
    """reference x symbol: when comp_from has no pins, a new pin is allocated."""
    comp_from = _make_comp("reference", tag="REF2", pins=())
    comp_to = _make_comp("symbol", tag="SYM2")
    _, wire = _register_connection_pair(
        state, comp_from, "p_from", None, 0, comp_to, "p_to", None, 0
    )
    assert wire is not None
    # Allocated pin should not be empty
    assert wire[1]


# ---------------------------------------------------------------------------
# _register_linear_connections -- smoke test
# ---------------------------------------------------------------------------


def test_register_linear_connections_basic(state):
    comp_a = _make_comp("symbol", tag="K1", pins=("1",), connect_to_next=True)
    comp_b = _make_comp("symbol", tag="K2", pins=("2",), connect_to_next=False)
    _, wires = _register_linear_connections(state, [comp_a, comp_b])
    assert len(wires) == 1
    assert wires[0] == ("K1", "1", "K2", "2")


def test_register_linear_connections_no_connect(state):
    comp_a = _make_comp("symbol", tag="K1", connect_to_next=False)
    comp_b = _make_comp("symbol", tag="K2")
    _, wires = _register_linear_connections(state, [comp_a, comp_b])
    assert wires == []


def test_register_linear_connections_skips_placed_right(state):
    comp_a = _make_comp("symbol", tag="K1", connect_to_next=True)
    comp_b = _make_comp("symbol", tag="K2", placed_right_of=0)
    _, wires = _register_linear_connections(state, [comp_a, comp_b])
    assert wires == []


def test_linear_reference_to_symbol_honours_existing_pins(state):
    """reference x symbol in linear loop uses pre-set pins from reference component."""
    ref_comp = _make_comp("reference", tag="REF1", pins=("X1",), connect_to_next=True)
    sym_comp = _make_comp("symbol", tag="SYM1", pins=(), connect_to_next=False)
    _, wires = _register_linear_connections(state, [ref_comp, sym_comp])
    assert len(wires) == 1
    wire = wires[0]
    assert wire[0] == "REF1"
    assert wire[1] == "X1"  # User-supplied pin, not freshly allocated
    assert wire[2] == "SYM1"
    assert wire[3]  # sym_comp's output pin (concrete value varies)


# ---------------------------------------------------------------------------
# _register_manual_connections -- smoke test
# ---------------------------------------------------------------------------


def test_register_manual_connections_basic(state):
    comp_a = _make_comp("symbol", tag="K1", pins=("out",))
    comp_b = _make_comp("symbol", tag="K2", pins=("in",))
    manual = [(0, 0, 1, 0, "bottom", "top")]
    _, wires = _register_manual_connections(state, [comp_a, comp_b], manual)
    assert len(wires) == 1
    assert wires[0][0] == "K1"
    assert wires[0][2] == "K2"


def test_register_manual_connections_out_of_range(state):
    comp_a = _make_comp("symbol", tag="K1")
    manual = [(0, 0, 5, 0, "bottom", "top")]  # idx_b=5 out of range
    _, wires = _register_manual_connections(state, [comp_a], manual)
    assert wires == []
