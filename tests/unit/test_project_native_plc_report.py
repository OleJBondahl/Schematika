"""R3: opt-in native PLC report is byte-identical to the legacy 3-source path.

The legacy path (_generate_plc_csv: external + registry -> generate_plc_report_rows)
and the native path (use_native_plc_report -> _generate_plc_csv_native ->
plc_csv_rows over the buffered field-device HarnessBuildResult) must produce the
same ``plc_connections.csv`` bytes for a field device WITH a PLC pin (allocated
channel) on a rack with spare (unallocated) channels.
"""

from typing import Any

import pytest

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.builder import BuildResult
from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    PinDef,
)
from schematika.electrical.plc_resolver import (
    PlcModuleType,
    extract_plc_connections_from_registry,
)
from schematika.electrical.system.connection_registry import log_connection
from schematika.electrical.system.system import Circuit
from schematika.electrical.terminal import Terminal
from schematika.project import Project

_DI = PlcModuleType(mpn="DI16", signal_type="DI", channels=8, pins_per_channel=("",))
_DO = PlcModuleType(mpn="DO16", signal_type="DO", channels=8, pins_per_channel=("",))


def _devices() -> list[FieldDevice]:
    sig = Terminal("X100", "Signal terminal")
    plc_di = Terminal("PLC:DI", "PLC Digital Input", reference=True)
    template = DeviceTemplate(
        mpn="SENSOR",
        pins=(
            PinDef("Sig", sig, plc_di),  # allocates one DI channel
            PinDef("GND", sig),  # no PLC ref
        ),
    )
    return [FieldDevice(tag="TT-101", template=template)]


def _build_project() -> Project:
    p = Project()
    p.plc_rack([("DI1", _DI)])
    p.field_devices(_devices())
    return p


def test_fixture_has_no_registry_plc_connections():
    # The native field-device path only covers field-device PLC channels; assert
    # the fixture logs none in the registry, so legacy and native must agree.
    p = _build_project()
    p._build_all_circuits()
    p._resolve_field_devices()
    external = list(p._external_connections)
    registry = extract_plc_connections_from_registry(p._state, [("DI1", _DI)], external)
    assert registry == []


def test_native_plc_csv_byte_identical_to_legacy(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    native_dir = tmp_path / "native"
    native_dir.mkdir()

    p_legacy = _build_project()
    p_legacy._build_all_circuits()
    p_legacy._resolve_field_devices()
    p_legacy._resolve_routes()
    legacy_csv = str(legacy_dir / "plc_connections.csv")
    p_legacy._generate_plc_csv(legacy_csv)

    p_native = _build_project().use_native_plc_report()
    p_native._build_all_circuits()
    p_native._resolve_field_devices()
    p_native._resolve_routes()
    native_csv = str(native_dir / "plc_connections.csv")
    p_native._generate_plc_csv(native_csv)

    assert (native_dir / "plc_connections.csv").read_bytes() == (
        legacy_dir / "plc_connections.csv"
    ).read_bytes()


def _circuit_with_registry_plc(state: Any, **_kwargs: Any) -> BuildResult:
    # A registry-logged PLC connection the field-device-only native path can't see.
    state = log_connection(state, "PLC:DO", "1", "K1", "13", "top")
    return BuildResult(state=state, circuit=Circuit(), used_terminals=[])


def test_native_plc_refuses_when_registry_plc_connection_present(tmp_path):
    # field device with a PLC pin (native covers it) PLUS a registry PLC connection
    # (native can't see it) -> the guard must refuse rather than drop the row.
    p = Project().use_native_plc_report()
    p.plc_rack([("DI1", _DI), ("DO1", _DO)])
    p.add_circuit("c1", _circuit_with_registry_plc)
    p.field_devices(_devices())
    p._build_all_circuits()
    p._resolve_field_devices()
    p._resolve_routes()

    with pytest.raises(CircuitValidationError):
        p._generate_plc_csv(str(tmp_path / "plc_connections.csv"))
