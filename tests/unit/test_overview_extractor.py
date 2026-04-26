"""Tests for ``schematika.overview.extractor.extract``."""

from __future__ import annotations

import warnings

import pytest

from schematika.electrical.builder_models import BuildResult
from schematika.electrical.internal_device import InternalDevice
from schematika.electrical.model.state import create_initial_state
from schematika.electrical.system.system import Circuit
from schematika.electrical.terminal import Terminal
from schematika.overview.errors import (
    OverviewContainmentError,
    OverviewExtractionError,
)
from schematika.overview.extractor import (
    SYSTEM_CONTAINER_ID,
    ConnectionKey,
    extract,
)
from schematika.overview.model import ContainerSpec
from schematika.project import Project

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_result(
    *,
    devices: dict[str, InternalDevice] | None = None,
    terminal_pin_map: dict[str, list[str]] | None = None,
    wire_connections: list[tuple[str, str, str, str]] | None = None,
) -> BuildResult:
    return BuildResult(
        state=create_initial_state(),
        circuit=Circuit(),
        used_terminals=[],
        device_registry=devices or {},
        terminal_pin_map=terminal_pin_map or {},
        wire_connections=wire_connections or [],
    )


def _project_with(
    results: dict[str, BuildResult],
    *,
    external: list | None = None,
    terminals: dict[str, Terminal] | None = None,
) -> Project:
    project = Project()
    project._results = results
    if external is not None:
        project._external_connections = external
    if terminals is not None:
        project._terminals = terminals
    return project


def _device(prefix: str = "K") -> InternalDevice:
    return InternalDevice(prefix=prefix, mpn="MPN", description="desc")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_one_circuit_one_container() -> None:
    result = _make_result(
        devices={"K1": _device()},
        terminal_pin_map={"X1": ["1", "2"], "X2": ["1"]},
        wire_connections=[("X1", "1", "K1", "A1"), ("X2", "1", "K1", "A2")],
    )
    project = _project_with({"main": result})
    containment = {
        "cabinet": ContainerSpec(label="Cabinet", kind="cabinet", circuits=("main",)),
    }

    units, wires = extract(project, containment=containment)

    by_id = {u.id: u for u in units}
    assert set(by_id) == {"cabinet", "K1", "X1", "X2"}
    assert by_id["cabinet"].is_container
    assert by_id["K1"].kind == "device"
    assert by_id["K1"].parent == "cabinet"
    assert by_id["X1"].kind == "terminal"
    assert by_id["X1"].ports == ("1", "2")
    assert by_id["K1"].ports == ("A1", "A2")
    assert len(wires) == 2
    assert {(w.from_unit, w.to_unit) for w in wires} == {("X1", "K1"), ("X2", "K1")}


def test_external_connections_become_wires() -> None:
    result = _make_result(devices={"K1": _device()})
    # Row layout: component_from, pin_from, terminal, terminal_pin, component_to, pin_to.
    external = [("S1", "1", Terminal("X1"), "1", "K1", "A1")]
    project = _project_with({"main": result}, external=external)
    containment = {
        "cabinet": ContainerSpec(label="C", kind="cabinet", circuits=("main",)),
    }

    _units, wires = extract(project, containment=containment)

    assert any(
        w.from_unit == "X1" and w.from_port == "1" and w.to_unit == "K1" for w in wires
    )


# ---------------------------------------------------------------------------
# signal_kind classification
# ---------------------------------------------------------------------------


def test_default_classifier_marks_power_ports() -> None:
    result = _make_result(
        wire_connections=[
            ("PSU", "+24V", "K1", "A1"),
            ("X1", "out", "K1", "A2"),
        ],
    )
    project = _project_with({"main": result})
    containment = {
        "cab": ContainerSpec(label="C", kind="cabinet", circuits=("main",)),
    }

    _units, wires = extract(project, containment=containment)

    by_to_port = {w.to_port: w.kind for w in wires}
    assert by_to_port["A1"] == "power"
    assert by_to_port["A2"] == "signal"


def test_default_classifier_recognises_pe_and_n() -> None:
    result = _make_result(
        wire_connections=[
            ("X1", "PE", "M1", "PE"),
            ("X1", "N", "M1", "N"),
            ("X1", "1", "M1", "U"),
        ],
    )
    project = _project_with({"main": result})
    containment = {
        "cab": ContainerSpec(label="C", kind="cabinet", circuits=("main",)),
    }

    _units, wires = extract(project, containment=containment)

    kinds = {w.from_port: w.kind for w in wires}
    assert kinds["PE"] == "power"
    assert kinds["N"] == "power"
    assert kinds["1"] == "signal"


