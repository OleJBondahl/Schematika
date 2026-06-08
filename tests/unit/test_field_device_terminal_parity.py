"""R2: field_devices() resolved through the Harness emits a byte-identical CSV.

The legacy tuple path (generate_field_connections -> resolve_plc_references ->
_external_connections -> verbatim rows) and the new Harness wire path
(add_field_devices -> wires + PlcAssignment, correlated back into rows) must
produce the same ``system_terminals.csv`` bytes, for a device pin WITH a PLC
ref and a pin WITHOUT.
"""

from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    PinDef,
)
from schematika.electrical.plc_resolver import PlcModuleType
from schematika.electrical.terminal import Terminal
from schematika.project import Project

_DI = PlcModuleType(mpn="DI16", signal_type="DI", channels=8, pins_per_channel=("",))


def _devices() -> list[FieldDevice]:
    sig = Terminal("X100", "Signal terminal")
    plc_di = Terminal("PLC:DI", "PLC Digital Input", reference=True)
    template = DeviceTemplate(
        mpn="SENSOR",
        pins=(
            PinDef("Sig", sig, plc_di),  # pin WITH plc -> 3-entity row
            PinDef("GND", sig),  # pin WITHOUT plc -> device->terminal only
        ),
    )
    return [FieldDevice(tag="TT-101", template=template)]


def _build_project() -> Project:
    p = Project()
    p.plc_rack([("DI1", _DI)])
    p.field_devices(_devices())
    return p


def test_field_device_native_csv_byte_identical_to_legacy(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    native_dir = tmp_path / "native"
    native_dir.mkdir()

    p_legacy = _build_project()
    p_legacy._build_all_circuits()
    p_legacy._resolve_field_devices()
    p_legacy._resolve_routes()
    p_legacy._generate_system_csv(str(legacy_dir))

    p_native = _build_project().use_native_terminal_emit()
    p_native._build_all_circuits()
    p_native._resolve_field_devices()
    p_native._resolve_routes()
    p_native._emit_system_csv(str(native_dir))

    assert (native_dir / "system_terminals.csv").read_bytes() == (
        legacy_dir / "system_terminals.csv"
    ).read_bytes()


def test_buffered_plc_assignments_recorded():
    p = _build_project()
    p._build_all_circuits()
    p._resolve_field_devices()
    # One pin references PLC:DI; it must yield one buffered assignment.
    assert len(p._plc_assignments) == 1
    a = p._plc_assignments[0]
    assert a.module == "DI1"
    assert str(a.source.device) == "TT-101"
