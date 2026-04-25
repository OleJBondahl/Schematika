"""Tests for cable CSV generation."""

import csv
import tempfile
from pathlib import Path

from schematika.electrical.cable_export import generate_cable_csv
from schematika.electrical.field_devices import (
    CableData,
    DeviceCable,
    DeviceTemplate,
    FieldDevice,
    PinDef,
)
from schematika.electrical.terminal import Terminal


class TestGenerateCableCsv:
    def test_single_cable_device(self):
        t = Terminal("X03", "Motor")
        template = DeviceTemplate(
            mpn="3-phase motor",
            pins=(
                PinDef("U", t),
                PinDef("V", t),
                PinDef("W", t),
            ),
        )
        cable = CableData(wire_gauge=2.5)
        device = FieldDevice(tag="M1", template=template, terminal=t, cable=cable)

        connections = [
            ("M1", "U", t, "1", "PLC:DO", ""),
            ("M1", "V", t, "2", "PLC:DO", ""),
            ("M1", "W", t, "3", "PLC:DO", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "cables.csv")
            path, count, titles, _overrides = generate_cable_csv(
                connections, [device], output
            )
            assert Path(path).exists()
            assert count == 1
            assert len(titles) == 1

    def test_multi_cable_device(self):
        t = Terminal("X09", "IO")
        template = DeviceTemplate(
            mpn="Control valve",
            pins=(
                PinDef("1", t),
                PinDef("2", t),
                PinDef("3", t),
                PinDef("4", t),
            ),
        )
        dc1 = DeviceCable(
            pins=("1", "2"),
            cable=CableData(wire_gauge=1.5),
        )
        dc2 = DeviceCable(
            pins=("3", "4"),
            cable=CableData(wire_gauge=0.75),
        )
        device = FieldDevice(
            tag="CV1", template=template, terminal=t, cables=(dc1, dc2)
        )

        connections = [
            ("CV1", "1", t, "1", "", ""),
            ("CV1", "2", t, "2", "", ""),
            ("CV1", "3", t, "3", "", ""),
            ("CV1", "4", t, "4", "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "cables.csv")
            _path, count, _titles, _overrides = generate_cable_csv(
                connections, [device], output
            )
            assert count == 2  # two cable groups

    def test_csv_contents(self):
        t = Terminal("X05", "Power")
        template = DeviceTemplate(
            mpn="Pump",
            pins=(PinDef("U", t), PinDef("V", t)),
        )
        cable = CableData(wire_gauge=1.5, cable_note="Shielded", category="cable")
        device = FieldDevice(tag="PU1", template=template, cable=cable)

        connections = [
            ("PU1", "U", t, "1", "", ""),
            ("PU1", "V", t, "2", "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "cables.csv")
            path, _count, _titles, _overrides = generate_cable_csv(
                connections, [device], output
            )
            with Path(path).open(newline="") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 2
            assert rows[0]["comp_des_1"] == "PU1"
            assert rows[0]["wire_gauge"] == "1.5"
            assert rows[0]["cable_note"] == "Shielded"
            assert rows[0]["pin_1"] == "U"
            assert rows[0]["comp_des_2"] == "X05"

    def test_no_field_device(self):
        """Connections without a matching FieldDevice should still be written."""
        t = Terminal("X01", "Misc")
        connections = [
            ("UNKNOWN1", "A", t, "1", "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "cables.csv")
            _path, count, _titles, _overrides = generate_cable_csv(
                connections, [], output
            )
            assert count == 1

    def test_cable_titles_mapping(self):
        t = Terminal("X10", "Sensors")
        template = DeviceTemplate(mpn="Sensor", pins=(PinDef("1", t),))
        device = FieldDevice(
            tag="PT1", template=template, cable=CableData(wire_gauge=0.75)
        )

        connections = [("PT1", "1", t, "1", "", "")]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "cables.csv")
            _path, count, titles, _overrides = generate_cable_csv(
                connections, [device], output
            )
            assert count == 1
            assert "A-W001" in titles
            assert titles["A-W001"] == "PT1"
