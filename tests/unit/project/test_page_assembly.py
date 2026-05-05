"""Tests for Project page-assembly methods.

Targets the survivors clustered in:
- ``Project.add_circuit`` / ``Project.circuit``
- ``Project.add_pcb``
- ``Project.page``
- ``Project._add_page_to_compiler``
- ``Project.add_pid`` / ``Project.pid_page``
- ``Project.set_catalog`` / ``Project.set_cable_registry``
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from schematika.electrical import Terminal
from schematika.electrical.builder import BuildResult
from schematika.electrical.system.system import Circuit
from schematika.pcb.model import (
    ConnectorBlock,
    Page,
    PCBBuildResult,
)
from schematika.project import Project, _PageDef


def _trivial_builder():
    def _b(state, **_kw):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

    return _b


# ---------------------------------------------------------------------------
# add_circuit / circuit registration -- internal state shape
# ---------------------------------------------------------------------------


def test_add_circuit_default_count_is_one():
    p = Project()
    p.add_circuit("a", _trivial_builder())
    assert p._circuit_defs[0].count == 1


def test_add_circuit_factory_is_custom():
    p = Project()
    p.add_circuit("a", _trivial_builder())
    assert p._circuit_defs[0].factory == "custom"


def test_add_circuit_appends_in_order():
    p = Project()
    p.add_circuit("a", _trivial_builder())
    p.add_circuit("b", _trivial_builder())
    p.add_circuit("c", _trivial_builder())
    assert [c.key for c in p._circuit_defs] == ["a", "b", "c"]


def test_add_circuit_kwargs_stored_in_params():
    p = Project()
    p.add_circuit("a", _trivial_builder(), count=4, foo=1, bar="x")
    cdef = p._circuit_defs[0]
    assert cdef.count == 4
    assert cdef.params == {"foo": 1, "bar": "x"}


def test_add_circuit_does_not_set_components():
    """custom-factory circuits never touch the components field."""
    p = Project()
    p.add_circuit("a", _trivial_builder())
    assert p._circuit_defs[0].components is None


# ---------------------------------------------------------------------------
# add_pcb
# ---------------------------------------------------------------------------


def _make_pcb_result():
    state = object()  # unused placeholder

    # Minimal connector blocks with empty pin columns
    # (render_connector_block will iterate but find no slices)
    blocks = (
        ConnectorBlock(
            connector_ref="J1",
            functional_label="Power",
            pin_columns=(),
        ),
        ConnectorBlock(
            connector_ref="J2",
            functional_label="Signal",
            pin_columns=(),
        ),
        ConnectorBlock(
            connector_ref="J3",
            functional_label="Ground",
            pin_columns=(),
        ),
    )

    pages = (
        Page(title="Page 1", placements=(("J1", 0.0), ("J2", 50.0))),
        Page(title="Page 2", placements=(("J3", 0.0),)),
    )
    return PCBBuildResult(state=state, connector_blocks=blocks, pages=pages)


def test_add_pcb_registers_pages_with_titles():
    p = Project()
    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ):
        p.add_pcb(_make_pcb_result())
    titles = [pg.title for pg in p._pages]
    assert titles == ["Page 1", "Page 2"]


def test_add_pcb_multi_column_pages_use_circuit_keys():
    p = Project()
    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ):
        p.add_pcb(_make_pcb_result())
    # One merged circuit per page, keyed as pcb_page_<title>
    assert p._pages[0].circuit_keys == ["pcb_page_Page 1"]
    assert p._pages[1].circuit_keys == ["pcb_page_Page 2"]


def test_add_pcb_returns_self():
    p = Project()
    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ):
        result = p.add_pcb(_make_pcb_result())
    assert result is p


def test_add_pcb_registers_circuits():
    """add_pcb registers one merged circuit per page."""
    p = Project()
    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ):
        p.add_pcb(_make_pcb_result())
    assert len(p._circuit_defs) == 2
    circuit_keys = [c.key for c in p._circuit_defs]
    assert circuit_keys == ["pcb_page_Page 1", "pcb_page_Page 2"]


# ---------------------------------------------------------------------------
# page() — single key vs list
# ---------------------------------------------------------------------------


def test_page_single_key_sets_circuit_key_only():
    p = Project()
    p.page("Title", "key1")
    page = p._pages[0]
    assert page.page_type == "schematic"
    assert page.circuit_key == "key1"
    assert page.circuit_keys is None


def test_page_list_sets_circuit_keys_only():
    p = Project()
    p.page("Combined", ["a", "b", "c"])
    page = p._pages[0]
    assert page.page_type == "schematic"
    assert page.circuit_keys == ["a", "b", "c"]
    # circuit_key is the empty default until merge resolves
    assert page.circuit_key == ""


def test_page_preserves_title():
    p = Project()
    p.page("My Page", "k")
    assert p._pages[0].title == "My Page"


def test_page_appends_in_order():
    p = Project()
    p.page("A", "a")
    p.page("B", "b")
    p.page("C", ["c1", "c2"])
    titles = [pg.title for pg in p._pages]
    assert titles == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# add_pid / pid_page
# ---------------------------------------------------------------------------


def test_add_pid_appends_def():
    def factory(state):
        return None

    p = Project()
    p.add_pid("pid1", factory)
    assert p._pid_defs[0].key == "pid1"
    assert p._pid_defs[0].builder_or_factory is factory


def test_add_pid_returns_self():
    p = Project()
    result = p.add_pid("k", lambda state: None)
    assert result is p


def test_pid_page_registers_pid_page():
    p = Project()
    p.pid_page("Process Diagram", "pid1")
    assert len(p._pages) == 1
    page = p._pages[0]
    assert page.page_type == "pid"
    assert page.title == "Process Diagram"
    assert page.circuit_key == "pid1"


def test_pid_page_returns_self():
    p = Project()
    result = p.pid_page("Title", "k")
    assert result is p


# ---------------------------------------------------------------------------
# set_catalog / set_cable_registry
# ---------------------------------------------------------------------------


def test_set_catalog_stores_value():
    from schematika.catalog.registry import DeviceCatalog

    p = Project()
    cat = DeviceCatalog()
    p.set_catalog(cat)
    assert p._catalog is cat
    assert p.catalog is cat


def test_set_catalog_returns_self():
    from schematika.catalog.registry import DeviceCatalog

    p = Project()
    assert p.set_catalog(DeviceCatalog()) is p


def test_catalog_default_is_none():
    p = Project()
    assert p.catalog is None


def test_set_cable_registry_stores_value():
    from schematika.catalog.cables import CableRegistry

    p = Project()
    reg = CableRegistry()
    p.set_cable_registry(reg)
    assert p._cable_registry is reg
    assert p.cable_registry is reg


def test_set_cable_registry_returns_self():
    from schematika.catalog.cables import CableRegistry

    p = Project()
    assert p.set_cable_registry(CableRegistry()) is p


# ---------------------------------------------------------------------------
# _add_page_to_compiler — pid + bom + cable variants
# ---------------------------------------------------------------------------


def test_add_page_to_compiler_pid_uses_pid_svg_paths():
    p = Project()
    compiler = MagicMock()
    page_def = _PageDef(page_type="pid", title="Process", circuit_key="pid1")
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
        plc_csv_path="",
        pid_svg_paths={"pid1": "/tmp/pid1.svg"},
    )
    compiler.add_schematic_page.assert_called_once_with(
        "Process", "/tmp/pid1.svg", None
    )


def test_add_page_to_compiler_pid_missing_key_no_call():
    p = Project()
    compiler = MagicMock()
    page_def = _PageDef(page_type="pid", title="Missing", circuit_key="absent")
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
        plc_csv_path="",
        pid_svg_paths={},
    )
    compiler.add_schematic_page.assert_not_called()


def test_add_page_to_compiler_bom_report_calls_custom_page():
    p = Project()
    compiler = MagicMock()
    page_def = _PageDef(page_type="bom_report")
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    compiler.add_custom_page.assert_called_once()
    call_args = compiler.add_custom_page.call_args
    assert call_args[0][0] == "Bill of Materials"
    assert "Bill of Materials" in call_args[0][1]  # typst content


def test_add_page_to_compiler_cable_calls_add_cable_pages():
    p = Project()
    compiler = MagicMock()
    cable_entries = [("/tmp/c1.svg", "W001", "Cable 1", "5 m")]
    page_def = _PageDef(page_type="cable", title="Cables", cable_entries=cable_entries)
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    compiler.add_cable_pages.assert_called_once_with(cable_entries)


def test_add_page_to_compiler_cable_no_entries_skipped():
    p = Project()
    compiler = MagicMock()
    page_def = _PageDef(page_type="cable", title="Cables", cable_entries=None)
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    compiler.add_cable_pages.assert_not_called()


def test_add_page_to_compiler_cable_toc_calls_add_cable_toc():
    p = Project()
    compiler = MagicMock()
    toc_entries = [("W001", "Cable 1"), ("W002", "Cable 2")]
    page_def = _PageDef(
        page_type="cable_toc", title="TOC", cable_toc_entries=toc_entries
    )
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    compiler.add_cable_toc.assert_called_once_with(toc_entries)


def test_add_page_to_compiler_cable_toc_no_entries_skipped():
    p = Project()
    compiler = MagicMock()
    page_def = _PageDef(page_type="cable_toc", cable_toc_entries=None)
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    compiler.add_cable_toc.assert_not_called()


def test_add_page_to_compiler_unknown_type_silent():
    """An unrecognized page_type must not raise (silent skip)."""
    p = Project()
    compiler = MagicMock()
    page_def = _PageDef(page_type="not_a_real_type")
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    # No method on compiler should be called for an unknown type
    assert not compiler.method_calls


def test_add_page_to_compiler_terminal_report_excludes_references():
    p = Project()
    p.terminals(
        Terminal("X1", title="Real"),
        Terminal("PLC:DO", title="Reference", reference=True),
    )
    compiler = MagicMock()
    page_def = _PageDef(page_type="terminal_report")
    p._add_page_to_compiler(
        compiler,
        page_def,
        svg_paths={},
        csv_paths={},
        system_csv_path="/tmp/sys.csv",
    )
    titles = compiler.add_terminal_report.call_args[0][1]
    assert "X1" in titles
    assert "PLC:DO" not in titles


# ---------------------------------------------------------------------------
# Setters / chaining sanity
# ---------------------------------------------------------------------------


def test_internal_wiring_appends():
    p = Project()
    row1 = ("DEV1", "p", "X1", "1", "DEV2", "q")
    row2 = ("DEV3", "p", "X1", "2", "DEV4", "q")
    p.internal_wiring([row1])
    p.internal_wiring([row2])
    assert p._terminal_only_connections == [row1, row2]


def test_inter_device_cables_appends():
    p = Project()
    p.inter_device_cables(["cable1"])
    p.inter_device_cables(["cable2", "cable3"])
    assert p._inter_device_defs == ["cable1", "cable2", "cable3"]


def test_inter_device_cables_returns_self():
    p = Project()
    assert p.inter_device_cables([]) is p


def test_internal_wiring_returns_self():
    """internal_wiring returns the project for chaining."""
    p = Project()
    result = p.internal_wiring([])
    assert result is p


def test_add_field_devices_appends_to_external_connections():
    p = Project()
    rows = [("DEV", "p", "X1", "1", "PLC:DI", "")]
    p.add_field_devices(rows)
    assert p._external_connections == rows


def test_add_field_devices_returns_self():
    p = Project()
    assert p.add_field_devices([]) is p


def test_export_wire_labels_returns_self_and_stores():
    p = Project()
    result = p.export_wire_labels("/tmp/labels.csv", titles={"a": "A"})
    assert result is p
    assert p._wire_label_export == ("/tmp/labels.csv", {"a": "A"})


def test_export_taglist_returns_self_and_stores():
    p = Project()
    result = p.export_taglist("/tmp/tags.csv")
    assert result is p
    assert p._taglist_export == "/tmp/tags.csv"


def test_bom_report_returns_self_and_appends_page():
    p = Project()
    result = p.bom_report()
    assert result is p
    assert p._pages[-1].page_type == "bom_report"


def test_init_initializes_all_collections_empty():
    p = Project()
    assert p._pid_defs == []
    assert p._pid_results == {}
    assert p._inter_device_defs == []
    assert p._field_device_defs == []
    assert p._terminal_only_connections == []
    assert p._wire_label_export is None
    assert p._taglist_export is None
    assert p._bom_csv_export is None
    assert p._bom_excel_export is None
