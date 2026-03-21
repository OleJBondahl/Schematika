"""Build CableDrawing objects from field devices and external connections.

Replaces the CSV-based pipeline (cable_export.py → wireviz_yaml_generator)
with direct in-memory construction of cable drawing data.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from schematika.cable.constants import GROUP_LABELS
from schematika.cable.model import (
    CableConnection,
    CableConnector,
    CableDef,
    CableDrawing,
)

if TYPE_CHECKING:
    from schematika.electrical.field_devices import (
        CableData,
        ConnectorData,
        DeviceCable,
        FieldDevice,
    )

# Each wire triple: (device_pin, terminal_designator, terminal_pin)
WireTriple = tuple[str, str, str]


def _reorder_pins_last(
    triples: list[WireTriple],
    pins_last: tuple[str, ...],
) -> list[WireTriple]:
    """Move connections whose device pin matches pins_last to the end."""
    if not pins_last:
        return triples
    normal = [t for t in triples if t[0] not in pins_last]
    deferred = [t for t in triples if t[0] in pins_last]
    return normal + deferred


def _build_connector_from_override(
    designator: str,
    pins: tuple[str, ...],
    connector_data: ConnectorData | None,
) -> CableConnector:
    """Build a CableConnector, applying ConnectorData overrides."""
    if connector_data is None:
        return CableConnector(designator=designator, pins=pins)

    effective_pins = pins
    if connector_data.loops and connector_data.pins:
        effective_pins = connector_data.pins

    # Convert loop pin references to strings to match pin list
    loops = (
        tuple((str(a), str(b)) for a, b in connector_data.loops)
        if connector_data.loops
        else ()
    )

    return CableConnector(
        designator=designator,
        pins=effective_pins,
        type=connector_data.type or "",
        subtype=connector_data.subtype or "",
        style=connector_data.style or "",
        notes=connector_data.notes or "",
        loops=loops,
    )


def _build_cable_def(
    designator: str,
    wirecount: int,
    cable_data: CableData | None,
) -> CableDef:
    """Build a CableDef from CableData."""
    if cable_data is None:
        return CableDef(designator=designator, wirecount=wirecount)
    return CableDef(
        designator=designator,
        wirecount=wirecount,
        wire_gauge=cable_data.wire_gauge,
        length=cable_data.cable_length or 0.0,
        category=cable_data.category,
        wire_colors=cable_data.wire_colors or (),
        notes=cable_data.cable_note or "",
    )


def _build_target_connectors(
    triples: list[WireTriple],
) -> tuple[list[CableConnector], dict[int, tuple[str, str]]]:
    """Build one CableConnector per unique target terminal.

    Returns:
        (connectors, wire_targets) where wire_targets maps wire index
        to (terminal_designator, terminal_pin).
    """
    # Group pins by terminal designator, preserving order
    terminal_pins: OrderedDict[str, list[str]] = OrderedDict()
    wire_targets: dict[int, tuple[str, str]] = {}

    for i, (_, term_des, term_pin) in enumerate(triples):
        terminal_pins.setdefault(term_des, []).append(term_pin)
        wire_targets[i] = (term_des, term_pin)

    connectors = []
    for term_des, pins in terminal_pins.items():
        connectors.append(
            CableConnector(
                designator=term_des,
                pins=tuple(pins),
                notes="Wire ferrule",
            )
        )
    return connectors, wire_targets


def _build_drawing_from_triples(
    comp_des: str,
    triples: list[WireTriple],
    cable_designator: str,
    cable_data: CableData | None,
    source_connector_data: ConnectorData | None,
    title: str,
) -> CableDrawing:
    """Build a CableDrawing from ordered wire triples."""
    source_pins = tuple(t[0] for t in triples)
    wirecount = len(triples)

    source = _build_connector_from_override(
        comp_des, source_pins, source_connector_data
    )
    target_connectors, wire_targets = _build_target_connectors(triples)
    cable = _build_cable_def(cable_designator, wirecount, cable_data)

    connections = tuple(
        CableConnection(
            from_connector=source.designator,
            from_pin=source_pins[i],
            cable=cable_designator,
            wire=i + 1,
            to_connector=wire_targets[i][0],
            to_pin=wire_targets[i][1],
        )
        for i in range(wirecount)
    )

    return CableDrawing(
        cable=cable,
        connectors=(source, *target_connectors),
        connections=connections,
        title=title,
    )


def _build_single_cable_drawing(
    comp_des: str,
    raw_connections: list[tuple[str, str, str, str, str, str]],
    field_device: FieldDevice | None,
    cable_designator: str,
    pins_last: tuple[str, ...],
) -> CableDrawing:
    """Build a CableDrawing for a single-cable device."""
    triples: list[WireTriple] = [
        (conn[1], str(conn[2]), conn[3]) for conn in raw_connections
    ]
    triples = _reorder_pins_last(triples, pins_last)

    source_connector_data = None
    if field_device and field_device.connectors:
        source_connector_data = field_device.connectors[0]
    cable_data = field_device.cable if field_device else None

    return _build_drawing_from_triples(
        comp_des,
        triples,
        cable_designator,
        cable_data,
        source_connector_data,
        title=comp_des,
    )


def _build_multi_cable_drawings(
    device_tag: str,
    raw_connections: list[tuple[str, str, str, str, str, str]],
    field_device: FieldDevice,
    cable_prefix: str,
    cable_number: int,
    pins_last: tuple[str, ...],
) -> list[tuple[CableDrawing, str, int]]:
    """Build CableDrawings for a multi-cable device."""
    device_cables: tuple[DeviceCable, ...] = field_device.cables  # type: ignore[assignment]

    pin_to_group: dict[str, int] = {}
    for i, dc in enumerate(device_cables):
        for pin in dc.pins:
            pin_to_group[pin] = i

    groups: dict[int, list[tuple[str, str, str, str, str, str]]] = {}
    for conn in raw_connections:
        group_idx = pin_to_group.get(conn[1], 0)
        groups.setdefault(group_idx, []).append(conn)

    results: list[tuple[CableDrawing, str, int]] = []
    for i, dc in enumerate(device_cables):
        comp_des = f"{device_tag} [{GROUP_LABELS[i]}]"
        cable_designator = f"{cable_prefix}{cable_number:03d}"
        group_conns = groups.get(i, [])
        if not group_conns:
            cable_number += 1
            continue

        triples: list[WireTriple] = [
            (conn[1], str(conn[2]), conn[3]) for conn in group_conns
        ]
        triples = _reorder_pins_last(triples, pins_last)

        drawing = _build_drawing_from_triples(
            comp_des,
            triples,
            cable_designator,
            dc.cable,
            dc.connector,
            title=device_tag,
        )
        results.append((drawing, comp_des, cable_number))
        cable_number += 1

    return results


def build_cable_drawings(
    external_connections: list[tuple[str, str, object, str, str, str]],
    field_devices: list[FieldDevice],
    cable_prefix: str = "A-W",
    cable_start: int = 1,
    pins_last: tuple[str, ...] = ("PE",),
) -> list[CableDrawing]:
    """Build cable drawings from field device data and external connections.

    Args:
        external_connections: ConnectionRow tuples from resolved field devices.
            Each tuple: (component_from, pin_from, terminal, terminal_pin,
            component_to, pin_to).
        field_devices: FieldDevice instances with cable metadata.
        cable_prefix: Auto-numbering prefix, e.g. "A-W".
        cable_start: First cable number.
        pins_last: Pin names to move to end of each cable, e.g. ("PE",).

    Returns:
        Ordered list of CableDrawing objects, one per cable.
    """
    device_connections: OrderedDict[str, list] = OrderedDict()
    for row in external_connections:
        device_connections.setdefault(row[0], []).append(row)

    device_lookup = {fd.tag: fd for fd in field_devices}

    drawings: list[CableDrawing] = []
    cable_number = cable_start

    for device_tag, connections in device_connections.items():
        field_device = device_lookup.get(device_tag)

        if field_device and field_device.cables:
            results = _build_multi_cable_drawings(
                device_tag,
                connections,
                field_device,
                cable_prefix,
                cable_number,
                pins_last,
            )
            for drawing, _comp_des, _num in results:
                drawings.append(drawing)
            cable_number += len(results)
        else:
            cable_designator = f"{cable_prefix}{cable_number:03d}"
            drawing = _build_single_cable_drawing(
                device_tag,
                connections,
                field_device,
                cable_designator,
                pins_last,
            )
            drawings.append(drawing)
            cable_number += 1

    return drawings
