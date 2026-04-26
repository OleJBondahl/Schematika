"""Tests for Project P&ID integration (set_catalog, add_pid, pid_page)."""

import pytest

from schematika.catalog import DeviceCatalog
from schematika.core.options import EquipmentConfig, EquipmentPlacement
from schematika.pid.builder import PIDBuilder
from schematika.pid.symbols import centrifugal_pump, gate_valve, tank
from schematika.project import Project


def test_project_set_catalog():
    project = Project()
    catalog = DeviceCatalog()
    project.set_catalog(catalog)
    assert project.catalog is catalog


def test_project_catalog_default_none():
    project = Project()
    assert project.catalog is None


def test_project_set_catalog_returns_self():
    project = Project()
    catalog = DeviceCatalog()
    result = project.set_catalog(catalog)
    assert result is project


def test_project_add_pid_with_builder():
    project = Project()
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    project.add_pid("cooling", builder)
    assert len(project._pid_defs) == 1
    assert project._pid_defs[0].key == "cooling"


def test_project_add_pid_returns_self():
    project = Project()
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    result = project.add_pid("cooling", builder)
    assert result is project


def test_project_add_pid_with_factory():
    def cooling_pid(state):
        builder = PIDBuilder(state)
        builder.add_equipment(
            "pump",
            config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
            placement=EquipmentPlacement(x=50, y=50),
        )
        return builder.build(state=state)

    project = Project()
    project.add_pid("cooling", cooling_pid)
    assert len(project._pid_defs) == 1
    assert project._pid_defs[0].key == "cooling"


def test_project_pid_page():
    project = Project()
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    project.add_pid("cooling", builder)
    project.pid_page("Cooling System P&ID", "cooling")

    pid_pages = [p for p in project._pages if p.page_type == "pid"]
    assert len(pid_pages) == 1
    assert pid_pages[0].title == "Cooling System P&ID"
    assert pid_pages[0].circuit_key == "cooling"


def test_project_pid_page_returns_self():
    project = Project()
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    project.add_pid("cooling", builder)
    result = project.pid_page("Cooling System P&ID", "cooling")
    assert result is project


def test_project_build_with_pid_builder():
    """Project._build_all_circuits() executes PIDBuilder definitions."""
    project = Project()
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    builder.add_equipment(
        "tank",
        config=EquipmentConfig(factory=tank, tag_prefix="T"),
        placement=EquipmentPlacement(
            relative_to="pump", from_port="outlet", to_port="inlet"
        ),
    )
    builder.pipe("pump", "tank")
    project.add_pid("cooling", builder)
    project.pid_page("Cooling P&ID", "cooling")

    project._build_all_circuits()

    assert "cooling" in project._pid_results
    result = project._pid_results["cooling"]
    assert result.diagram is not None
    assert "pump" in result.equipment_map
    assert "tank" in result.equipment_map


def test_project_build_with_pid_factory():
    """Project._build_all_circuits() executes factory callables."""

    def cooling_pid(state):
        builder = PIDBuilder(state)
        builder.add_equipment(
            "pump",
            config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
            placement=EquipmentPlacement(x=50, y=50),
        )
        return builder.build(state=state)

    project = Project()
    project.add_pid("cooling", cooling_pid)

    project._build_all_circuits()

    assert "cooling" in project._pid_results
    result = project._pid_results["cooling"]
    assert result.equipment_map == {"pump": "P1"}


def test_project_add_pid_invalid_type():
    """add_pid with a non-callable, non-PIDBuilder raises TypeError on build."""
    project = Project()
    project.add_pid("bad", "not_a_builder")  # registered without error

    with pytest.raises(TypeError, match="PIDBuilder"):
        project._build_all_circuits()


def test_project_multiple_pid_diagrams():
    """Multiple P&ID diagrams can be registered and built."""
    project = Project()

    b1 = PIDBuilder()
    b1.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    project.add_pid("cooling", b1)

    b2 = PIDBuilder()
    b2.add_equipment(
        "valve",
        config=EquipmentConfig(factory=gate_valve, tag_prefix="V"),
        placement=EquipmentPlacement(x=100, y=100),
    )
    project.add_pid("utility", b2)

    project._build_all_circuits()

    assert "cooling" in project._pid_results
    assert "utility" in project._pid_results


def test_project_pid_state_threaded():
    """P&ID tag counters advance correctly across multiple diagrams."""
    project = Project()

    b1 = PIDBuilder()
    b1.add_equipment(
        "pump1",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=0, y=0),
    )
    project.add_pid("diagram1", b1)

    b2 = PIDBuilder()
    b2.add_equipment(
        "pump2",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=0, y=0),
    )
    project.add_pid("diagram2", b2)

    project._build_all_circuits()

    tag1 = project._pid_results["diagram1"].equipment_map["pump1"]
    tag2 = project._pid_results["diagram2"].equipment_map["pump2"]
    assert tag1 == "P1"
    assert tag2 == "P2"


def test_project_render_pid_svgs(tmp_path):
    """_render_pid_svgs writes SVG files for each P&ID diagram."""
    project = Project()
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    project.add_pid("cooling", builder)

    project._build_all_circuits()
    pid_svg_paths = project._render_pid_svgs(str(tmp_path))

    assert "cooling" in pid_svg_paths
    svg_path = pid_svg_paths["cooling"]
    assert svg_path.endswith("pid_cooling.svg")
    assert (tmp_path / "pid_cooling.svg").exists()


def test_project_mixed_electrical_and_pid():
    """Project supports both electrical circuits and P&ID diagrams."""
    project = Project()

    # Add P&ID
    builder = PIDBuilder()
    builder.add_equipment(
        "pump",
        config=EquipmentConfig(factory=centrifugal_pump, tag_prefix="P"),
        placement=EquipmentPlacement(x=50, y=50),
    )
    project.add_pid("cooling", builder)
    project.pid_page("Cooling P&ID", "cooling")

    project._build_all_circuits()

    assert "cooling" in project._pid_results
    pid_pages = [p for p in project._pages if p.page_type == "pid"]
    assert len(pid_pages) == 1
