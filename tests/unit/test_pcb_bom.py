"""pcb.bom: designator grouping/sort + supplier-annotated BOM rows, decoupled from data."""

from dataclasses import dataclass

import pytest

from schematika.pcb.bom import SupplierInfo, build_bom_rows, group_parts, write_bom_xlsx


@dataclass
class _Part:
    ref: str
    value: str
    footprint: str


def test_group_parts_groups_by_footprint_and_value():
    parts = [
        _Part("R1", "10k", "R_0603"),
        _Part("R2", "10k", "R_0603"),
        _Part("C1", "100n", "C_0603"),
    ]

    groups = group_parts(parts)

    assert groups[("R_0603", "10k")] == ["R1", "R2"]
    assert groups[("C_0603", "100n")] == ["C1"]


def test_build_bom_rows_sorts_designators_naturally():
    parts = [_Part("R10", "10k", "R_0603"), _Part("R2", "10k", "R_0603")]
    lookup = {"R_0603": SupplierInfo("Yageo", "RC0603", "Mouser", "603-RC0603")}

    rows = build_bom_rows(parts, lookup)

    assert rows[0].designators == ("R2", "R10")


def test_build_bom_rows_strips_library_prefix():
    parts = [_Part("J1", "conn", "Zen Footprints:JST_XH_2")]
    lookup = {
        "Zen Footprints:JST_XH_2": SupplierInfo("JST", "XH-2", "Digikey", "455-1234")
    }

    rows = build_bom_rows(parts, lookup, footprint_library_prefix="Zen Footprints:")

    assert rows[0].footprint == "JST_XH_2"


def test_build_bom_rows_raises_on_missing_supplier_entry():
    parts = [_Part("R1", "10k", "R_0603")]

    with pytest.raises(KeyError):
        build_bom_rows(parts, {})


def test_write_bom_xlsx_writes_a_workbook(tmp_path):
    rows = build_bom_rows(
        [_Part("R1", "10k", "R_0603")],
        {"R_0603": SupplierInfo("Yageo", "RC0603", "Mouser", "603-RC0603")},
    )
    path = tmp_path / "bom.xlsx"

    write_bom_xlsx(rows, path)

    assert path.exists()
