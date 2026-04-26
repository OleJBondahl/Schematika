"""Tests for ``schematika.overview.extractor.extract`` (boundary-view algorithm)."""

from __future__ import annotations

import pytest

from schematika.electrical.terminal import Terminal
from schematika.overview.errors import (
    OverviewContainmentError,
    OverviewExtractionError,
)
from schematika.overview.extractor import ConnectionKey, extract
from schematika.overview.model import ContainerSpec
from schematika.project import Project

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _project(
    *,
    external: list | None = None,
    terminals: dict[str, Terminal] | None = None,
) -> Project:
    project = Project()
    project._external_connections = external or []
    project._terminals = terminals or {}
    return project


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_terminals_inside_cabinet_field_devices_grouped_by_kind() -> None:
    external = [
        ("M1", "U", Terminal("X02"), "1", "", ""),
        ("M1", "V", Terminal("X02"), "2", "", ""),
        ("S1", "1", Terminal("X05"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="Cabinet", kind="cabinet")}

    units, wires = extract(project, containment=containment)

    by_id = {u.id: u for u in units}
    assert by_id["X02"].kind == "terminal"
    assert by_id["X02"].parent == "cab"
    assert by_id["X05"].parent == "cab"
    # M1 is unclassified -> "<field_other>"; S1 matches the switches pattern.
    assert by_id["M1"].kind == "field_device"
    assert by_id["M1"].parent == "<field_other>"
    assert by_id["S1"].parent == "<field_switches>"
    # Synthetic kind containers for both groups are emitted.
    assert by_id["<field_other>"].is_container
    assert by_id["<field_switches>"].is_container
    assert len(wires) == 3


def test_terminal_pins_filtered_to_used_only() -> None:
    """Terminal in ``_terminals`` with no boundary rows produces no Unit."""
    external = [("M1", "U", Terminal("X02"), "1", "", "")]
    terminals = {"X02": Terminal("X02"), "X99": Terminal("X99")}  # X99 has no rows
    project = _project(external=external, terminals=terminals)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, _ = extract(project, containment=containment)

    by_id = {u.id: u for u in units}
    assert "X99" not in by_id
    assert by_id["X02"].ports == ("1",)


def test_terminal_label_uses_title_when_available() -> None:
    external = [("M1", "U", Terminal("X02"), "1", "", "")]
    terminals = {"X02": Terminal("X02", "Pump 1 Motor Power", description="d")}
    project = _project(external=external, terminals=terminals)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, _ = extract(project, containment=containment)

    x02 = next(u for u in units if u.id == "X02")
    assert "Pump 1 Motor Power" in x02.label


def test_terminal_label_falls_back_to_id_when_no_title() -> None:
    external = [("M1", "U", Terminal("X02"), "1", "", "")]
    project = _project(external=external)  # no _terminals entry
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, _ = extract(project, containment=containment)

    x02 = next(u for u in units if u.id == "X02")
    assert x02.label == "X02"


def test_field_device_ports_aggregate_across_rows() -> None:
    external = [
        ("M1", "U", Terminal("X02"), "1", "", ""),
        ("M1", "V", Terminal("X02"), "2", "", ""),
        ("M1", "W", Terminal("X02"), "3", "", ""),
        ("M1", "PE", Terminal("PE"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, _ = extract(project, containment=containment)

    m1 = next(u for u in units if u.id == "M1")
    assert set(m1.ports) == {"U", "V", "W", "PE"}


def test_terminal_pins_sort_numerically_then_alpha() -> None:
    external = [
        ("M1", "a", Terminal("X02"), "10", "", ""),
        ("M1", "b", Terminal("X02"), "2", "", ""),
        ("M1", "c", Terminal("X02"), "PE", "", ""),
        ("M1", "d", Terminal("X02"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, _ = extract(project, containment=containment)

    x02 = next(u for u in units if u.id == "X02")
    assert x02.ports == ("1", "2", "10", "PE")


# ---------------------------------------------------------------------------
# Wires
# ---------------------------------------------------------------------------


def test_wires_go_terminal_to_device() -> None:
    external = [("M1", "U", Terminal("X02"), "1", "", "")]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    _, wires = extract(project, containment=containment)

    assert len(wires) == 1
    w = wires[0]
    assert (w.from_unit, w.from_port, w.to_unit, w.to_port) == ("X02", "1", "M1", "U")


def test_duplicate_rows_dedup_to_one_wire() -> None:
    external = [
        ("M1", "U", Terminal("X02"), "1", "", ""),
        ("M1", "U", Terminal("X02"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    _, wires = extract(project, containment=containment)

    assert len(wires) == 1


def test_rows_with_empty_endpoint_dropped() -> None:
    external = [
        ("", "", Terminal("X02"), "1", "", ""),  # missing field-device side
        ("M1", "U", Terminal(""), "", "", ""),  # missing terminal side
        ("M1", "U", Terminal("X02"), "1", "", ""),  # valid
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    _, wires = extract(project, containment=containment)

    assert len(wires) == 1


def test_internal_wires_are_not_in_output() -> None:
    """Even if circuit results have internal wires, they don't appear in the overview.

    The boundary view ignores ``project._results`` entirely.
    """
    project = Project()
    project._external_connections = [("M1", "U", Terminal("X02"), "1", "", "")]
    # No terminals dict change; results stays empty as a Project default.
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, wires = extract(project, containment=containment)

    assert len(wires) == 1
    # All non-container kinds are terminal or field_device.
    assert all(u.kind in {"terminal", "field_device"} or u.is_container for u in units)


# ---------------------------------------------------------------------------
# signal_kind classification
# ---------------------------------------------------------------------------


def test_default_classifier_marks_power_ports() -> None:
    external = [
        ("PSU", "+24V", Terminal("X10"), "1", "", ""),
        ("S1", "out", Terminal("X05"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    _, wires = extract(project, containment=containment)

    by_to_port = {w.to_port: w.kind for w in wires}
    assert by_to_port["+24V"] == "power"
    assert by_to_port["out"] == "signal"


def test_default_classifier_recognises_pe_and_n() -> None:
    external = [
        ("M1", "PE", Terminal("PE_BAR"), "1", "", ""),
        ("M1", "N", Terminal("X01"), "N", "", ""),
        ("M1", "U", Terminal("X02"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    _, wires = extract(project, containment=containment)

    kinds = {w.to_port: w.kind for w in wires}
    assert kinds["PE"] == "power"
    assert kinds["N"] == "power"
    assert kinds["U"] == "signal"


def test_custom_signal_kind_overrides_default() -> None:
    external = [
        ("PSU", "+24V", Terminal("X10"), "1", "", ""),
        ("S1", "1", Terminal("X05"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    def all_safety(_key: ConnectionKey) -> str:
        return "safety"

    _, wires = extract(project, containment=containment, signal_kind=all_safety)

    assert {w.kind for w in wires} == {"safety"}


# ---------------------------------------------------------------------------
# Containment validation
# ---------------------------------------------------------------------------


def test_containment_cycle_raises_with_path() -> None:
    project = _project()
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


def test_unknown_parent_raises() -> None:
    project = _project()
    containment = {"child": ContainerSpec(label="C", kind="pcb", parent="missing")}
    with pytest.raises(OverviewContainmentError, match="missing"):
        extract(project, containment=containment)


def test_multiple_cabinets_raises() -> None:
    project = _project()
    containment = {
        "a": ContainerSpec(label="A", kind="cabinet"),
        "b": ContainerSpec(label="B", kind="cabinet"),
    }
    with pytest.raises(OverviewContainmentError, match="cabinet"):
        extract(project, containment=containment)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_cabinet_in_containment_terminals_at_root() -> None:
    """No cabinet declared -> terminals at root; field devices still kind-grouped."""
    external = [("M1", "U", Terminal("X02"), "1", "", "")]
    project = _project(external=external)

    units, _ = extract(project, containment={})

    by_id = {u.id: u for u in units}
    assert by_id["X02"].parent is None
    assert by_id["M1"].parent == "<field_other>"


def test_empty_external_connections_returns_containers_only() -> None:
    project = _project()
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units, wires = extract(project, containment=containment)

    assert wires == []
    assert [u.id for u in units] == ["cab"]


def test_empty_project_and_empty_containment() -> None:
    project = _project()

    units, wires = extract(project, containment={})

    assert units == []
    assert wires == []


# ---------------------------------------------------------------------------
# Adapter shape checks
# ---------------------------------------------------------------------------


def test_get_external_connections_raises_when_not_list() -> None:
    project = Project()
    project._external_connections = {"not": "a list"}  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    with pytest.raises(OverviewExtractionError, match="list"):
        extract(project, containment={})


def test_get_terminals_raises_when_not_dict() -> None:
    project = Project()
    project._terminals = ["not a dict"]  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    with pytest.raises(OverviewExtractionError, match="dict"):
        extract(project, containment={})


# ---------------------------------------------------------------------------
# Field-device kind classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "expected_kind"),
    [
        ("400V Main", "power"),
        ("230V Em", "power"),
        ("PU-01-CX", "motors"),
        ("F-01-VA", "motors"),
        ("XV-01-CX", "valves"),
        ("FV-01-PA", "valves"),
        ("S1", "switches"),
        ("S10-PB", "switches"),
        ("G-01-PA", "sensors"),
        ("LT-01-RX", "sensors"),
        ("PT-01-CX", "sensors"),
        ("TT-02-CX", "sensors"),
        ("UNKNOWN_TAG", "other"),
    ],
)
def test_field_kind_classification(tag: str, expected_kind: str) -> None:
    external = [(tag, "1", Terminal("X01"), "1", "", "")]
    project = _project(external=external)

    units, _ = extract(project, containment={})

    device = next(u for u in units if u.id == tag)
    assert device.parent == f"<field_{expected_kind}>"


def test_only_used_kinds_emit_containers() -> None:
    """Don't synthesise empty kind clusters."""
    external = [("S1", "1", Terminal("X05"), "1", "", "")]  # only switches
    project = _project(external=external)

    units, _ = extract(project, containment={})

    container_ids = {u.id for u in units if u.is_container}
    assert container_ids == {"<field_switches>"}


def test_kind_containers_in_render_order() -> None:
    """Power -> motors -> valves -> switches -> sensors -> other (deterministic)."""
    external = [
        ("PT-01", "Sig+", Terminal("X10"), "1", "", ""),  # sensor
        ("S1", "1", Terminal("X05"), "1", "", ""),  # switch
        ("400V Main", "L1", Terminal("X01"), "1", "", ""),  # power
        ("PU-01", "U", Terminal("X02"), "1", "", ""),  # motor
    ]
    project = _project(external=external)

    units, _ = extract(project, containment={})

    container_order = [u.id for u in units if u.is_container]
    # Sort key in extract() puts is_container=True units after their parent ordering;
    # check that the canonical render order is preserved.
    assert container_order.index("<field_power>") < container_order.index(
        "<field_motors>"
    )
    assert container_order.index("<field_motors>") < container_order.index(
        "<field_switches>"
    )
    assert container_order.index("<field_switches>") < container_order.index(
        "<field_sensors>"
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_ordering() -> None:
    external = [
        ("M2", "V", Terminal("X02"), "2", "", ""),
        ("M1", "U", Terminal("X02"), "1", "", ""),
    ]
    project = _project(external=external)
    containment = {"cab": ContainerSpec(label="C", kind="cabinet")}

    units1, wires1 = extract(project, containment=containment)
    units2, wires2 = extract(project, containment=containment)

    assert [u.id for u in units1] == [u.id for u in units2]
    assert [w.from_port for w in wires1] == [w.from_port for w in wires2]
    # Field devices share parent=None and sort by id.
    field_ids = [u.id for u in units1 if u.kind == "field_device"]
    assert field_ids == ["M1", "M2"]
