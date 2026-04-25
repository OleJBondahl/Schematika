"""
Tests for schematika.utils.export_utils.

Covers the terminal CSV merge/sort utilities:
- _terminal_pin_sort_key  (natural sort ordering)
- _merge_terminal_rows    (duplicate row merging)
- merge_terminal_csv      (full round-trip file operation)
"""

import csv
import tempfile
from pathlib import Path

import pytest

from schematika.electrical.utils.export_utils import (
    _merge_terminal_rows,
    _terminal_pin_sort_key,
    merge_terminal_csv,
)

# ---------------------------------------------------------------------------
# _terminal_pin_sort_key
# ---------------------------------------------------------------------------


class TestTerminalPinSortKey:
    """Tests for the natural sort key function."""

    def test_numeric_ordering(self):
        """Numeric pins sort numerically, not lexicographically."""
        pins = ["10", "2", "1", "20", "3"]
        result = sorted(pins, key=_terminal_pin_sort_key)
        assert result == ["1", "2", "3", "10", "20"]

    def test_prefixed_pins(self):
        """Prefixed pins like 'L1:1' sort by prefix then number."""
        pins = ["L1:10", "L1:2", "L1:1", "L2:1"]
        result = sorted(pins, key=_terminal_pin_sort_key)
        assert result == ["L1:1", "L1:2", "L1:10", "L2:1"]

    def test_mixed_numeric_and_prefixed(self):
        """Numeric pins sort before prefixed pins (letters come after digits)."""
        pins = ["L1:1", "2", "1", "L1:2"]
        result = sorted(pins, key=_terminal_pin_sort_key)
        # "1" and "2" start with digits; "L1:..." starts with a letter
        # In natural sort, digits < letters, so numeric pins come first
        assert result == ["1", "2", "L1:1", "L1:2"]

    def test_single_pin(self):
        """Single-element list is trivially sorted."""
        assert sorted(["5"], key=_terminal_pin_sort_key) == ["5"]

    def test_empty_string(self):
        """Empty string does not raise."""
        key = _terminal_pin_sort_key("")
        assert isinstance(key, list)

    def test_pure_alpha_pins(self):
        """Purely alphabetic pins sort lexicographically."""
        pins = ["PE", "N", "L"]
        result = sorted(pins, key=_terminal_pin_sort_key)
        assert result == ["L", "N", "PE"]


# ---------------------------------------------------------------------------
# _merge_terminal_rows
# ---------------------------------------------------------------------------


class TestMergeTerminalRows:
    """Tests for merging duplicate terminal pin rows."""

    def test_two_from_entries_one_moved_to_to(self):
        """When two rows both have FROM filled, one is moved to TO."""
        rows = [
            ["F1", "2", "X001", "1", "", "", ""],
            ["EXT1", "+", "X001", "1", "", "", ""],
        ]
        result = _merge_terminal_rows(rows)
        # Last FROM entry stays on FROM side (EXT1), first moves to TO
        assert result[0] == "EXT1"  # Component From
        assert result[1] == "+"  # Pin From
        assert result[2] == "X001"  # Terminal Tag
        assert result[3] == "1"  # Terminal Pin
        assert result[4] == "F1"  # Component To
        assert result[5] == "2"  # Pin To

    def test_from_and_to_already_filled(self):
        """When one row has FROM and the other has TO, they combine naturally."""
        rows = [
            ["F1", "2", "X001", "1", "", "", ""],
            ["", "", "X001", "1", "M1", "U", ""],
        ]
        result = _merge_terminal_rows(rows)
        assert result[0] == "F1"
        assert result[1] == "2"
        assert result[4] == "M1"
        assert result[5] == "U"

    def test_two_to_entries_one_moved_to_from(self):
        """When two rows both have TO filled, one is moved to FROM."""
        rows = [
            ["", "", "X001", "1", "M1", "U", ""],
            ["", "", "X001", "1", "EXT1", "+", ""],
        ]
        result = _merge_terminal_rows(rows)
        # Excess TO entry moves to FROM
        assert result[0] == "M1"  # Component From (moved from TO)
        assert result[1] == "U"  # Pin From
        assert result[4] == "EXT1"  # Component To (first TO stays)
        assert result[5] == "+"  # Pin To

    def test_bridge_preserved(self):
        """Internal bridge value is preserved across merge."""
        rows = [
            ["F1", "2", "X001", "1", "", "", "3"],
            ["EXT1", "+", "X001", "1", "", "", ""],
        ]
        result = _merge_terminal_rows(rows)
        assert result[6] == "3"

    def test_bridge_from_second_row(self):
        """Bridge value from any row is captured."""
        rows = [
            ["F1", "2", "X001", "1", "", "", ""],
            ["EXT1", "+", "X001", "1", "", "", "2"],
        ]
        result = _merge_terminal_rows(rows)
        assert result[6] == "2"

    def test_single_row_passthrough(self):
        """A single row is returned unchanged (7 columns)."""
        # Note: _merge_terminal_rows is only called for len > 1 in practice,
        # but it should still work for a single row.
        rows = [
            ["F1", "2", "X001", "1", "M1", "U", ""],
        ]
        result = _merge_terminal_rows(rows)
        assert result == ["F1", "2", "X001", "1", "M1", "U", ""]

    def test_all_empty_entries(self):
        """Two rows with no component data merge to an empty row."""
        rows = [
            ["", "", "X001", "1", "", "", ""],
            ["", "", "X001", "1", "", "", ""],
        ]
        result = _merge_terminal_rows(rows)
        assert result[0] == ""
        assert result[4] == ""
        assert result[2] == "X001"
        assert result[3] == "1"

    def test_result_always_seven_columns(self):
        """Merged result always has exactly 7 columns."""
        rows = [
            ["F1", "2", "X001", "1", "", ""],
            ["EXT1", "+", "X001", "1", "", ""],
        ]
        result = _merge_terminal_rows(rows)
        assert len(result) == 7


