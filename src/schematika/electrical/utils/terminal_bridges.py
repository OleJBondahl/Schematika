"""Terminal Internal Connections (Bridges) Utilities.

This module provides utilities for managing internal connections between
terminal pins. Internal connections (bridges) represent physical jumpers
or connections between pins on terminal strips.

Key Concepts:
    - Bridge Range: A tuple (start, end) representing connected pins
    - Connection Definition: Either "all" (all pins connected) or a list of ranges

Example Usage:
    # Define internal connections for a project
    connections = {
        "X001": [(1, 2), (5, 8)],  # Pins 1-2 bridged, pins 5-8 bridged
        "X103": "all",              # All pins on X103 are bridged
    }

    # Parse existing terminal data and add bridge info
    terminal_pins = parse_terminal_pins_from_csv("terminals.csv")
    update_csv_with_internal_connections("terminals.csv", connections)
"""

import csv
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

# Type aliases for internal connection definitions
BridgeRange = tuple[int, int]
ConnectionDef = str | list[BridgeRange]


def expand_range_to_pins(start: int, end: int) -> list[int]:
    """Expand a (start, end) range to list of all pins in between.

    Since bridges physically connect all pins between start and end,
    this function returns all pins that would be connected.

    Args:
        start: First pin in bridge
        end: Last pin in bridge

    Returns:
        List of all pins from start to end inclusive

    Example:
        >>> expand_range_to_pins(5, 8)
        [5, 6, 7, 8]
    """
    return list(range(min(start, end), max(start, end) + 1))


def get_connection_groups_for_terminal(
    tag: str, pins: list[int], internal_connections: dict[str, ConnectionDef]
) -> list[list[int]]:
    """Get the internal connection groups for a specific terminal.

    Groups are sets of pins that are physically connected (bridged).
    A terminal can have multiple independent bridge groups.

    Args:
        tag: Terminal tag (e.g., "X001")
        pins: List of all pin numbers on this terminal
        internal_connections: Dictionary mapping terminal tags to connection defs

    Returns:
        List of groups, where each group is a list of pin numbers that are connected.
        Empty list if no internal connections defined for this terminal.

    Example:
        >>> connections = {"X001": [(1, 2), (5, 8)]}
        >>> pins = [1, 2, 3, 4, 5, 6, 7, 8]
        >>> get_connection_groups_for_terminal("X001", pins, connections)
        [[1, 2], [5, 6, 7, 8]]
    """
    if tag not in internal_connections:
        return []

    connection_def = internal_connections[tag]

    if connection_def == "all":
        # All pins connected - return single group with all pins
        return [sorted(pins)]
    if isinstance(connection_def, list):
        # Expand ranges and filter to only include pins that exist on this terminal
        pin_set = set(pins)
        groups = []
        for start, end in connection_def:
            expanded = expand_range_to_pins(start, end)
            # Only include pins that exist on this terminal
            filtered = [p for p in expanded if p in pin_set]
            if filtered:
                groups.append(filtered)
        return groups

    return []


def generate_internal_connections_data(
    terminal_pins: dict[str, list[int]], internal_connections: dict[str, ConnectionDef]
) -> dict[str, list[list[int]]]:
    """Generate internal connections data for all terminals.

    Processes the terminal pins dictionary and generates connection groups
    based on the internal connections definition.

    Args:
        terminal_pins: Dictionary mapping terminal tags to list of pin numbers
        internal_connections: Dictionary mapping terminal tags to connection defs

    Returns:
        Dictionary with terminal tags as keys and connection groups as values.
        Format suitable for JSON export or further processing.

    Example:
        >>> pins = {"X001": [1, 2, 3], "X103": [1, 2, 3, 4]}
        >>> connections = {"X001": [(1, 2)], "X103": "all"}
        >>> generate_internal_connections_data(pins, connections)
        {'X001': [[1, 2]], 'X103': [[1, 2, 3, 4]]}
    """
    result: dict[str, list[list[int]]] = {}

    for tag, pins in terminal_pins.items():
        groups = get_connection_groups_for_terminal(tag, pins, internal_connections)
        if groups:
            result[tag] = groups

    return result


