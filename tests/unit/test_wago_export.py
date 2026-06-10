"""Tests for the WAGO PFC IOServer <Modules> XML export."""

from __future__ import annotations

import dataclasses

import pytest

from schematika.electrical.field_devices import (
    AnalogScaling,
    DeviceTemplate,
    FieldDevice,
    PinDef,
)

# ---------------------------------------------------------------------------
# New data fields
# ---------------------------------------------------------------------------


class TestAnalogScaling:
    def test_fields(self):
        s = AnalogScaling(unit="bar", raw_min=0, raw_max=31987, eng_min=0, eng_max=3.6)
        assert s.unit == "bar"
        assert s.raw_max == 31987
        assert s.eng_max == 3.6

    def test_frozen(self):
        s = AnalogScaling(unit="bar", raw_min=0, raw_max=1, eng_min=0, eng_max=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.unit = "psi"  # ty: ignore[invalid-assignment]

    def test_kw_only(self):
        with pytest.raises(TypeError):
            AnalogScaling("bar", 0, 1, 0, 1)  # ty: ignore[too-many-positional-arguments, missing-argument]


class TestNewOptionalFields:
    def test_pindef_function_suffix_default_empty(self):
        assert PinDef(device_pin="1").function_suffix == ""

    def test_pindef_function_suffix_set(self):
        assert PinDef("C2", function_suffix="OpenFb").function_suffix == "OpenFb"

    def test_fielddevice_scaling_default_none(self):
        tmpl = DeviceTemplate(mpn="T", pins=(PinDef(device_pin="1"),))
        assert FieldDevice(tag="PT-01", template=tmpl).scaling is None

    def test_fielddevice_scaling_set(self):
        tmpl = DeviceTemplate(mpn="T", pins=(PinDef(device_pin="1"),))
        s = AnalogScaling(unit="bar", raw_min=0, raw_max=31987, eng_min=0, eng_max=3.6)
        dev = FieldDevice(tag="PT-01", template=tmpl, scaling=s)
        assert dev.scaling is s
