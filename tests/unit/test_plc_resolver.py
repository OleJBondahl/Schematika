"""
Tests for the plc_resolver module.

Covers PlcDesignation, PlcModuleType, PlcRack, resolve_plc_references,
extract_plc_connections_from_registry, generate_plc_report_rows, and
natural_sort_key.
"""

from __future__ import annotations

import dataclasses

import pytest

from schematika.electrical.plc_resolver import (
    PlcDesignation,
    PlcModuleType,
    PlcRack,
    extract_plc_connections_from_registry,
    generate_plc_report_rows,
    resolve_plc_references,
)
from schematika.electrical.utils.utils import natural_sort_key

# ---------------------------------------------------------------------------
# Sample module types shared across tests
# ---------------------------------------------------------------------------

RTD_MODULE = PlcModuleType("750-461", "RTD", 2, ("+R", "RL", "-R"))
MA_MODULE = PlcModuleType("750-452", "4-20mA", 4, ("Sig", "GND"))
DI_MODULE = PlcModuleType("750-430", "DI", 8, ("",))
DO_MODULE = PlcModuleType("750-530", "DO", 8, ("",))


def make_small_rack() -> PlcRack:
    """Return a small test rack with one module of each type."""
    return [
        ("RTD1", RTD_MODULE),
        ("AI1", MA_MODULE),
        ("DI1", DI_MODULE),
        ("DO1", DO_MODULE),
    ]


# ---------------------------------------------------------------------------
# natural_sort_key
# ---------------------------------------------------------------------------


class TestNaturalSortKey:
    def test_orders_numeric_suffixes(self):
        tags = ["K10", "K2", "K1"]
        result = sorted(tags, key=natural_sort_key)
        assert result == ["K1", "K2", "K10"]

    def test_pure_numbers(self):
        tags = ["10", "2", "1"]
        result = sorted(tags, key=natural_sort_key)
        assert result == ["1", "2", "10"]

    def test_mixed_prefix(self):
        tags = ["DI10", "DI2", "RTD1"]
        result = sorted(tags, key=natural_sort_key)
        assert result == ["DI2", "DI10", "RTD1"]

    def test_no_numbers(self):
        tags = ["beta", "alpha", "gamma"]
        result = sorted(tags, key=natural_sort_key)
        assert result == ["alpha", "beta", "gamma"]

    def test_single_item(self):
        assert natural_sort_key("K1") == ["K", 1, ""]

    def test_empty_string(self):
        assert natural_sort_key("") == [""]

    def test_exported_from_utils(self):
        """natural_sort_key is importable from utils.utils."""
        from schematika.electrical.utils.utils import natural_sort_key as nsk

        assert nsk("K10") == natural_sort_key("K10")

    def test_exported_from_package(self):
        """natural_sort_key is importable from the top-level package."""
        from schematika.electrical import natural_sort_key as pkg_nsk

        assert pkg_nsk("K10") == natural_sort_key("K10")


# ---------------------------------------------------------------------------
# PlcModuleType
# ---------------------------------------------------------------------------


