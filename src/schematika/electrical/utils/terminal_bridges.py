"""Terminal-bridge helpers. Bridge def: `"all"` or list of `(start, end)` ranges."""

import csv
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

# Type aliases for internal connection definitions
BridgeRange = tuple[int, int]
ConnectionDef = str | list[BridgeRange]


def expand_range_to_pins(start: int, end: int) -> list[int]:
    """All integers from min to max inclusive (ignores argument order)."""
    return list(range(min(start, end), max(start, end) + 1))


def get_connection_groups_for_terminal(
    tag: str, pins: list[int], internal_connections: dict[str, ConnectionDef]
) -> list[list[int]]:
    """Returns groups of bridged pins; empty if no bridges defined for *tag*."""
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
    """Maps terminal tag -> bridge groups; terminals without bridges are omitted."""
    result: dict[str, list[list[int]]] = {}

    for tag, pins in terminal_pins.items():
        groups = get_connection_groups_for_terminal(tag, pins, internal_connections)
        if groups:
            result[tag] = groups

    return result


def parse_terminal_pins_from_csv(csv_path: str) -> dict[str, list[int]]:
    """Falls back to columns 2/3 if `Terminal Tag/Pin` headers are absent."""
    terminal_pins: dict[str, list[int]] = {}
    csv_file = Path(csv_path)

    if not csv_file.exists():
        return terminal_pins

    with Path(csv_path).open(newline="") as f:
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
    """In-place: appends an `Internal Bridge` column with 1-based group IDs per pin."""
    # 1. Parse existing pins to determine bridges
    terminal_pins = parse_terminal_pins_from_csv(csv_path)
    connections_data = generate_internal_connections_data(
        terminal_pins, internal_connections
    )

    # 2. Read and rewrite CSV
    with NamedTemporaryFile(mode="w", newline="", delete=False) as temp_file:
        temp_path = temp_file.name
    try:
        with (
            Path(csv_path).open(newline="") as infile,
            Path(temp_path).open("w", newline="") as outfile,
        ):
            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            try:
                header = next(reader)
            except StopIteration:
                return  # Empty file

            # Add new column to header
            new_header = [*header, "Internal Bridge"]
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

                writer.writerow([*row, bridge_val])

    except (OSError, csv.Error):
        Path(temp_path).unlink(missing_ok=True)
        raise

    shutil.move(temp_path, csv_path)
