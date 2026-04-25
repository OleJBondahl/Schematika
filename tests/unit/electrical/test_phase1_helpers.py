"""Characterisation tests for the 5 phase-1 helpers extracted in wave C1a."""

from __future__ import annotations

import pytest

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical import create_initial_state
from schematika.electrical.builder_models import ComponentSpec
from schematika.electrical.builder_phases import (
    _compute_component_y,
    _resolve_symbol_or_reference_tag,
    _resolve_terminal_id,
    _resolve_terminal_pins,
    _track_pin_accumulator,
)


def _terminal_spec(
    tm_id: str | int = 1, logical_name: str | None = None
) -> ComponentSpec:
    kwargs: dict = {"tm_id": tm_id}
    if logical_name is not None:
        kwargs["logical_name"] = logical_name
    return ComponentSpec(func=None, kind="terminal", kwargs=kwargs)


def _symbol_spec(tag_prefix: str | None = "K") -> ComponentSpec:
    return ComponentSpec(func=None, kind="symbol", tag_prefix=tag_prefix)


# ---------------------------------------------------------------------------
# _resolve_terminal_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("terminal_maps", "spec_terminal_map", "expected"),
    [
        # 1. runtime override wins
        ({"L1": 99}, {"L1": 50}, 99),
        # 2. spec map fallback
        (None, {"L1": 50}, 50),
        # 3. kwargs fallback (no maps provide an override)
        (None, {}, 1),
    ],
)
def test_resolve_terminal_id(terminal_maps, spec_terminal_map, expected):
    spec = _terminal_spec(tm_id=1, logical_name="L1")
    result = _resolve_terminal_id(spec, terminal_maps, spec_terminal_map)
    assert result == expected


# ---------------------------------------------------------------------------
# _resolve_terminal_pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("explicit_pins", "reuse_generators", "expected_pins"),
    [
        # 1. explicit pins win
        (["X1", "X2"], None, ["X1", "X2"]),
        # 2. reuse generator (lname key)
        (None, {"lname_key": lambda s, poles: (s, ("R1", "R2"))}, ["R1", "R2"]),
        # 3. fresh allocation from next_terminal_pins
        (None, None, None),  # just check it doesn't raise; pins are non-empty strings
    ],
)
def test_resolve_terminal_pins(explicit_pins, reuse_generators, expected_pins):
    state = create_initial_state()
    spec = ComponentSpec(
        func=None,
        kind="terminal",
        kwargs={"tm_id": 1},
        poles=2,
        pins=explicit_pins,
    )
    _, pins = _resolve_terminal_pins(
        state,
        spec,
        tid=1,
        lname="lname_key",
        terminal_reuse_generators=reuse_generators,
    )
    if expected_pins is not None:
        assert pins == expected_pins
    else:
        # fresh allocation: must yield non-empty pin strings
        assert len(pins) == 2
        assert all(isinstance(p, str) for p in pins)


# ---------------------------------------------------------------------------
# _track_pin_accumulator
# ---------------------------------------------------------------------------


def test_track_pin_accumulator_extends():
    acc: dict = {}
    _track_pin_accumulator(acc, lname="L1", tid=1, pins=["X1", "X2"])
    assert acc == {"L1": ["X1", "X2"]}
    _track_pin_accumulator(acc, lname="L1", tid=1, pins=["X3"])
    assert acc == {"L1": ["X1", "X2", "X3"]}


def test_track_pin_accumulator_none_is_noop():
    _track_pin_accumulator(None, lname="L1", tid=1, pins=["X1"])
    # no exception, no state to check


# ---------------------------------------------------------------------------
# _resolve_symbol_or_reference_tag
# ---------------------------------------------------------------------------


def test_resolve_symbol_or_reference_tag_raises_without_prefix():
    state = create_initial_state()
    spec = _symbol_spec(tag_prefix=None)
    instance_tags: dict = {}
    with pytest.raises(CircuitValidationError):
        _resolve_symbol_or_reference_tag(
            state, spec, tag_generators=None, instance_tags=instance_tags
        )


def test_resolve_symbol_or_reference_tag_generates_tag():
    state = create_initial_state()
    spec = _symbol_spec(tag_prefix="K")
    instance_tags: dict = {}
    _, tag = _resolve_symbol_or_reference_tag(
        state, spec, tag_generators=None, instance_tags=instance_tags
    )
    assert tag.startswith("K")
    assert instance_tags["K"] == tag


# ---------------------------------------------------------------------------
# _compute_component_y
# ---------------------------------------------------------------------------


def test_compute_component_y_default_stack_advance():
    spec = ComponentSpec(func=None, kind="symbol", tag_prefix="K")
    comp_y, new_y = _compute_component_y(
        spec, current_y=0.0, realized_components=[], layout_spacing=50.0
    )
    assert comp_y == 0.0
    assert new_y == 50.0


def test_compute_component_y_placed_right_of():
    ref_dict = {
        "spec": ComponentSpec(func=None, kind="symbol"),
        "tag": "K1",
        "pins": [],
        "y": 75.0,
    }
    spec = ComponentSpec(func=None, kind="symbol", tag_prefix="K", placed_right_of=0)
    comp_y, new_y = _compute_component_y(
        spec, current_y=100.0, realized_components=[ref_dict], layout_spacing=50.0
    )
    assert comp_y == 75.0
    assert new_y == 100.0  # no stack advance


def test_compute_component_y_placed_above_or_below():
    spec = ComponentSpec(
        func=None, kind="symbol", tag_prefix="K", placed_above_of=(0, "top")
    )
    comp_y, new_y = _compute_component_y(
        spec, current_y=30.0, realized_components=[], layout_spacing=50.0
    )
    assert comp_y == 30.0
    assert new_y == 30.0  # no stack advance