def parse_terminal_pins_from_csv(csv_path: str) -> dict[str, list[int]]:  # noqa: C901
    """Parse system_terminals.csv to extract unique pins per terminal tag.

    Reads a CSV file with terminal connections and extracts all unique pins
    for each terminal tag. The CSV is expected to have columns for
    'Terminal Tag' and 'Terminal Pin' (or fallback to columns 2 and 3).

    Args:
        csv_path: Path to system_terminals.csv

    Returns:
        Dictionary mapping terminal tags to sorted list of pin numbers

    Note:
        Non-numeric pins are silently skipped.
    """
    terminal_pins: dict[str, list[int]] = {}
    csv_file = Path(csv_path)

    if not csv_file.exists():
        return terminal_pins

    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return terminal_pins  # Empty file

        # Try to find column indices by name
        try:
            tag_idx = header.index("Terminal Tag")
            pin_idx = header.index("Terminal Pin")
        except ValueError:
            # Fallback indices based on known structure
            tag_idx = 2
            pin_idx = 3

        for row in reader:
            if len(row) > max(tag_idx, pin_idx):
                tag = row[tag_idx]
                pin_str = row[pin_idx]

                if tag and pin_str:
                    try:
                        pin = int(pin_str)
                        if tag not in terminal_pins:
                            terminal_pins[tag] = []
                        if pin not in terminal_pins[tag]:
                            terminal_pins[tag].append(pin)
                    except ValueError:
                        pass  # Skip non-numeric pins

    # Sort pins for each terminal
    for tag in terminal_pins:
        terminal_pins[tag].sort()

    return terminal_pins


def update_csv_with_internal_connections(
    csv_path: str, internal_connections: dict[str, ConnectionDef]
) -> None:
    """Update system_terminals.csv with an 'Internal Bridge' column.

    Reads the CSV, determines internal connection groups for each terminal,
    and appends a bridge group ID to the new column. Pins in the same bridge
    group get the same ID number (1-based).

    Args:
        csv_path: Path to system_terminals.csv
        internal_connections: Dictionary mapping terminal tags to connection defs

    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        csv.Error: If CSV parsing fails

    Note:
        This function modifies the file in place by writing to a temp file
        and then replacing the original.
    """
    # 1. Parse existing pins to determine bridges
    terminal_pins = parse_terminal_pins_from_csv(csv_path)
    connections_data = generate_internal_connections_data(
        terminal_pins, internal_connections
    )

    # 2. Read and rewrite CSV
    temp_file = NamedTemporaryFile(mode="w", newline="", delete=False)

    try:
        with open(csv_path, newline="") as infile, temp_file as outfile:
            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            try:
                header = next(reader)
            except StopIteration:
                return  # Empty file

            # Add new column to header
            new_header = header + ["Internal Bridge"]
            writer.writerow(new_header)

            # Find column indices
            try:
                tag_idx = header.index("Terminal Tag")
                pin_idx = header.index("Terminal Pin")
            except ValueError:
                # Fallback indices based on known structure
                tag_idx = 2
                pin_idx = 3

            for row in reader:
                # Handle potential short rows or empty lines
                if not row:
                    continue

                # Safe access to columns
                tag = row[tag_idx] if len(row) > tag_idx else ""
                pin_str = row[pin_idx] if len(row) > pin_idx else ""

                bridge_val = ""

                if tag in connections_data and pin_str and pin_str.isdigit():
                    pin = int(pin_str)
                    groups = connections_data[tag]
                    # Find which group this pin belongs to
                    for idx, group in enumerate(groups):
                        if pin in group:
                            bridge_val = str(idx + 1)  # 1-based index
                            break

                writer.writerow(row + [bridge_val])

    except (OSError, csv.Error) as e:
        temp_file.close()
        Path(temp_file.name).unlink(missing_ok=True)
        raise e

    temp_file.close()
    shutil.move(temp_file.name, csv_path)
