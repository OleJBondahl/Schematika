from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    FixedPin,
    PrefixedPin,
    SequentialPin,
)
from schematika.electrical.harness import Harness
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


def _targets(result):
    return {(str(w.target.device), w.target.port_id) for w in result.wires}


def _sources(result):
    return {(str(w.source.device), w.source.port_id) for w in result.wires}


def test_add_field_devices_sequential_pins():
    term = Terminal("X1", "Terminal strip")
    tmpl = DeviceTemplate("MPN", (SequentialPin("1", term), SequentialPin("2", term)))
    h = Harness(rack=[])
    h.add_field_devices([FieldDevice("TT-101", tmpl)])
    result = h.build()
    assert _targets(result) == {("X1", "1"), ("X1", "2")}
    assert _sources(result) == {("TT-101", "1"), ("TT-101", "2")}


def test_add_field_devices_fixed_pin():
    term = Terminal("X1", "Terminal strip")
    tmpl = DeviceTemplate("MPN", (FixedPin("A", term, terminal_pin="7"),))
    h = Harness(rack=[])
    h.add_field_devices([FieldDevice("TT-1", tmpl)])
    assert _targets(h.build()) == {("X1", "7")}


def test_add_field_devices_prefixed_pins():
    term = Terminal("X1", "Terminal strip")
    tmpl = DeviceTemplate(
        "MPN",
        (
            PrefixedPin("L", term, pin_prefix="L1"),
            PrefixedPin("N", term, pin_prefix="N"),
        ),
    )
    h = Harness(rack=[])
    h.add_field_devices([FieldDevice("M1", tmpl)])
    assert _targets(h.build()) == {("X1", "L1:1"), ("X1", "N:1")}


def test_add_field_devices_reuse_terminals():
    term = Terminal("X1", "Terminal strip")
    tmpl = DeviceTemplate("MPN", (SequentialPin("1", term), SequentialPin("2", term)))
    h = Harness(rack=[])
    h.add_field_devices(
        [FieldDevice("TT-1", tmpl)], reuse_terminals={"X1": ["10", "11"]}
    )
    assert _targets(h.build()) == {("X1", "10"), ("X1", "11")}


def test_add_field_devices_plc_allocation():
    term = Terminal("X1", "Terminal strip")
    plc = Terminal("PLC:DI", "PLC DI", reference=True)
    tmpl = DeviceTemplate("MPN", (SequentialPin("1", term, plc),))
    h = Harness(rack=_di_rack())
    h.add_field_devices([FieldDevice("TT-1", tmpl)])
    result = h.build()
    assert len(result.plc_assignments) == 1
    asg = result.plc_assignments[0]
    assert asg.signal_type == "DI"
    assert (str(asg.source.device), asg.source.port_id) == ("TT-1", "1")
    # one device->terminal wire + one terminal->PLC wire
    assert len(result.wires) == 2
    plc_targets = {
        (str(w.target.device), w.target.port_id)
        for w in result.wires
        if str(w.target.device).startswith("PLC:")
    }
    assert plc_targets == {(f"PLC:{asg.module}", asg.pin_label)}
