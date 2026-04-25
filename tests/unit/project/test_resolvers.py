"""Tests for Project resolver / build internals.

Targets:
- ``schematika.project._resolve_svg_for_page`` (module-level helper)
- ``Project._resolve_field_devices``
- ``Project._resolve_terminal_reuse``
- ``Project._resolve_template_reuse``
- ``Project._build_descriptor_circuit``
- ``Project._build_one_circuit``
- ``Project._generate_system_csv``
- ``Project._generate_plc_csv``
- ``Project._render_block_svgs``
- ``Project._render_pid_svgs``
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from schematika.block.diagram import BlockDiagram
from schematika.core.exceptions import CircuitValidationError
from schematika.electrical import Terminal, comp, term
from schematika.electrical.builder import BuildResult
from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    SequentialPin,
)
from schematika.electrical.plc_resolver import PlcModuleType
from schematika.electrical.symbols.coils import coil
from schematika.electrical.system.system import Circuit
from schematika.project import Project, _CircuitDef, _resolve_svg_for_page

# ---------------------------------------------------------------------------
# _resolve_svg_for_page (module-level pure function)
# ---------------------------------------------------------------------------


def test_resolve_svg_schematic_uses_svg_paths():
    svg_paths = {"a": "/svg/a.svg"}
    csv_paths = {"a": "/csv/a.csv"}
    svg, csv_p = _resolve_svg_for_page(
        "schematic", "a", svg_paths, csv_paths, None, None
    )
    assert svg == "/svg/a.svg"
    assert csv_p == "/csv/a.csv"


def test_resolve_svg_schematic_missing_csv():
    svg_paths = {"a": "/svg/a.svg"}
    csv_paths: dict[str, str] = {}
    svg, csv_p = _resolve_svg_for_page(
        "schematic", "a", svg_paths, csv_paths, None, None
    )
    assert svg == "/svg/a.svg"
    assert csv_p is None


def test_resolve_svg_schematic_missing_svg():
    svg, csv_p = _resolve_svg_for_page("schematic", "missing", {}, {}, None, None)
    assert svg == ""
    assert csv_p is None


def test_resolve_svg_pid_uses_pid_paths_only():
    svg, csv_p = _resolve_svg_for_page(
        "pid",
        "p1",
        svg_paths={"p1": "/wrong.svg"},
        csv_paths={"p1": "/wrong.csv"},
        pid_svg_paths={"p1": "/pid/p1.svg"},
        block_svg_paths={"p1": "/block/p1.svg"},
    )
    assert svg == "/pid/p1.svg"
    assert csv_p is None


def test_resolve_svg_pid_with_no_pid_paths_returns_empty():
    svg, csv_p = _resolve_svg_for_page("pid", "p1", {}, {}, None, None)
    assert svg == ""
    assert csv_p is None


def test_resolve_svg_pid_missing_key_returns_empty():
    svg, csv_p = _resolve_svg_for_page("pid", "absent", {}, {}, {"other": "/x"}, None)
    assert svg == ""
    assert csv_p is None


def test_resolve_svg_block_uses_block_paths_only():
    svg, csv_p = _resolve_svg_for_page(
        "block",
        "b1",
        svg_paths={"b1": "/wrong.svg"},
        csv_paths={"b1": "/wrong.csv"},
        pid_svg_paths={"b1": "/pid.svg"},
        block_svg_paths={"b1": "/block/b1.svg"},
    )
    assert svg == "/block/b1.svg"
    assert csv_p is None


def test_resolve_svg_block_with_no_block_paths_returns_empty():
    svg, csv_p = _resolve_svg_for_page("block", "b1", {}, {}, None, None)
    assert svg == ""
    assert csv_p is None


# ---------------------------------------------------------------------------
# _build_descriptor_circuit
# ---------------------------------------------------------------------------


def test_build_descriptor_circuit_no_components_raises():
    """Descriptor circuit with components=None must raise CircuitValidationError."""
    p = Project()
    cdef = _CircuitDef(key="bad", factory="descriptors", components=None)
    with pytest.raises(CircuitValidationError, match="no components defined"):
        p._build_descriptor_circuit(cdef, resolved_reuse=None)


def test_build_descriptor_circuit_runs_with_components():
    """A minimal descriptor circuit can be built directly."""
    p = Project()
    p.terminals(Terminal("X1", "Power"), Terminal("X2", "GND"))
    cdef = _CircuitDef(
        key="coils",
        factory="descriptors",
        components=[
            term("X1"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X2"),
        ],
        count=1,
    )
    result = p._build_descriptor_circuit(cdef, resolved_reuse=None)
    assert isinstance(result, BuildResult)


def test_build_descriptor_circuit_uses_count_param():
    p = Project()
    p.terminals(Terminal("X1", "Power"), Terminal("X2", "GND"))
    cdef = _CircuitDef(
        key="coils",
        factory="descriptors",
        components=[
            term("X1"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X2"),
        ],
        count=3,
    )
    result = p._build_descriptor_circuit(cdef, resolved_reuse=None)
    # Three K instances should have been allocated
    assert "K" in result.component_map
    assert len(result.component_map["K"]) == 3


def test_build_descriptor_circuit_passes_x_y_spacing():
    """Default x/y/spacing values are read from cdef.params."""
    p = Project()
    p.terminals(Terminal("X1", "Power"), Terminal("X2", "GND"))
    cdef = _CircuitDef(
        key="coils",
        factory="descriptors",
        components=[
            term("X1"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X2"),
        ],
        count=1,
        params={"x": 100.0, "y": 50.0, "spacing": 60.0},
    )
    # Should not raise — values are forwarded to build_from_descriptors
    result = p._build_descriptor_circuit(cdef, resolved_reuse=None)
    assert isinstance(result, BuildResult)


# ---------------------------------------------------------------------------
# _build_one_circuit dispatcher
# ---------------------------------------------------------------------------


def test_build_one_circuit_descriptors_dispatches():
    p = Project()
    p.terminals(Terminal("X1", "Power"), Terminal("X2", "GND"))
    cdef = _CircuitDef(
        key="c",
        factory="descriptors",
        components=[term("X1"), comp(coil, "K", pins=("A1", "A2")), term("X2")],
    )
    result = p._build_one_circuit(cdef)
    assert isinstance(result, BuildResult)


def test_build_one_circuit_custom_dispatches():
    p = Project()

    def builder(state, **_kw):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

    cdef = _CircuitDef(key="c", factory="custom", builder_fn=builder)
    result = p._build_one_circuit(cdef)
    assert isinstance(result, BuildResult)


def test_build_one_circuit_unknown_factory_raises():
    p = Project()
    cdef = _CircuitDef(key="c", factory="weird")
    with pytest.raises(CircuitValidationError, match="Unknown circuit factory"):
        p._build_one_circuit(cdef)


def test_build_one_circuit_reuse_tags_unbuilt_raises():
    p = Project()
    p.terminals(Terminal("X1", "Power"), Terminal("X2", "GND"))
    cdef = _CircuitDef(
        key="c",
        factory="descriptors",
        components=[term("X1"), comp(coil, "K", pins=("A1", "A2")), term("X2")],
        reuse_tags={"K": "missing_circuit"},
    )
    with pytest.raises(CircuitValidationError, match="hasn't been built yet"):
        p._build_one_circuit(cdef)


# ---------------------------------------------------------------------------
# _resolve_terminal_reuse / _resolve_template_reuse
# ---------------------------------------------------------------------------


def test_resolve_terminal_reuse_none_returns_none():
    p = Project()
    assert p._resolve_terminal_reuse(None) is None
    assert p._resolve_terminal_reuse({}) is None


def test_resolve_terminal_reuse_unknown_key_raises():
    p = Project()
    t = Terminal("X1", "P")
    with pytest.raises(CircuitValidationError, match="hasn't been built yet"):
        p._resolve_terminal_reuse({t: "missing"})


def test_resolve_terminal_reuse_resolves_to_result():
    p = Project()

    def builder(state, **_kw):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

    p.add_circuit("src", builder)
    p.build_circuits()

    t = Terminal("X1", "P")
    out = p._resolve_terminal_reuse({t: "src"})
    assert out is not None
    assert out["X1"] is p._results["src"]


def test_resolve_template_reuse_none_returns_none():
    p = Project()
    assert p._resolve_template_reuse(None) is None
    assert p._resolve_template_reuse({}) is None


def test_resolve_template_reuse_unknown_key_raises():
    p = Project()
    t = Terminal("X1", "P")
    template = DeviceTemplate(mpn="X", pins=())
    with pytest.raises(CircuitValidationError, match="hasn't been built yet"):
        p._resolve_template_reuse({template: {t: "missing"}})


def test_resolve_template_reuse_resolves_per_template():
    p = Project()

    def builder(state, **_kw):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

    p.add_circuit("src", builder)
    p.build_circuits()

    t = Terminal("X1", "P")
    template = DeviceTemplate(mpn="X", pins=())
    out = p._resolve_template_reuse({template: {t: "src"}})
    assert out is not None
    assert out[template]["X1"] is p._results["src"]


# ---------------------------------------------------------------------------
# _resolve_field_devices
# ---------------------------------------------------------------------------


def test_resolve_field_devices_empty_is_noop():
    p = Project()
    p._resolve_field_devices()  # no field_device_defs -> nothing to do
    assert p._external_connections == []


def test_resolve_field_devices_populates_external_connections():
    t = Terminal("X1", "Power")
    template = DeviceTemplate(mpn="Motor", pins=(SequentialPin("U", terminal=t),))
    device = FieldDevice(tag="M1", template=template)

    p = Project()
    p.terminals(t)
    p.field_devices([device])
    # build at least one circuit so state is consistent
    p.add_circuit(
        "_dummy",
        lambda s, **_kw: BuildResult(state=s, circuit=Circuit(), used_terminals=[]),
    )
    p.build_circuits()
    # _resolve_field_devices was called -> external connections exist
    assert len(p._external_connections) >= 1
    # Connection refers to terminal X1
    found = any(str(row[2]) == "X1" for row in p._external_connections)
    assert found


def test_resolve_field_devices_with_reuse_unbuilt_raises():
    t = Terminal("X1", "Power")
    template = DeviceTemplate(mpn="Motor", pins=(SequentialPin("U", terminal=t),))
    device = FieldDevice(tag="M1", template=template)

    p = Project()
    p.terminals(t)
    # reuse points at a non-existent circuit
    p.field_devices([device], reuse_terminals={t: "missing"})
    with pytest.raises(CircuitValidationError, match="hasn't been built yet"):
        p._resolve_field_devices()


# ---------------------------------------------------------------------------
# _generate_system_csv
# ---------------------------------------------------------------------------


def test_generate_system_csv_creates_file(tmp_path):
    p = Project()
    p.terminals(Terminal("X1", "Power"))
    p.add_circuit(
        "c",
        lambda s, **_kw: BuildResult(state=s, circuit=Circuit(), used_terminals=[]),
    )
    p.build_circuits()
    out_dir = str(tmp_path)
    path = p._generate_system_csv(out_dir)
    assert path.endswith("system_terminals.csv")
    assert Path(path).exists()


def test_generate_system_csv_filters_plc_prefixed_connections(tmp_path):
    """PLC-prefixed connections must be filtered out of system_terminals.csv."""
    from schematika.electrical.system.connection_registry import log_connection

    p = Project()
    p.terminals(Terminal("X1", "Power"))
    # Inject a PLC-prefixed and a regular registry connection via state mutation
    p._state = log_connection(p._state, "PLC:DO", "1", "Q1", "out")
    p._state = log_connection(p._state, "X1", "1", "Q1", "in")

    out_dir = str(tmp_path)
    csv_path = p._generate_system_csv(out_dir)
    with Path(csv_path).open(encoding="utf-8") as f:
        text = f.read()
    # X1 should appear; PLC:DO must not
    assert "X1" in text
    assert "PLC:DO" not in text


# ---------------------------------------------------------------------------
# _generate_plc_csv
# ---------------------------------------------------------------------------


def _make_di_rack():
    di_module = PlcModuleType(
        mpn="750-1405",
        signal_type="DI",
        channels=4,
        pins_per_channel=("",),
    )
    return [("DI1", di_module)]


def test_generate_plc_csv_writes_header(tmp_path):
    p = Project()
    p.plc_rack(_make_di_rack())
    csv_path = str(tmp_path / "plc.csv")
    p._generate_plc_csv(csv_path)
    with Path(csv_path).open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Module", "MPN", "PLC Pin", "Component", "Pin", "Terminal"]


def test_generate_plc_csv_with_external_connection(tmp_path):
    p = Project()
    p.plc_rack(_make_di_rack())
    # Add an external connection that resolves to a PLC tag
    p.external_connections([("Sensor1", "Sig+", "X10", "1", "PLC:DI", "")])
    csv_path = str(tmp_path / "plc.csv")
    p._generate_plc_csv(csv_path)

    with Path(csv_path).open(newline="") as f:
        rows = list(csv.reader(f))
    # Header + at least one data row referring to Sensor1
    data_rows = rows[1:]
    assert any("Sensor1" in row for row in data_rows)


def test_generate_plc_csv_empty_rack_writes_header_only(tmp_path):
    p = Project()
    p.plc_rack([])  # empty rack
    csv_path = str(tmp_path / "plc.csv")
    p._generate_plc_csv(csv_path)
    with Path(csv_path).open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Module", "MPN", "PLC Pin", "Component", "Pin", "Terminal"]
    # No data rows
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# _render_block_svgs / _render_pid_svgs
# ---------------------------------------------------------------------------


def test_render_block_svgs_writes_one_svg_per_block(tmp_path):
    p = Project()
    d1 = BlockDiagram()
    d1.block("First")
    d2 = BlockDiagram()
    d2.block("Second")
    p.add_block_diagram("d1", d1)
    p.add_block_diagram("d2", d2)
    p._build_all_block_diagrams()

    out_dir = str(tmp_path)
    paths = p._render_block_svgs(out_dir)
    assert set(paths.keys()) == {"d1", "d2"}
    for key, path in paths.items():
        assert Path(path).exists()
        assert path.endswith(f"block_{key}.svg")


def test_render_block_svgs_empty_when_no_diagrams(tmp_path):
    p = Project()
    paths = p._render_block_svgs(str(tmp_path))
    assert paths == {}


def test_render_pid_svgs_empty_when_no_diagrams(tmp_path):
    p = Project()
    paths = p._render_pid_svgs(str(tmp_path))
    assert paths == {}


# ---------------------------------------------------------------------------
# _build_all_pids type checking
# ---------------------------------------------------------------------------


def test_build_all_pids_rejects_non_callable():
    p = Project()
    p.add_pid("bad", 12345)  # not a builder, not callable
    with pytest.raises(TypeError, match="must be a"):
        p._build_all_pids()


def test_build_all_pids_accepts_callable_factory():
    """A callable factory returning a PIDBuildResult-shaped object should work."""
    from schematika.pid.builder import PIDBuildResult
    from schematika.pid.diagram import PIDDiagram

    def factory(state):
        return PIDBuildResult(
            state=state,
            diagram=PIDDiagram(),
            equipment_map={},
            instrument_map={},
        )

    p = Project()
    p.add_pid("ok", factory)
    p._build_all_pids()
    assert "ok" in p._pid_results
