"""Export utilities for generating CSV reports for terminals.

Provides functions for exporting terminal lists, and for merging and sorting
terminal connection CSVs produced by ``export_registry_to_csv``.

The merge/sort workflow handles the common case where multiple sources
(e.g. registry export + external connections) append rows to the same CSV,
producing duplicate (Terminal Tag, Terminal Pin) entries that need to be
collapsed into single rows with FROM and TO sides populated.
"""

import csv
import re
from pathlib import Path
from collections import defaultdict
from typing import Final

from schematika.electrical.utils.terminal_bridges import (
    ConnectionDef,
    update_csv_with_internal_connections,
)

# Column indices in the merged terminal CSV format.
# Columns: FROM_COMP(0), FROM_PIN(1), TERM_TAG(2), TERM_PIN(3),
#          TO_COMP(4), TO_PIN(5), BRIDGE(6)  # noqa: ERA001
_CSV_COL_TO_COMP: Final = 4
_CSV_COL_BRIDGE: Final = 6


def export_terminal_list(
    filepath: str, used_terminals: list[str], descriptions: dict[str, str] | None = None
) -> None:
    """Exports the terminal list to a CSV file.

    Args:
        filepath: Path to the CSV file.
        used_terminals: List of terminal tags used on that page.
        descriptions: Optional dict mapping tags to descriptions.
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    descriptions = descriptions or {}

    unique_terminals = sorted(set(used_terminals))

    with Path(filepath).open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Terminal", "Description"])
        for tag in unique_terminals:
            desc = descriptions.get(tag, "Unknown Terminal")
            writer.writerow([tag, desc])


# ---------------------------------------------------------------------------
# Terminal CSV merge / sort utilities
# ---------------------------------------------------------------------------


def _terminal_pin_sort_key(pin: str) -> list:
    """Natural sort key for terminal pin strings.

    Splits *pin* on digit boundaries so that numeric parts compare as
    integers rather than lexicographically.  This ensures the ordering
    ``"1" < "2" < "10" < "L1:1" < "L1:10"``.

    Args:
        pin: A terminal pin identifier, e.g. ``"1"``, ``"10"``, ``"L1:3"``.

    Returns:
        A list of alternating ``str`` / ``int`` segments suitable for use
        as a sort key.

    Examples:
        >>> _terminal_pin_sort_key("2") < _terminal_pin_sort_key("10")
        True
        >>> _terminal_pin_sort_key("L1:1") < _terminal_pin_sort_key("L1:10")
        True
    """
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", pin)]


def _merge_terminal_rows(rows: list[list[str]]) -> list[str]:
    """Merge multiple CSV rows that share the same (Terminal Tag, Terminal Pin).

    When the same terminal pin appears in more than one row (e.g. once from
    the registry export and once from an external-connections append), this
    function collapses them into a single row.  It collects all
    ``(component, pin)`` pairs from both the FROM side (columns 0-1) and
    the TO side (columns 4-5), then distributes them so that one pair ends
    up on each side.

    The **last** FROM entry is kept on the FROM side (this is typically the
    external device that was appended after the registry export).  Excess
    entries are moved to the opposite side to fill vacancies.

    Any non-empty ``Internal Bridge`` value (column 6) found in any of the
    input rows is preserved on the merged result.

    Args:
        rows: Two or more CSV data rows (lists of strings) that share the
            same Terminal Tag (index 2) and Terminal Pin (index 3).

    Returns:
        A single merged row as a list of strings with 7 columns:
        ``[Component From, Pin From, Terminal Tag, Terminal Pin,
        Component To, Pin To, Internal Bridge]``.
    """
    from_entries: list[tuple[str, str]] = []
    to_entries: list[tuple[str, str]] = []
    bridge = ""
    term_tag = rows[0][2]
    term_pin = rows[0][3]

    for row in rows:
        if row[0]:
            from_entries.append((row[0], row[1]))
        if len(row) > _CSV_COL_TO_COMP and row[_CSV_COL_TO_COMP]:
            to_entries.append((row[_CSV_COL_TO_COMP], row[_CSV_COL_TO_COMP + 1]))
        if len(row) > _CSV_COL_BRIDGE and row[_CSV_COL_BRIDGE]:
            bridge = row[_CSV_COL_BRIDGE]

    # Balance: move excess FROM entries to TO and vice versa
    while len(from_entries) > 1 and len(to_entries) < 1:
        to_entries.append(from_entries.pop(0))
    while len(to_entries) > 1 and len(from_entries) < 1:
        from_entries.append(to_entries.pop(0))

    # Last FROM entry is typically the external device (appended after registry)
    comp_from = from_entries[-1][0] if from_entries else ""
    pin_from = from_entries[-1][1] if from_entries else ""
    comp_to = to_entries[0][0] if to_entries else ""
    pin_to = to_entries[0][1] if to_entries else ""

    return [comp_from, pin_from, term_tag, term_pin, comp_to, pin_to, bridge]


def merge_terminal_csv(csv_path: str) -> None:
    """Merge duplicate terminal rows and sort by terminal tag then pin number.

    Reads a terminal-connection CSV (as produced by
    :func:`~schematika.electrical.system.connection_registry.export_registry_to_csv`,
    optionally with rows appended from other sources), merges rows that
    share the same ``(Terminal Tag, Terminal Pin)`` key, and writes the
    result back to the same file, sorted by terminal tag and pin in natural
    order.

    The expected CSV columns are::

        Component From, Pin From, Terminal Tag, Terminal Pin,
        Component To, Pin To[, Internal Bridge]

    The ``Internal Bridge`` column is optional; if present it is preserved.

    **Gap-filling:** After merging duplicates, this function inserts empty
    placeholder rows for any missing pin slots in sequential pin sequences
    (e.g. if pins 1 and 3 exist, pin 2 is inserted as an empty row). This
    ensures the printed terminal strip renders as a complete, unbroken strip.
    Intentional gaps in pin numbering will be filled — if sparse pin sequences
    are required, do not call this function.

    This function is the library equivalent of the consumer project's
    ``_merge_and_sort_terminal_csv()`` utility, made generic so any project
    can call it after assembling a terminal CSV from multiple sources.

    Args:
        csv_path: Path to the CSV file to merge and sort **in place**.

    Raises:
        FileNotFoundError: If *csv_path* does not exist.

    Example:
        >>> from schematika.electrical.utils.export_utils import merge_terminal_csv
        >>> merge_terminal_csv("output/system_terminals.csv")
    """
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    if not rows:
        return

    # Group rows by (Terminal Tag, Terminal Pin)
    groups: dict[tuple[str, str], list[list[str]]] = defaultdict(list)
    for row in rows:
        key = (row[2], row[3])
        groups[key].append(row)

    # Merge duplicates
    merged_rows: list[list[str]] = []
    for group_rows in groups.values():
        if len(group_rows) == 1:
            merged_rows.append(group_rows[0])
        else:
            merged_rows.append(_merge_terminal_rows(group_rows))

    # Fill any missing pin slots (gaps in sequential pin numbering)
    merged_rows = _fill_empty_pin_slots(merged_rows)

    # Sort by terminal tag (natural), then by pin (natural)
    merged_rows.sort(
        key=lambda r: (_terminal_pin_sort_key(r[2]), _terminal_pin_sort_key(r[3]))
    )

    with Path(csv_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(merged_rows)


def _fill_empty_pin_slots(rows: list[list[str]]) -> list[list[str]]:
    """Return rows extended with empty placeholders for missing pin slots.

    Scans all rows to find the highest pin number per prefix per terminal,
    then produces placeholder rows for any missing slots from 1 up to that max.
    This ensures the printed terminal strip looks complete.

    Args:
        rows: CSV data rows (lists of strings), each with Terminal Tag at
            index 2 and Terminal Pin at index 3.

    Returns:
        A new list containing all original rows plus placeholder rows for
        any missing pin slots.
    """
    ncols = len(rows[0]) if rows else 7

    max_pins: dict[tuple[str, str], int] = {}
    existing_keys: set[tuple[str, str]] = set()

    for row in rows:
        tag = row[2]
        pin_str = row[3]
        existing_keys.add((tag, pin_str))

        if ":" in pin_str:
            prefix, num_str = pin_str.rsplit(":", 1)
            try:
                num = int(num_str)
                key = (tag, prefix)
                max_pins[key] = max(max_pins.get(key, 0), num)
            except ValueError:
                pass
        else:
            try:
                num = int(pin_str)
                key = (tag, "")
                max_pins[key] = max(max_pins.get(key, 0), num)
            except ValueError:
                pass

    placeholders: list[list[str]] = []
    for (tag, prefix), max_num in max_pins.items():
        for n in range(1, max_num + 1):
            pin_str = f"{prefix}:{n}" if prefix else str(n)
            if (tag, pin_str) not in existing_keys:
                empty_row = ["", "", tag, pin_str, "", ""]
                while len(empty_row) < ncols:
                    empty_row.append("")
                placeholders.append(empty_row)
                existing_keys.add((tag, pin_str))

    return rows + placeholders


def _build_prefix_groups(
    rows: list[list[str]], terminal_tags: set[str]
) -> dict[str, dict[str, str]]:
    """Build a mapping of tag -> prefix -> group number for prefixed pins."""
    prefix_groups: dict[str, dict[str, str]] = {}
    for row in rows:
        tag = row[2]
        if tag not in terminal_tags or ":" not in row[3]:
            continue
        prefix = row[3].rsplit(":", 1)[0]
        tag_groups = prefix_groups.setdefault(tag, {})
        if prefix not in tag_groups:
            tag_groups[prefix] = str(len(tag_groups) + 1)
    return prefix_groups


def _apply_prefix_bridges(csv_path: str, terminal_tags: set[str]) -> None:
    """Add bridge group numbers to prefixed terminal pins.

    For terminals with ``bridge="per_prefix"``, all pins sharing the same
    prefix (e.g. all ``"L1:*"`` pins) are marked as internally connected.
    Each prefix gets a unique group number within its terminal.

    The bridge column must already exist in the CSV (added by
    :func:`~schematika.electrical.update_csv_with_internal_connections`).

    Args:
        csv_path: Path to the CSV file to update **in place**.
        terminal_tags: Set of terminal tag strings that use
            ``bridge="per_prefix"`` (e.g. ``{"X101", "X002"}``).
    """
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    bridge_col = header.index("Internal Bridge") if "Internal Bridge" in header else -1
    if bridge_col == -1:
        return

    prefix_groups = _build_prefix_groups(rows, terminal_tags)

    for row in rows:
        tag = row[2]
        if tag not in prefix_groups or ":" not in row[3]:
            continue
        prefix = row[3].rsplit(":", 1)[0]
        group = prefix_groups[tag].get(prefix, "")
        if group:
            row[bridge_col] = group

    with Path(csv_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def finalize_terminal_csv(
    csv_path: str,
    bridge_defs: dict[str, ConnectionDef] | None = None,
    prefix_bridge_tags: set[str] | None = None,
    external_connections: list | None = None,
) -> None:
    """Apply the full terminal CSV post-processing pipeline.

    This is the recommended single-call replacement for the three-step
    sequence::

        update_csv_with_internal_connections(path, bridge_defs)
        merge_terminal_csv(path)  # merge + sort + fill gaps
        _apply_prefix_bridges(path, prefix_tags)

    Args:
        csv_path: Path to the terminal CSV (already written by
            :func:`~schematika.electrical.export_registry_to_csv`).
        bridge_defs: Mapping of terminal tag -> bridge mode for
            non-prefix terminals (e.g. ``{"X102": "all"}``).
            Passed to :func:`update_csv_with_internal_connections`.
        prefix_bridge_tags: Set of terminal tags that use
            ``bridge="per_prefix"`` (e.g. ``{"X101", "X002"}``).
            These are handled by :func:`_apply_prefix_bridges` after
            sorting so that prefixes appear in consistent order.
        external_connections: Optional list of
            :data:`~schematika.electrical.field_devices.ConnectionRow`
            tuples to append before processing. These are the field
            wiring rows not captured in the registry.
    """
    # 1. Append external connections (field wiring)
    if external_connections:
        with Path(csv_path).open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in external_connections:
                writer.writerow(row)

    # 2. Apply internal bridges (all / specific pins)
    if bridge_defs:
        update_csv_with_internal_connections(csv_path, bridge_defs)

    # 3. Merge duplicates, fill gaps, sort
    merge_terminal_csv(csv_path)

    # 4. Apply per-prefix bridges after sort (stable prefix order)
    if prefix_bridge_tags:
        _apply_prefix_bridges(csv_path, prefix_bridge_tags)
