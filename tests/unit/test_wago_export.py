"""Tests for the WAGO PFC IOServer <Modules> XML export."""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET

import pytest

from schematika.electrical.field_devices import (
    AnalogScaling,
    DeviceTemplate,
    FieldDevice,
    PinDef,
)
from schematika.electrical.plc_resolver import PlcModuleType
from schematika.electrical.wago_export import render_wago_modules_xml

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


# ---------------------------------------------------------------------------
# Renderer — sample module types mirroring the consumer rack
# ---------------------------------------------------------------------------

RTD_MODULE = PlcModuleType("750-461", "RTD", 2, ("+R", "RL", "-R"))
MA_MODULE = PlcModuleType("750-455", "4-20mA", 4, ("Sig", "GND"))
DI_MODULE = PlcModuleType("750-1405", "DI", 8, ("",))
DO_MODULE = PlcModuleType("750-530", "DO", 8, ("",))
RELAY_MODULE = PlcModuleType(
    "750-515", "RELAY", 4, ("3", "4"), label_format="{channel}{suffix}"
)


def _channels(xml: str, module_index: int = 0) -> list[ET.Element]:
    root = ET.fromstring(xml)
    return list(root[module_index].findall("Channel"))


class TestRenderDigital:
    def test_empty_rack(self):
        xml = render_wago_modules_xml([], rows=[])
        root = ET.fromstring(xml)
        assert root.tag == "Modules"
        assert len(root) == 0

    def test_spare_di_module(self):
        xml = render_wago_modules_xml([("DI1", DI_MODULE)], rows=[])
        root = ET.fromstring(xml)
        module = root[0]
        assert module.get("Model") == "WagoIOModules.IOModule"
        assert module.get("Name") == "750-1405_8DI_a"
        channels = _channels(xml)
        assert len(channels) == 8
        first = channels[0]
        assert first.get("Input") == "0"
        assert first.get("Model") == "CDPSignalChannel<bool>"
        assert first.get("Name") == "DI1_0"
        assert first.get("NetworkConvert") == "1"
        assert first.get("Nr") == "0"
        assert first.get("Type") == "bool"
        assert first.get("Value") == "0"
        assert first.get("Description") == "Digital input channel"
        assert channels[7].get("Nr") == "7"

    def test_model_attribute_is_escaped_in_raw_text(self):
        xml = render_wago_modules_xml([("DI1", DI_MODULE)], rows=[])
        assert "CDPSignalChannel&lt;bool&gt;" in xml
        assert "CDPSignalChannel<bool>" not in xml

    def test_do_and_relay_are_outputs(self):
        rack = [("DO1", DO_MODULE), ("Relay1", RELAY_MODULE)]
        xml = render_wago_modules_xml(rack, rows=[])
        assert all(c.get("Input") == "1" for c in _channels(xml, 0))
        assert all(c.get("Input") == "1" for c in _channels(xml, 1))
        do_first = _channels(xml, 0)[0]
        assert do_first.get("Type") == "bool"
        assert do_first.get("Description") == "Digital output channel"
        assert len(_channels(xml, 1)) == 4  # relay: 4 channels, not 8 pin rows

    def test_wired_channel_with_function_suffix(self):
        tmpl = DeviceTemplate(
            mpn="Level Switch",
            pins=(PinDef("1", function_suffix="LevelSw"), PinDef(device_pin="2")),
        )
        dev = FieldDevice(tag="LS-01", template=tmpl)
        rows = [("DI1", "750-1405", "3", "LS-01", "1", "X16:1")]
        xml = render_wago_modules_xml([("DI1", DI_MODULE)], rows=rows, devices=[dev])
        channels = _channels(xml)
        assert channels[2].get("Name") == "LS-01-LevelSw"
        assert channels[1].get("Name") == "DI1_1"  # neighbours stay spare

    def test_wired_channel_without_suffix_falls_back_to_component_pin(self):
        rows = [("DO1", "750-530", "1", "K3", "14", "")]
        xml = render_wago_modules_xml([("DO1", DO_MODULE)], rows=rows)
        assert _channels(xml)[0].get("Name") == "K3-14"

    def test_module_name_letter_increments_per_repeated_mpn(self):
        rack = [("DI1", DI_MODULE), ("DO1", DO_MODULE), ("DI2", DI_MODULE)]
        xml = render_wago_modules_xml(rack, rows=[])
        root = ET.fromstring(xml)
        names = [m.get("Name") for m in root]
        assert names == ["750-1405_8DI_a", "750-530_8DO_a", "750-1405_8DI_b"]

    def test_descriptions_applied_and_missing_is_empty(self):
        rack = [("DI1", DI_MODULE), ("DO1", DO_MODULE)]
        xml = render_wago_modules_xml(
            rack,
            rows=[],
            descriptions={"750-1405": "8-channel digital input; 24 VDC; 3 ms"},
        )
        root = ET.fromstring(xml)
        assert root[0].get("Description") == "8-channel digital input; 24 VDC; 3 ms"
        assert root[1].get("Description") == ""
