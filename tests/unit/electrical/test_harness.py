"""Tests for the Harness builder, Plc request, and PLC resolution."""

import dataclasses

import pytest

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.electrical.harness import (
    HarnessBuildResult,
    Plc,
    PlcAssignment,
)


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