class TestPlcModuleType:
    def test_basic_fields(self):
        mod = PlcModuleType("750-461", "RTD", 2, ("+R", "RL", "-R"))
        assert mod.mpn == "750-461"
        assert mod.signal_type == "RTD"
        assert mod.channels == 2
        assert mod.pins_per_channel == ("+R", "RL", "-R")

    def test_frozen(self):
        mod = PlcModuleType("", "DI", 8, ("",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            mod.channels = 4  # type: ignore[misc]

    def test_equality(self):
        a = PlcModuleType("mpn", "DI", 8, ("",))
        b = PlcModuleType("mpn", "DI", 8, ("",))
        assert a == b


# ---------------------------------------------------------------------------
# PlcDesignation.parse()  # noqa: ERA001
# ---------------------------------------------------------------------------


class TestPlcDesignationParse:
    def test_generic_single_pin(self):
        d = PlcDesignation.parse("PLC:DO")
        assert d is not None
        assert d.type == "DO"
        assert d.instance is None
        assert d.signal is None

    def test_generic_with_signal(self):
        d = PlcDesignation.parse("PLC:RTD:+R")
        assert d is not None
        assert d.type == "RTD"
        assert d.instance is None
        assert d.signal == "+R"

    def test_specific_instance(self):
        d = PlcDesignation.parse("PLC:DO1")
        assert d is not None
        assert d.type == "DO"
        assert d.instance == 1
        assert d.signal is None

    def test_specific_instance_two_digits(self):
        d = PlcDesignation.parse("PLC:DI12")
        assert d is not None
        assert d.type == "DI"
        assert d.instance == 12
        assert d.signal is None

    def test_ai_with_signal(self):
        d = PlcDesignation.parse("PLC:AI:Sig")
        assert d is not None
        assert d.type == "AI"
        assert d.instance is None
        assert d.signal == "Sig"

    def test_non_plc_tag_returns_none(self):
        assert PlcDesignation.parse("X100") is None
        assert PlcDesignation.parse("K1") is None
        assert PlcDesignation.parse("") is None
        assert PlcDesignation.parse("PLCX:DO") is None

    def test_plc_prefix_exact(self):
        """Strings starting with 'PLC:' but no type should still parse."""
        d = PlcDesignation.parse("PLC:AI")
        assert d is not None
        assert d.type == "AI"

    def test_frozen(self):
        d = PlcDesignation.parse("PLC:DO")
        assert d is not None
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.type = "DI"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PlcDesignation.__str__()  # noqa: ERA001
# ---------------------------------------------------------------------------


class TestPlcDesignationStr:
    def test_generic_no_instance(self):
        d = PlcDesignation(type="DO", instance=None, signal=None)
        assert str(d) == "PLC:DO"

    def test_specific_instance(self):
        d = PlcDesignation(type="DO", instance=1, signal=None)
        assert str(d) == "PLC:DO1"

    def test_instance_two_digits(self):
        d = PlcDesignation(type="DI", instance=12, signal=None)
        assert str(d) == "PLC:DI12"

    def test_signal_not_included_in_str(self):
        """__str__ only produces the base designation, not the signal suffix."""
        d = PlcDesignation(type="RTD", instance=None, signal="+R")
        assert str(d) == "PLC:RTD"

    def test_roundtrip_generic(self):
        d = PlcDesignation.parse("PLC:DI")
        assert d is not None
        assert str(d) == "PLC:DI"

    def test_roundtrip_specific(self):
        d = PlcDesignation.parse("PLC:DO2")
        assert d is not None
        assert str(d) == "PLC:DO2"

    def test_str_with_instance_zero(self):
        d = PlcDesignation(type="DO", instance=0, signal=None)
        assert str(d) == "PLC:DO0"


# ---------------------------------------------------------------------------
# resolve_plc_references()  — single-pin references (DI, DO)
# ---------------------------------------------------------------------------


class TestResolvePlcReferencesSinglePin:
    def test_resolves_di_reference(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        connections = [
            ("SW-01", "Signal", "X100", "1", "PLC:DI", ""),
        ]
        result = resolve_plc_references(connections, rack)
        assert len(result) == 1
        row = result[0]
        assert row[4] == "PLC:DI1"
        assert row[5] == "1"  # channel 1, no suffix

    def test_resolves_multiple_di_references_in_order(self):
        """Three DI connections across two modules, ordered by terminal pin."""
        rack: PlcRack = [("DI1", DI_MODULE)]
        connections = [
            ("SW-03", "Signal", "X100", "3", "PLC:DI", ""),
            ("SW-01", "Signal", "X100", "1", "PLC:DI", ""),
            ("SW-02", "Signal", "X100", "2", "PLC:DI", ""),
        ]
        result = resolve_plc_references(connections, rack)
        # Should be sorted by terminal pin: 1, 2, 3 → DI1.1, DI1.2, DI1.3
        plc_pins = [r[5] for r in result]
        assert plc_pins == ["1", "2", "3"]
        plc_modules = [r[4] for r in result]
        assert all(m == "PLC:DI1" for m in plc_modules)

    def test_non_plc_connections_pass_through(self):
        rack = make_small_rack()
        connections = [
            ("M1", "L1", "X100", "1", "MOTOR", ""),
            ("SW-01", "Signal", "X100", "2", "PLC:DI", ""),
        ]
        result = resolve_plc_references(connections, rack)
        assert len(result) == 2
        # Non-PLC row preserved unchanged
        assert result[0] == ("M1", "L1", "X100", "1", "MOTOR", "")

    def test_already_specific_designation_passes_through(self):
        rack = make_small_rack()
        connections = [
            ("SW-01", "Signal", "X100", "1", "PLC:DI1", "1"),
        ]
        result = resolve_plc_references(connections, rack)
        assert len(result) == 1
        assert result[0] == connections[0]

    def test_unknown_plc_type_passes_through(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        connections = [
            ("SW-01", "Signal", "X100", "1", "PLC:TC", ""),
        ]
        result = resolve_plc_references(connections, rack)
        # No matching module — row passes through unchanged
        assert len(result) == 1
        assert result[0] == connections[0]

    def test_empty_connections_returns_empty(self):
        rack = make_small_rack()
        assert resolve_plc_references([], rack) == []


# ---------------------------------------------------------------------------
# resolve_plc_references()  — multi-pin references (RTD, 4-20mA)
# ---------------------------------------------------------------------------


class TestResolvePlcReferencesMultiPin:
    def test_resolves_rtd_pins_same_channel(self):
        rack: PlcRack = [("RTD1", RTD_MODULE)]
        connections = [
            ("TT-01", "R+", "X200", "1", "PLC:RTD:+R", ""),
            ("TT-01", "RL", "X200", "2", "PLC:RTD:RL", ""),
            ("TT-01", "R-", "X200", "3", "PLC:RTD:-R", ""),
        ]
        result = resolve_plc_references(connections, rack)
        assert len(result) == 3
        # All pins for TT-01 should land on channel 1 of RTD1
        for row in result:
            assert row[4] == "PLC:RTD1"
            assert row[5].endswith("1")  # "+R1", "RL1", "-R1"

    def test_resolves_4_20ma_two_devices(self):
        rack: PlcRack = [("AI1", MA_MODULE)]
        connections = [
            ("PT-01", "Sig+", "X200", "1", "PLC:AI:Sig", ""),
            ("PT-01", "GND", "X200", "2", "PLC:AI:GND", ""),
            ("PT-02", "Sig+", "X200", "3", "PLC:AI:Sig", ""),
            ("PT-02", "GND", "X200", "4", "PLC:AI:GND", ""),
        ]
        result = resolve_plc_references(connections, rack)
        assert len(result) == 4
        pt01_rows = [r for r in result if r[0] == "PT-01"]
        pt02_rows = [r for r in result if r[0] == "PT-02"]
        # PT-01 → channel 1, PT-02 → channel 2
        assert all(r[5].endswith("1") for r in pt01_rows)
        assert all(r[5].endswith("2") for r in pt02_rows)


# ---------------------------------------------------------------------------
# resolve_plc_references()  — overflow and mixed-suffix edge cases
# ---------------------------------------------------------------------------


class TestResolvePlcReferences:
    def test_overflow_emits_warning(self):
        DI_MODULE_1CH = PlcModuleType("750-430", "DI", 1, ("",))
        rack: PlcRack = [("DI1", DI_MODULE_1CH)]
        connections = [
            ("SW-01", "Signal", "X100", "1", "PLC:DI", ""),
            ("SW-02", "Signal", "X100", "2", "PLC:DI", ""),
        ]
        with pytest.warns(UserWarning, match="DI"):
            result = resolve_plc_references(connections, rack)
        assert len(result) == 1

    def test_mixed_suffix_bucket_emits_warning_and_drops(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        connections = [
            ("SW-01", "Signal", "X100", "1", "PLC:DI:Sig", ""),  # suffixed
            ("SW-02", "Signal", "X100", "2", "PLC:DI", ""),  # unsuffixed
        ]
        with pytest.warns(UserWarning, match="mix"):
            result = resolve_plc_references(connections, rack)
        # Both dropped (cannot route mixed bucket)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# extract_plc_connections_from_registry()  # noqa: ERA001
# ---------------------------------------------------------------------------


class TestExtractPlcConnectionsFromRegistry:
    def _make_state_with_connections(self, connections):
        """Build a GenerationState whose registry contains the given connections."""
        from schematika.electrical import create_initial_state
        from schematika.electrical.system.connection_registry import (
            Connection,
            TerminalRegistry,
            update_registry,
        )

        state = create_initial_state()
        reg = TerminalRegistry(
            tuple(
                Connection(
                    terminal_tag=c["terminal_tag"],
                    terminal_pin=c["terminal_pin"],
                    component_tag=c["component_tag"],
                    component_pin=c["component_pin"],
                    side="bottom",
                )
                for c in connections
            )
        )
        return update_registry(state, reg)

    def test_extracts_di_from_registry(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        state = self._make_state_with_connections(
            [
                {
                    "terminal_tag": "PLC:DI",
                    "terminal_pin": "1",
                    "component_tag": "SW-01",
                    "component_pin": "Signal",
                },
            ]
        )
        result = extract_plc_connections_from_registry(state, rack)
        assert len(result) == 1
        assert result[0][4] == "PLC:DI1"

    def test_skips_used_channels(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        # Channel 1 already occupied by existing connections
        existing: list = [
            ("SW-EXT", "Signal", "X100", "1", "PLC:DI1", "1"),
        ]
        state = self._make_state_with_connections(
            [
                {
                    "terminal_tag": "PLC:DI",
                    "terminal_pin": "1",
                    "component_tag": "SW-01",
                    "component_pin": "Signal",
                },
            ]
        )
        result = extract_plc_connections_from_registry(
            state, rack, existing_connections=existing
        )
        assert len(result) == 1
        # Should be assigned to channel 2 (channel 1 is used)
        assert result[0][5] == "2"

    def test_extracts_multi_pin_from_registry(self):
        rack: PlcRack = [("RTD1", RTD_MODULE)]
        state = self._make_state_with_connections(
            [
                {
                    "terminal_tag": "PLC:RTD:+R",
                    "terminal_pin": "1",
                    "component_tag": "TT-01",
                    "component_pin": "R+",
                },
                {
                    "terminal_tag": "PLC:RTD:RL",
                    "terminal_pin": "2",
                    "component_tag": "TT-01",
                    "component_pin": "RL",
                },
                {
                    "terminal_tag": "PLC:RTD:-R",
                    "terminal_pin": "3",
                    "component_tag": "TT-01",
                    "component_pin": "R-",
                },
            ]
        )
        result = extract_plc_connections_from_registry(state, rack)
        assert len(result) == 3
        for row in result:
            assert row[4] == "PLC:RTD1"

    def test_empty_registry_returns_empty(self):
        rack = make_small_rack()
        state = self._make_state_with_connections([])
        result = extract_plc_connections_from_registry(state, rack)
        assert result == []

    def test_non_plc_registry_connections_ignored(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        state = self._make_state_with_connections(
            [
                {
                    "terminal_tag": "X100",
                    "terminal_pin": "1",
                    "component_tag": "F1",
                    "component_pin": "2",
                },
            ]
        )
        result = extract_plc_connections_from_registry(state, rack)
        assert result == []


# ---------------------------------------------------------------------------
# generate_plc_report_rows()  # noqa: ERA001
# ---------------------------------------------------------------------------


class TestGeneratePlcReportRows:
    def test_empty_connections_produces_all_empty_rows(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        rows = generate_plc_report_rows([], rack)
        # DI1 has 8 channels x 1 pin = 8 rows
        assert len(rows) == 8
        for row in rows:
            module, mpn, _pin, comp, _comp_pin, terminal = row
            assert module == "DI1"
            assert mpn == DI_MODULE.mpn
            assert comp == ""
            assert terminal == ""

    def test_matched_connection_fills_row(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        connections = [
            ("SW-01", "Signal", "X100", "3", "PLC:DI1", "1"),
        ]
        rows = generate_plc_report_rows(connections, rack)
        filled = [r for r in rows if r[3] != ""]
        assert len(filled) == 1
        module, _mpn, pin, comp, comp_pin, terminal = filled[0]
        assert module == "DI1"
        assert pin == "1"
        assert comp == "SW-01"
        assert comp_pin == "Signal"
        assert terminal == "X100:3"

    def test_rtd_module_report(self):
        rack: PlcRack = [("RTD1", RTD_MODULE)]
        connections = [
            ("TT-01", "R+", "X200", "1", "PLC:RTD1", "+R1"),
            ("TT-01", "RL", "X200", "2", "PLC:RTD1", "RL1"),
            ("TT-01", "R-", "X200", "3", "PLC:RTD1", "-R1"),
        ]
        rows = generate_plc_report_rows(connections, rack)
        # RTD1: 2 channels x 3 pins = 6 rows total
        assert len(rows) == 6
        # First 3 rows (channel 1) should be filled
        filled = rows[:3]
        assert all(r[3] == "TT-01" for r in filled)

    def test_multiple_modules_in_rack(self):
        rack: PlcRack = [("DI1", DI_MODULE), ("DO1", DO_MODULE)]
        rows = generate_plc_report_rows([], rack)
        # 8 + 8 = 16 rows
        assert len(rows) == 16
        di_rows = [r for r in rows if r[0] == "DI1"]
        do_rows = [r for r in rows if r[0] == "DO1"]
        assert len(di_rows) == 8
        assert len(do_rows) == 8

    def test_terminal_string_format_with_empty_terminal(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        # Terminal is empty string — should produce empty terminal_str
        connections = [
            ("SW-01", "Signal", "", "", "PLC:DI1", "1"),
        ]
        rows = generate_plc_report_rows(connections, rack)
        filled = [r for r in rows if r[3] != ""]
        assert len(filled) == 1
        assert filled[0][5] == ""  # empty terminal

    def test_report_rows_are_6_tuples(self):
        rack: PlcRack = [("DI1", DI_MODULE)]
        rows = generate_plc_report_rows([], rack)
        for row in rows:
            assert len(row) == 6
            assert all(isinstance(field, str) for field in row)

    def test_pin_labels_correct_for_rtd(self):
        rack: PlcRack = [("RTD1", RTD_MODULE)]
        rows = generate_plc_report_rows([], rack)
        # Expected pins: +R1, RL1, -R1, +R2, RL2, -R2
        expected_pins = ["+R1", "RL1", "-R1", "+R2", "RL2", "-R2"]
        actual_pins = [r[2] for r in rows]
        assert actual_pins == expected_pins

    def test_public_api_import(self):
        """generate_plc_report_rows is importable from top-level package."""
        from schematika.electrical import generate_plc_report_rows as fn

        assert callable(fn)


# ---------------------------------------------------------------------------
# Public API imports
# ---------------------------------------------------------------------------


class TestPublicApiImports:
    def test_plc_designation_importable_from_package(self):
        from schematika.electrical import PlcDesignation as PD

        assert PD is PlcDesignation

    def test_plc_module_type_importable_from_package(self):
        from schematika.electrical import PlcModuleType as PMT

        assert PMT is PlcModuleType

    def test_plc_rack_importable_from_package(self):
        from schematika.electrical import PlcRack as PR

        assert PR is PlcRack

    def test_resolve_plc_references_importable_from_package(self):
        from schematika.electrical import resolve_plc_references as fn

        assert fn is resolve_plc_references

    def test_extract_plc_connections_importable_from_package(self):
        from schematika.electrical import (
            extract_plc_connections_from_registry as fn,
        )

        assert fn is extract_plc_connections_from_registry

    def test_plc_mapper_removed(self):
        """PlcMapper is no longer exported from the package."""
        import schematika.electrical

        assert not hasattr(schematika.electrical, "PlcMapper")
