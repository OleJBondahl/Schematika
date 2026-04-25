"""Cable CSV generation for wireviz-compatible cable drawings."""

import csv as _csv
import string
from pathlib import Path
from collections import OrderedDict

_GROUP_LABELS = list(string.ascii_uppercase)

CSV_COLUMNS = [
    "cable_des",
    "comp_des_1",
    "conn_des_1",
    "pin_1",
    "comp_des_2",
    "conn_des_2",
    "pin_2",
    "wire_gauge",
    "length",
    "cable_note",
    "category",
    "colors",
]


def _connector_override(cd) -> dict:
    """Build connector override dict from ConnectorData."""
    ovr = {}
    if cd.type:
        ovr["type"] = cd.type
    if cd.subtype:
        ovr["subtype"] = cd.subtype
    if cd.style:
        ovr["style"] = cd.style
    if cd.notes:
        ovr["notes"] = cd.notes
    if cd.loops:
        ovr["loops"] = [list(pair) for pair in cd.loops]
        if cd.pins:
            ovr["pins"] = list(cd.pins)
    return ovr


def _write_cable_group(writer, comp_des_1, connections, cable) -> None:
    """Write one cable group to CSV."""
    for conn in connections:
        _comp_from, pin_from, terminal, terminal_pin, _comp_to, _pin_to = conn
        csv_row = {
            "cable_des": "",
            "comp_des_1": comp_des_1,
            "conn_des_1": "",
            "pin_1": pin_from,
            "comp_des_2": str(terminal),
            "conn_des_2": "",
            "pin_2": terminal_pin,
            "wire_gauge": "",
            "length": "",
            "cable_note": "",
            "category": "",
            "colors": "",
        }
        if cable:
            csv_row["wire_gauge"] = str(cable.wire_gauge)
            if cable.cable_length is not None:
                csv_row["length"] = str(cable.cable_length)
            if cable.cable_note:
                csv_row["cable_note"] = cable.cable_note
            csv_row["category"] = cable.category
            if cable.wire_colors:
                csv_row["colors"] = ":".join(cable.wire_colors)
        writer.writerow(csv_row)


def _write_multi_cable_device(
    writer,
    device_tag: str,
    connections: list,
    field_device,
    cable_groups: list,
    connector_overrides: dict,
) -> None:
    """Write a multi-cable device (DeviceCable groups) to CSV."""
    pin_to_group: dict[str, int] = {}
    for i, dc in enumerate(field_device.cables):
        for pin in dc.pins:
            pin_to_group[pin] = i

    groups: dict[int, list] = {}
    for conn in connections:
        group_idx = pin_to_group.get(conn[1], 0)
        groups.setdefault(group_idx, []).append(conn)

    for i, dc in enumerate(field_device.cables):
        comp_des = f"{device_tag} [{_GROUP_LABELS[i]}]"
        _write_cable_group(writer, comp_des, groups.get(i, []), dc.cable)
        cable_groups.append((comp_des, device_tag))
        if dc.connector:
            ovr = _connector_override(dc.connector)
            if ovr:
                connector_overrides[comp_des] = ovr


def _write_single_cable_device(
    writer,
    device_tag: str,
    connections: list,
    field_device,
    cable_groups: list,
    connector_overrides: dict,
) -> None:
    """Write a single-cable device to CSV."""
    cable = field_device.cable if field_device else None
    _write_cable_group(writer, device_tag, connections, cable)
    cable_groups.append((device_tag, device_tag))
    if field_device and field_device.connectors:
        for cd in field_device.connectors:
            ovr = _connector_override(cd)
            if ovr:
                connector_overrides[device_tag] = ovr


def generate_cable_csv(
    external_connections: list,
    field_devices: list,
    output_path: str,
) -> tuple[str, int, dict[str, str], dict[str, dict]]:
    """Generate wireviz-compatible cable CSV from resolved connections.

    Args:
        external_connections: Resolved ConnectionRow tuples.
        field_devices: List of FieldDevice instances (for cable metadata).
        output_path: Path for the output CSV file.

    Returns:
        (csv_path, cable_count, cable_titles, connector_overrides)
    """
    device_connections: OrderedDict[str, list] = OrderedDict()
    for row in external_connections:
        device_connections.setdefault(row[0], []).append(row)

    device_lookup = {fd.tag: fd for fd in field_devices}

    Path(output_path).resolve().parent.mkdir(parents=True, exist_ok=True)

    cable_groups: list[tuple[str, str]] = []
    connector_overrides: dict[str, dict] = {}

    with Path(output_path).open("w", newline="") as f:
        writer = _csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for device_tag, connections in device_connections.items():
            field_device = device_lookup.get(device_tag)
            if field_device and field_device.cables:
                _write_multi_cable_device(
                    writer,
                    device_tag,
                    connections,
                    field_device,
                    cable_groups,
                    connector_overrides,
                )
            else:
                _write_single_cable_device(
                    writer,
                    device_tag,
                    connections,
                    field_device,
                    cable_groups,
                    connector_overrides,
                )

    cable_titles = {
        f"A-W{i:03d}": clean_tag
        for i, (_comp_des, clean_tag) in enumerate(cable_groups, start=1)
    }

    for connections in device_connections.values():
        for conn in connections:
            terminal_des = str(conn[2])
            if terminal_des not in connector_overrides:
                connector_overrides[terminal_des] = {"notes": "Wire ferrule"}

    return output_path, len(cable_groups), cable_titles, connector_overrides
