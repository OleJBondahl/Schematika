"""Tests for the Harness builder, Plc request, and PLC resolution."""

import dataclasses

import pytest

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.harness import (
    Harness,
    HarnessBuildResult,
    Plc,
    PlcAssignment,
    _allocate_plc,
    _PlcRequest,
)
from schematika.electrical.plc_resolver import PlcModuleType


def test_plc_request_fields_and_default_suffix():
    assert Plc(signal_type="DI").suffix == ""
    rtd = Plc(signal_type="RTD", suffix="+R")
    assert rtd.signal_type == "RTD"
    assert rtd.suffix == "+R"


def test_plc_assignment_fields():
    src = PinRef(device=DeviceTag("TT-101"), port_id="1")
    a = PlcAssignment(
        module="DI1",
        mpn="DI16",
        channel=3,
        signal_type="DI",
        pin_label="3",
        source=src,
        net=NetId("TT-101_1"),
    )
    assert a.module == "DI1"
    assert a.channel == 3
    assert a.source is src


def test_harness_build_result_frozen():
    result = HarnessBuildResult(wires=(), plc_assignments=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.wires = ()  # ty: ignore[invalid-assignment]


def _di_rack(channels=2):
    return [
        (
            "DI1",
            PlcModuleType(
                mpn="DI16", signal_type="DI", channels=channels, pins_per_channel=("",)
            ),
        )
    ]


def _req(signal_type, suffix, term_dev, term_pin, src_dev, idx):
    return _PlcRequest(
        signal_type=signal_type,
        suffix=suffix,
        terminal_sort=(term_dev, term_pin),
        source_device=src_dev,
        key=idx,
    )


def test_allocate_single_pin_sequential():
    reqs = [_req("DI", "", "X1", "2", "B", 0), _req("DI", "", "X1", "1", "A", 1)]
    resolved = _allocate_plc(reqs, _di_rack(channels=2))
    # sorted by terminal pin: "1" (key 1) gets channel 1, "2" (key 0) gets channel 2
    assert resolved[1].channel == 1
    assert resolved[1].pin_label == "1"
    assert resolved[0].channel == 2
    assert resolved[1].designation == "DI1"
    assert resolved[1].mpn == "DI16"


def test_allocate_multi_pin_rtd_shares_channel():
    rack = [
        (
            "RTD1",
            PlcModuleType(
                mpn="RTD8",
                signal_type="RTD",
                channels=4,
                pins_per_channel=("+R", "RL", "-R"),
            ),
        )
    ]
    reqs = [
        _req("RTD", "+R", "X1", "1", "TT1", 0),
        _req("RTD", "RL", "X1", "2", "TT1", 1),
        _req("RTD", "-R", "X1", "3", "TT1", 2),
    ]
    resolved = _allocate_plc(reqs, rack)
    assert {r.channel for r in resolved} == {1}  # one device -> one channel
    assert {r.pin_label for r in resolved} == {"+R1", "RL1", "-R1"}


def test_allocate_overflow_warns_and_truncates():
    reqs = [_req("DI", "", "X1", str(i), chr(65 + i), i) for i in range(3)]
    with pytest.warns(UserWarning, match="not enough free PLC channels"):
        resolved = _allocate_plc(reqs, _di_rack(channels=2))
    assert len(resolved) == 2  # only 2 channels


def test_allocate_unknown_type_returns_empty():
    reqs = [_req("AI", "", "X1", "1", "A", 0)]
    assert _allocate_plc(reqs, _di_rack()) == []


def _pin(dev, port):
    return PinRef(device=DeviceTag(dev), port_id=port)


def test_route_rejects_fewer_than_two_waypoints():
    h = Harness(rack=[])
    with pytest.raises(CircuitValidationError):
        h.route(_pin("-M1", "U"))


def test_route_collects_declarations():
    h = Harness(rack=[])
    h.route(_pin("-M1", "U"), _pin("X1", "1"))
    h.route(_pin("-M2", "V"), _pin("X1", "2"))
    assert len(h._routes) == 2
