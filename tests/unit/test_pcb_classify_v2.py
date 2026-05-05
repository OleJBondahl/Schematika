"""Tests for v2 net classification with power-alias matching."""

from types import SimpleNamespace

from schematika.pcb.classify import NetKind, classify_net
from schematika.pcb.model import PowerNetMap
from schematika.pcb.symbols.power import power_24v


def _power_24v_map() -> PowerNetMap:
    return PowerNetMap(
        canonical_name="+24V",
        symbol=power_24v,
        aliases=("/v24", "/V24"),
    )


def test_chain_when_two_pins_and_no_power_match() -> None:
    net = SimpleNamespace(name="/PWR_IN", pins=[object(), object()])
    assert classify_net(net, power_nets=()) is NetKind.CHAIN


def test_dropped_when_zero_or_one_pin() -> None:
    assert (
        classify_net(SimpleNamespace(name="/foo", pins=[]), power_nets=())
        is NetKind.DROPPED
    )
    assert (
        classify_net(SimpleNamespace(name="/foo", pins=[object()]), power_nets=())
        is NetKind.DROPPED
    )


def test_label_when_three_or_more_pins_no_power_match() -> None:
    net = SimpleNamespace(name="/em_stop_chain", pins=[object(), object(), object()])
    assert classify_net(net, power_nets=()) is NetKind.LABEL


def test_power_match_overrides_pin_count_two() -> None:
    pmap = _power_24v_map()
    net = SimpleNamespace(name="/v24", pins=[object(), object()])
    assert classify_net(net, power_nets=(pmap,)) is NetKind.POWER


def test_power_match_alias_with_or_without_leading_slash() -> None:
    pmap = _power_24v_map()
    for nm in ("/v24", "v24", "/V24", "+24V"):
        net = SimpleNamespace(name=nm, pins=[object(), object(), object()])
        assert classify_net(net, power_nets=(pmap,)) is NetKind.POWER
