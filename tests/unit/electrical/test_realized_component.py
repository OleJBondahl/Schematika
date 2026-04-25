from dataclasses import FrozenInstanceError, replace

import pytest

from schematika.core.symbol import Symbol
from schematika.electrical.builder_models import (
    ComponentSpec,
    RealizedComponent,
    realized_from_dict,
    realized_to_dict,
)


def _spec():
    return ComponentSpec(func=None, kind="terminal")


def _symbol():
    return Symbol(elements=[], ports={})


def test_construct_with_defaults():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1", "2"), y=10.0)
    assert rc.symbol is None


def test_replace_updates_y():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1",), y=0.0)
    rc2 = replace(rc, y=5.0)
    assert rc2.y == 5.0
    assert rc.y == 0.0


def test_frozen_blocks_mutation():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1",), y=0.0)
    with pytest.raises(FrozenInstanceError):
        rc.y = 5.0  # type: ignore


def test_roundtrip_without_symbol():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1", "2"), y=10.0)
    rt = realized_from_dict(realized_to_dict(rc))
    assert rt == rc


def test_roundtrip_with_symbol():
    sym = _symbol()
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1",), y=0.0, symbol=sym)
    rt = realized_from_dict(realized_to_dict(rc))
    assert rt == rc


def test_from_dict_omits_symbol_when_absent():
    d = {"spec": _spec(), "tag": "T1", "pins": ["1", "2"], "y": 0.0}
    rc = realized_from_dict(d)
    assert rc.symbol is None
    assert rc.pins == ("1", "2")
