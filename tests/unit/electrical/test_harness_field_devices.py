from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    FixedPin,
    PrefixedPin,
    SequentialPin,
    generate_field_connections,
)
from schematika.electrical.harness import Harness, _split_plc_ref
from schematika.electrical.plc_resolver import PlcModuleType, resolve_plc_references
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


def test_split_plc_ref_parses_type_and_suffix():
    assert _split_plc_ref("PLC:DI") == ("DI", "")
    assert _split_plc_ref("PLC:RTD:+R") == ("RTD", "+R")
    assert _split_plc_ref("PLC:AI:Sig") == ("AI", "Sig")


def test_parity_with_legacy_pipeline():
    term = Terminal("X1", "Terminal strip")
    plc_di = Terminal("PLC:DI", "PLC DI", reference=True)
    tmpl = DeviceTemplate(
        "MPN",
        (
            SequentialPin("1", term, plc_di),
            SequentialPin("2", term),
            FixedPin("3", term, terminal_pin="9"),
        ),
    )
    devices = [FieldDevice("TT-1", tmpl), FieldDevice("TT-2", tmpl)]
    rack = _di_rack()

    legacy = resolve_plc_references(generate_field_connections(devices), rack)

    h = Harness(rack=rack)
    h.add_field_devices(devices)
    result = h.build()

    legacy_dev_term = {(cf, pf, str(t), tp) for cf, pf, t, tp, _ct, _pt in legacy}
    new_dev_term = {
        (str(w.source.device), w.source.port_id, str(w.target.device), w.target.port_id)
        for w in result.wires
        if not str(w.target.device).startswith("PLC:")
    }
    assert new_dev_term == legacy_dev_term

    legacy_plc = {(ct, pt) for *_rest, ct, pt in legacy if ct.startswith("PLC:")}
    new_plc = {(f"PLC:{a.module}", a.pin_label) for a in result.plc_assignments}
    assert new_plc == legacy_plc