# ---------------------------------------------------------------------------
# merge_terminal_csv (round-trip)
# ---------------------------------------------------------------------------


class TestMergeTerminalCsv:
    """Integration tests for the full CSV merge/sort round-trip."""

    def _write_csv(self, path: str, header: list[str], rows: list[list[str]]) -> None:
        """Helper to write a CSV with header and rows."""
        with Path(path).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    def _read_csv(self, path: str) -> tuple[list[str], list[list[str]]]:
        """Helper to read a CSV returning (header, rows)."""
        with Path(path).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
        return header, rows

    def test_no_duplicates_just_sorts(self):
        """Without duplicates, rows are sorted by tag then pin (contiguous pins — no gap filling)."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        rows = [
            ["F1", "2", "X002", "1", "M1", "U"],
            ["F2", "4", "X001", "3", "M2", "V"],
            ["F3", "6", "X001", "2", "M3", "W"],
            ["F4", "1", "X001", "1", "M4", "U"],
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, rows)
            merge_terminal_csv(tmp_path)
            _, result = self._read_csv(tmp_path)

            # Should be sorted: X001/1, X001/2, X001/3, X002/1
            assert result[0][2] == "X001"
            assert result[0][3] == "1"
            assert result[1][2] == "X001"
            assert result[1][3] == "2"
            assert result[2][2] == "X001"
            assert result[2][3] == "3"
            assert result[3][2] == "X002"
            assert result[3][3] == "1"
        finally:
            Path(tmp_path).unlink()

    def test_duplicates_merged(self):
        """Duplicate (tag, pin) rows are merged into one."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        rows = [
            ["F1", "2", "X001", "1", "", ""],
            ["EXT1", "+", "X001", "1", "", ""],
            ["F2", "4", "X001", "2", "M1", "U"],
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, rows)
            merge_terminal_csv(tmp_path)
            _, result = self._read_csv(tmp_path)

            # Should have 2 rows (the two X001/1 rows merged into one)
            assert len(result) == 2

            # First row: X001 pin 1 (merged)
            assert result[0][2] == "X001"
            assert result[0][3] == "1"
            # Last FROM entry (EXT1) stays on FROM side
            assert result[0][0] == "EXT1"
            assert result[0][1] == "+"
            # First FROM entry (F1) moved to TO side
            assert result[0][4] == "F1"
            assert result[0][5] == "2"

            # Second row: X001 pin 2 (unchanged)
            assert result[1][2] == "X001"
            assert result[1][3] == "2"
        finally:
            Path(tmp_path).unlink()

    def test_bridge_column_preserved(self):
        """The Internal Bridge column survives the merge."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
            "Internal Bridge",
        ]
        rows = [
            ["F1", "2", "X001", "1", "", "", "1"],
            ["EXT1", "+", "X001", "1", "", "", ""],
            ["F2", "4", "X001", "2", "M1", "U", "1"],
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, rows)
            merge_terminal_csv(tmp_path)
            _, result = self._read_csv(tmp_path)

            # Merged row should still have bridge "1"
            assert result[0][6] == "1"
            assert result[1][6] == "1"
        finally:
            Path(tmp_path).unlink()

    def test_prefixed_pins_sorted_correctly(self):
        """Prefixed pins like L1:1 sort naturally (contiguous — no gap filling)."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        rows = [
            ["F1", "2", "X001", "L1:3", "M1", "U"],
            ["F2", "4", "X001", "L1:2", "M2", "V"],
            ["F3", "6", "X001", "L1:1", "M3", "W"],
            ["F4", "1", "X001", "2", "M4", "PE"],
            ["F5", "3", "X001", "1", "M5", "N"],
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, rows)
            merge_terminal_csv(tmp_path)
            _, result = self._read_csv(tmp_path)

            pins = [r[3] for r in result]
            # Numeric pins ("1", "2") sort before prefixed ("L1:1", "L1:2", "L1:3")
            assert pins == ["1", "2", "L1:1", "L1:2", "L1:3"]
        finally:
            Path(tmp_path).unlink()

    def test_empty_csv_no_data_rows(self):
        """A CSV with only a header produces no error."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, [])
            merge_terminal_csv(tmp_path)
            _, result = self._read_csv(tmp_path)
            assert result == []
        finally:
            Path(tmp_path).unlink()

    def test_header_preserved(self):
        """The original header row is preserved after merge/sort."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
            "Internal Bridge",
        ]
        rows = [
            ["F1", "2", "X001", "1", "M1", "U", ""],
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, rows)
            merge_terminal_csv(tmp_path)
            result_header, _ = self._read_csv(tmp_path)
            assert result_header == header
        finally:
            Path(tmp_path).unlink()

    def test_file_not_found(self):
        """Attempting to merge a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            merge_terminal_csv("/nonexistent/path/terminals.csv")

    def test_multiple_terminals_sorted(self):
        """Rows across multiple terminal tags are sorted correctly."""
        header = [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        rows = [
            ["F1", "2", "X003", "1", "M1", "U"],
            ["F2", "4", "X001", "2", "M2", "V"],
            ["F3", "6", "X002", "1", "M3", "W"],
            ["F4", "1", "X001", "1", "M4", "PE"],
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = tmp.name

        try:
            self._write_csv(tmp_path, header, rows)
            merge_terminal_csv(tmp_path)
            _, result = self._read_csv(tmp_path)

            tags_and_pins = [(r[2], r[3]) for r in result]
            assert tags_and_pins == [
                ("X001", "1"),
                ("X001", "2"),
                ("X002", "1"),
                ("X003", "1"),
            ]
        finally:
            Path(tmp_path).unlink()


# ---------------------------------------------------------------------------
# _fill_empty_pin_slots
# ---------------------------------------------------------------------------


def test_fill_empty_pin_slots_inserts_missing_sequential_pins():
    from schematika.electrical.utils.export_utils import _fill_empty_pin_slots

    rows = [["A", "1", "X1", "1", "", "", ""], ["A", "1", "X1", "3", "", "", ""]]
    result = _fill_empty_pin_slots(rows)
    pins = {r[3] for r in result if r[2] == "X1"}
    assert "2" in pins  # gap filled


def test_fill_empty_pin_slots_inserts_missing_prefixed_pins():
    from schematika.electrical.utils.export_utils import _fill_empty_pin_slots

    rows = [["A", "1", "X1", "L1:1", "", "", ""], ["A", "1", "X1", "L1:3", "", "", ""]]
    result = _fill_empty_pin_slots(rows)
    pins = {r[3] for r in result if r[2] == "X1"}
    assert "L1:2" in pins


def test_apply_prefix_bridges_sets_group_numbers(tmp_path):
    import csv

    from schematika.electrical.utils.export_utils import _apply_prefix_bridges

    csv_path = tmp_path / "test.csv"
    with Path(csv_path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Comp From",
                "Pin From",
                "Terminal Tag",
                "Terminal Pin",
                "Comp To",
                "Pin To",
                "Internal Bridge",
            ]
        )
        writer.writerow(["", "", "X101", "L1:1", "", "", ""])
        writer.writerow(["", "", "X101", "L1:2", "", "", ""])
        writer.writerow(["", "", "X101", "L2:1", "", "", ""])
    _apply_prefix_bridges(str(csv_path), {"X101"})
    with Path(csv_path).open(newline="") as f:
        rows = list(csv.reader(f))[1:]
    l1_groups = {r[3]: r[6] for r in rows if r[2] == "X101" and r[3].startswith("L1:")}
    l2_groups = {r[3]: r[6] for r in rows if r[2] == "X101" and r[3].startswith("L2:")}
    assert l1_groups["L1:1"] == l1_groups["L1:2"]  # same group
    assert l2_groups["L2:1"] != l1_groups["L1:1"]  # different group


def test_finalize_terminal_csv_round_trip(tmp_path):
    import csv

    from schematika.electrical.utils.export_utils import finalize_terminal_csv

    csv_path = tmp_path / "terminals.csv"
    with Path(csv_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Comp From",
                "Pin From",
                "Terminal Tag",
                "Terminal Pin",
                "Comp To",
                "Pin To",
                "Internal Bridge",
            ]
        )
        writer.writerow(["A", "1", "X1", "1", "", "", ""])
        writer.writerow(["", "", "X1", "3", "B", "2", ""])
    finalize_terminal_csv(str(csv_path))
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))[1:]
    pins = [r[3] for r in rows if r[2] == "X1"]
    assert "2" in pins  # gap filled
    assert pins == sorted(pins, key=lambda p: int(p) if p.isdigit() else p)  # sorted