def test_custom_signal_kind_overrides_default() -> None:
    result = _make_result(
        wire_connections=[("X1", "+24V", "K1", "A1"), ("X1", "1", "K1", "A2")],
    )
    project = _project_with({"main": result})
    containment = {
        "cab": ContainerSpec(label="C", kind="cabinet", circuits=("main",)),
    }

    def all_safety(_key: ConnectionKey) -> str:
        return "safety"

    _units, wires = extract(project, containment=containment, signal_kind=all_safety)

    assert {w.kind for w in wires} == {"safety"}


# ---------------------------------------------------------------------------
# Containment validation errors
# ---------------------------------------------------------------------------


def test_containment_cycle_raises_with_path() -> None:
    project = _project_with({})
    containment = {
        "a": ContainerSpec(label="A", kind="x", parent="b"),
        "b": ContainerSpec(label="B", kind="x", parent="c"),
        "c": ContainerSpec(label="C", kind="x", parent="a"),
    }
    with pytest.raises(OverviewContainmentError) as excinfo:
        extract(project, containment=containment)
    msg = str(excinfo.value)
    assert "cycle" in msg.lower()
    assert "->" in msg


def test_unknown_circuit_in_containment_raises() -> None:
    project = _project_with({"main": _make_result()})
    containment = {
        "cab": ContainerSpec(label="C", kind="cab", circuits=("main", "ghost")),
    }
    with pytest.raises(OverviewContainmentError, match="ghost"):
        extract(project, containment=containment)


def test_circuit_in_two_containers_raises() -> None:
    project = _project_with({"main": _make_result()})
    containment = {
        "a": ContainerSpec(label="A", kind="x", circuits=("main",)),
        "b": ContainerSpec(label="B", kind="x", circuits=("main",)),
    }
    with pytest.raises(OverviewContainmentError, match="two containers"):
        extract(project, containment=containment)


def test_container_id_collides_with_circuit_key() -> None:
    project = _project_with({"main": _make_result()})
    containment = {
        "main": ContainerSpec(label="M", kind="cabinet"),
    }
    with pytest.raises(OverviewContainmentError, match="collide"):
        extract(project, containment=containment)


def test_unknown_parent_raises() -> None:
    project = _project_with({})
    containment = {
        "child": ContainerSpec(label="C", kind="pcb", parent="missing"),
    }
    with pytest.raises(OverviewContainmentError, match="missing"):
        extract(project, containment=containment)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unreferenced_circuit_falls_into_system_with_warning() -> None:
    result = _make_result(devices={"K1": _device()})
    project = _project_with({"orphan": result})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        units, _wires = extract(project, containment={})

    assert any("orphan" in str(w.message) for w in caught)
    by_id = {u.id: u for u in units}
    assert SYSTEM_CONTAINER_ID in by_id
    assert by_id[SYSTEM_CONTAINER_ID].is_container
    assert by_id["K1"].parent == SYSTEM_CONTAINER_ID


def test_empty_results_returns_root_only() -> None:
    project = _project_with({})

    units, wires = extract(project, containment={})

    assert wires == []
    assert len(units) == 1
    assert units[0].id == SYSTEM_CONTAINER_ID
    assert units[0].is_container


def test_empty_container_circuits_is_allowed() -> None:
    project = _project_with({})
    containment = {
        "empty": ContainerSpec(label="Empty", kind="cabinet", circuits=()),
    }

    units, _wires = extract(project, containment=containment)

    assert {u.id for u in units} == {"empty"}


def test_junction_two_rows_same_pin_does_not_crash() -> None:
    result = _make_result(
        devices={"K1": _device()},
        wire_connections=[
            ("X1", "1", "K1", "A1"),
            ("X2", "1", "K1", "A1"),
        ],
    )
    project = _project_with({"main": result})
    containment = {"cab": ContainerSpec(label="C", kind="cab", circuits=("main",))}

    units, wires = extract(project, containment=containment)

    assert len(wires) == 2
    by_id = {u.id: u for u in units}
    assert by_id["K1"].ports == ("A1",)


# ---------------------------------------------------------------------------
# Adapter shape checks
# ---------------------------------------------------------------------------


def test_get_results_raises_when_results_is_not_dict() -> None:
    project = Project()
    project._results = ["not a dict"]  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    with pytest.raises(OverviewExtractionError, match="dict"):
        extract(project, containment={})


def test_deterministic_ordering() -> None:
    result = _make_result(
        devices={"K2": _device(), "K1": _device()},
        wire_connections=[
            ("X2", "1", "K2", "A1"),
            ("X1", "1", "K1", "A1"),
        ],
    )
    project = _project_with({"main": result})
    containment = {"cab": ContainerSpec(label="C", kind="cab", circuits=("main",))}

    units1, wires1 = extract(project, containment=containment)
    units2, wires2 = extract(project, containment=containment)

    assert [u.id for u in units1] == [u.id for u in units2]
    assert [w.from_unit for w in wires1] == [w.from_unit for w in wires2]
    # K1 sorts before K2 (same parent "cab")
    device_ids = [u.id for u in units1 if u.kind == "device"]
    assert device_ids == ["K1", "K2"]
