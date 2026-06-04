from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    SequentialPin,
)
from schematika.electrical.harness import Harness
from schematika.electrical.plc_report import plc_csv_rows
from schematika.electrical.plc_resolver import PlcModuleType
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
    module, mpn, plc_pin, component, pin, terminal = connected[0]
    assert module == "DI1"
    assert mpn == "DI16"
    assert plc_pin != ""
    assert component == "TT-1"
    assert pin == "1"
    assert terminal == "X1:1"
