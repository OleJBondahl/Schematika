from schematika.electrical import plc_csv_rows as exported_plc_csv_rows
from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    SequentialPin,
    generate_field_connections,
)
from schematika.electrical.harness import Harness
from schematika.electrical.plc_report import plc_csv_rows
from schematika.electrical.plc_resolver import (
    PlcModuleType,
    generate_plc_report_rows,
    resolve_plc_references,
)
from schematika.electrical.terminal import Terminal


def _di_rack():
    return [
        (
            "DI1",
            PlcModuleType(
                mpn="DI16", signal_type="DI", channels=4, pins_per_channel=("",)
            ),
        )
    ]


def test_plc_csv_rows_connected_and_empty():
    term = Terminal("X1", "Terminal strip")
    plc = Terminal("PLC:DI", "PLC DI", reference=True)
    tmpl = DeviceTemplate("MPN", (SequentialPin("1", term, plc),))
    h = Harness(rack=_di_rack())
    h.add_field_devices([FieldDevice("TT-1", tmpl)])
    rows = plc_csv_rows(h.build(), _di_rack())

    assert len(rows) == 4  # 4 channels -> 4 rows (1 connected, 3 empty)
    connected = [r for r in rows if r[3]]  # Component (index 3) non-empty
    assert len(connected) == 1
    module, mpn, plc_pin, component, pin, terminal, location = connected[0]
    assert module == "DI1"
    assert mpn == "DI16"
    assert plc_pin != ""
    assert component == "TT-1"
    assert pin == "1"
    assert terminal == "X1:1"
    assert location == ""


def test_plc_csv_rows_exported_from_package():
    assert exported_plc_csv_rows is plc_csv_rows


def test_plc_csv_rows_parity_with_legacy_pipeline():
    term = Terminal("X1", "Terminal strip")
    plc = Terminal("PLC:DI", "PLC DI", reference=True)
    tmpl = DeviceTemplate(
        "MPN",
        (SequentialPin("1", term, plc), SequentialPin("2", term, plc)),
    )
    devices = [
        FieldDevice("TT-1", tmpl, location="pit 3"),
        FieldDevice("TT-2", tmpl),
    ]
    rack = _di_rack()
    locations = {d.tag: d.location for d in devices if d.location}

    legacy = generate_plc_report_rows(
        resolve_plc_references(generate_field_connections(devices), rack),
        rack,
        locations,
    )

    h = Harness(rack=_di_rack())
    h.add_field_devices(devices)
    new = plc_csv_rows(h.build(), _di_rack(), locations)

    assert new == legacy


def test_field_device_location_default_and_set():
    term = Terminal("X1", "Terminal strip")
    plc = Terminal("PLC:DI", "PLC DI", reference=True)
    tmpl = DeviceTemplate("MPN", (SequentialPin("1", term, plc),))
    assert FieldDevice("TT-1", tmpl).location == ""
    dev = FieldDevice("TT-1", tmpl, location="coolant inlet")
    assert dev.location == "coolant inlet"


def test_plc_csv_rows_location_column():
    term = Terminal("X1", "Terminal strip")
    plc = Terminal("PLC:DI", "PLC DI", reference=True)
    tmpl = DeviceTemplate("MPN", (SequentialPin("1", term, plc),))
    h = Harness(rack=_di_rack())
    h.add_field_devices([FieldDevice("TT-1", tmpl, location="coolant inlet")])
    rows = plc_csv_rows(h.build(), _di_rack(), {"TT-1": "coolant inlet"})
    connected = [r for r in rows if r[3]]
    assert connected[0][6] == "coolant inlet"
    empty = [r for r in rows if not r[3]]
    assert all(r[6] == "" for r in empty)
