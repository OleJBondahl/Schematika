"""Pin exact values of page-size / slot-size constants and enum strings.

Wave 3 mutation targets: mutants 1, 2, 4, 5 (page sizes), 7, 9 (slot/column),
11, 13, 15 (enum string values), 222 (column_spacing_mm default).
"""

import inspect

from schematika.pcb.builder import (
    A3_LANDSCAPE,
    A4_LANDSCAPE,
    DEFAULT_COLUMN_WIDTH,
    DEFAULT_SYMBOL_SLOT_HEIGHT,
    _NetKind,
    build,
)


class TestPageSizeConstants:
    def test_a4_landscape_is_297_by_210(self) -> None:
        assert A4_LANDSCAPE == (297.0, 210.0)

    def test_a3_landscape_is_420_by_297(self) -> None:
        assert A3_LANDSCAPE == (420.0, 297.0)

    def test_a4_width_strictly_297(self) -> None:
        assert A4_LANDSCAPE[0] == 297.0

    def test_a4_height_strictly_210(self) -> None:
        assert A4_LANDSCAPE[1] == 210.0

    def test_a3_width_strictly_420(self) -> None:
        assert A3_LANDSCAPE[0] == 420.0

    def test_a3_height_strictly_297(self) -> None:
        assert A3_LANDSCAPE[1] == 297.0


class TestSlotSizeConstants:
    def test_default_slot_height_is_40(self) -> None:
        assert DEFAULT_SYMBOL_SLOT_HEIGHT == 40.0

    def test_default_column_width_is_50(self) -> None:
        assert DEFAULT_COLUMN_WIDTH == 50.0


class TestNetKindEnumValues:
    def test_chain_value(self) -> None:
        assert _NetKind.CHAIN.value == "CHAIN"

    def test_label_value(self) -> None:
        assert _NetKind.LABEL.value == "LABEL"

    def test_power_value(self) -> None:
        assert _NetKind.POWER.value == "POWER"

    def test_all_three_members_present(self) -> None:
        assert {m.name for m in _NetKind} == {"CHAIN", "LABEL", "POWER"}


class TestBuildDefaults:
    def test_build_column_spacing_default_is_40(self) -> None:
        """Mutant 222: column_spacing_mm default flipped 40.0 → 41.0."""
        sig = inspect.signature(build)
        assert sig.parameters["column_spacing_mm"].default == 40.0

    def test_build_page_size_default_is_a3_landscape(self) -> None:
        sig = inspect.signature(build)
        assert sig.parameters["page_size"].default == (420.0, 297.0)
