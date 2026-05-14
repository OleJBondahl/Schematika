"""Build CableDrawing objects directly from field devices + external connections."""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from schematika.cable.constants import GROUP_LABELS
from schematika.cable.errors import CableError
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
    from schematika.electrical.inter_device import InterDeviceConnection

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
    """Returns (connectors, wire_targets); `wire_targets[i] = (terminal, pin)`."""
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
    device_cables: tuple[DeviceCable, ...] = field_device.cables  # ty: ignore[invalid-assignment]

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
    """Build one CableDrawing per field-device cable from external connection rows.

    Devices that declare multiple cables (via ``FieldDevice.cables``) produce one
    drawing per cable; devices without an explicit cable declaration produce a
    single synthesised drawing.  Cable designators are assigned sequentially
    starting from *cable_start*.

    Args:
        external_connections: Rows from ``generate_field_connections()``.  Each
            row is a 6-tuple
            ``(device_tag, device_pin, terminal_obj, terminal_designator,
            terminal_pin, cable_number_str)``.
        field_devices: List of ``FieldDevice`` objects used to look up per-device
            cable overrides and connector metadata.
        cable_prefix: Prefix for generated cable designators, e.g. ``"A-W"``
            yields ``"A-W001"``, ``"A-W002"``, …
        cable_start: First cable number to assign.  Useful when merging drawings
            from multiple calls.
        pins_last: Device pin names that should always be routed last (e.g.
            ``("PE",)`` for protective earth).

    Returns:
        list[CableDrawing]: One ``CableDrawing`` per cable, in device-encounter
            order.

    Examples:
        >>> from schematika.cable.builder import build_cable_drawings
        >>> drawings = build_cable_drawings([], [])
        >>> drawings
        []
        >>> # With real rows, each device tag yields at least one drawing.
        >>> rows = [("TT-101", "1", None, "X100", "1", "1"),
        ...         ("TT-101", "2", None, "X100", "2", "1")]
        >>> drawings = build_cable_drawings(rows, [], cable_prefix="W")
        >>> len(drawings)
        1
        >>> drawings[0].title
        'TT-101'
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


def _resolve_inter_device_pins(
    conn: InterDeviceConnection,
) -> tuple[ConnectorData | None, ConnectorData | None, tuple[str, ...]]:
    """Resolve pins for the wires=None (simple 1:1) path against to_endpoints[0].

    Returns (from_cd, to_cd, pins) where pins drive the source connector and
    the single target connector.  Mirrors the old 2-endpoint logic exactly.
    """
    target = conn.to_endpoints[0]
    from_cd = conn.from_connector_data
    to_cd = target.connector_data

    if from_cd is not None and to_cd is not None:
        if from_cd.pins and to_cd.pins and len(from_cd.pins) != len(to_cd.pins):
            to_des = f"{target.device}-{target.connector}"
            msg = (
                f"InterDeviceConnection {conn.from_device}-{conn.from_connector} "
                f"<-> {to_des}: "
                f"connector pin counts differ "
                f"({len(from_cd.pins)} vs {len(to_cd.pins)})"
            )
            raise CableError(msg)
        pins = from_cd.pins or to_cd.pins or ()
        return from_cd, to_cd, pins

    if from_cd is not None:
        return from_cd, from_cd, from_cd.pins or ()
    if to_cd is not None:
        return to_cd, to_cd, to_cd.pins or ()

    # Neither side has ConnectorData -- synthesise from cable wire_colors.
    wire_colors = conn.cable.wire_colors or ()
    if not wire_colors:
        msg = (
            f"InterDeviceConnection {conn.from_device}-{conn.from_connector} "
            f"<-> {target.device}-{target.connector}: "
            f"neither connector_data nor cable.wire_colors provided; "
            f"wire count is undefined"
        )
        raise CableError(msg)
    pins = tuple(str(i) for i in range(1, len(wire_colors) + 1))
    return None, None, pins


def _build_inter_device_drawing(
    conn: InterDeviceConnection,
    cable_designator: str,
) -> CableDrawing:
    """Build one CableDrawing for a (possibly fan-out) InterDeviceConnection.

    Design note: WireViz supports an arbitrary number of connectors in a single
    Harness.  ``render_cable_svg`` loops over ``drawing.connections`` and calls
    ``harness.connect()`` for each one, so multiple target connectors are handled
    transparently.  We therefore always produce ONE CableDrawing per IDC regardless
    of fan-out degree.

    When wires=None (simple path): synthesise pins against to_endpoints[0] using
    the existing mirror/wire_colors logic.

    When wires is provided (fan-out path): build one CableConnector per distinct
    to_endpoint index, assembling the pin list from the WireSpec entries that
    reference it.  The source connector covers all from_pins in wire order.
    """
    from_designator = f"{conn.from_device}-{conn.from_connector}"

    if conn.wires is None:
        # --- Simple 1:1 path (wires=None) ---
        from_cd, to_cd, pins = _resolve_inter_device_pins(conn)
        wirecount = len(pins)
        target = conn.to_endpoints[0]
        to_designator = f"{target.device}-{target.connector}"

        source = _build_connector_from_override(from_designator, pins, from_cd)
        to_connector = _build_connector_from_override(to_designator, pins, to_cd)
        cable = _build_cable_def(cable_designator, wirecount, conn.cable)

        connections = tuple(
            CableConnection(
                from_connector=from_designator,
                from_pin=pins[i],
                cable=cable_designator,
                wire=i + 1,
                to_connector=to_designator,
                to_pin=pins[i],
            )
            for i in range(wirecount)
        )

        return CableDrawing(
            cable=cable,
            connectors=(source, to_connector),
            connections=connections,
            title=f"{from_designator} <-> {to_designator}",
        )

    # --- Fan-out path (explicit wires) ---
    # Validate endpoint indices.
    n_endpoints = len(conn.to_endpoints)
    for wire_spec in conn.wires:
        if not (0 <= wire_spec.to_endpoint < n_endpoints):
            msg = (
                f"InterDeviceConnection {from_designator}: "
                f"WireSpec.to_endpoint={wire_spec.to_endpoint} out of range "
                f"(0..{n_endpoints - 1})"
            )
            raise CableError(msg)

    # Source connector: from_pins in wire order.
    from_pins = tuple(ws.from_pin for ws in conn.wires)
    source = _build_connector_from_override(
        from_designator, from_pins, conn.from_connector_data
    )

    # Build per-endpoint connectors: collect pins in the order wires reference them.
    endpoint_pins: dict[int, list[str]] = {}
    ep_order: list[int] = []
    for ws in conn.wires:
        if ws.to_endpoint not in endpoint_pins:
            endpoint_pins[ws.to_endpoint] = []
            ep_order.append(ws.to_endpoint)
        endpoint_pins[ws.to_endpoint].append(ws.to_pin)

    target_connectors: list[CableConnector] = []
    endpoint_designators: dict[int, str] = {}
    for ep_idx in ep_order:
        ep = conn.to_endpoints[ep_idx]
        des = f"{ep.device}-{ep.connector}"
        endpoint_designators[ep_idx] = des
        pins_for_ep = tuple(endpoint_pins[ep_idx])
        target_connectors.append(
            _build_connector_from_override(des, pins_for_ep, ep.connector_data)
        )

    cable = _build_cable_def(cable_designator, len(conn.wires), conn.cable)

    connections = tuple(
        CableConnection(
            from_connector=from_designator,
            from_pin=ws.from_pin,
            cable=cable_designator,
            wire=i + 1,
            to_connector=endpoint_designators[ws.to_endpoint],
            to_pin=ws.to_pin,
        )
        for i, ws in enumerate(conn.wires)
    )

    # Title: source <-> all target designators
    all_targets = ", ".join(
        f"{conn.to_endpoints[i].device}-{conn.to_endpoints[i].connector}"
        for i in range(n_endpoints)
    )
    title = f"{from_designator} <-> {all_targets}"

    return CableDrawing(
        cable=cable,
        connectors=(source, *target_connectors),
        connections=connections,
        title=title,
    )


def build_inter_device_drawings(
    connections: list[InterDeviceConnection],
    cable_prefix: str = "A-W",
    cable_start: int = 1,
) -> list[CableDrawing]:
    """Build one CableDrawing per device-to-device cable connection.

    Each ``InterDeviceConnection`` becomes exactly one drawing regardless of
    fan-out degree.  Cable designators are assigned sequentially from *cable_start*.

    Args:
        connections: List of ``InterDeviceConnection`` objects describing
            device-to-device wiring (from/to device tags, connector designators,
            and cable properties).
        cable_prefix: Prefix for generated cable designators.
        cable_start: First cable number to assign.

    Returns:
        list[CableDrawing]: One ``CableDrawing`` per connection, in input order.

    Raises:
        CableError: If the pin counts on the two connector sides differ, or if
            neither side provides connector pins and the cable has no
            ``wire_colors`` to derive a pin count from, or if a WireSpec
            references an out-of-range endpoint index.

    Examples:
        >>> from schematika.cable.builder import build_inter_device_drawings
        >>> drawings = build_inter_device_drawings([])
        >>> drawings
        []
    """
    drawings: list[CableDrawing] = []
    cable_number = cable_start
    for conn in connections:
        cable_designator = f"{cable_prefix}{cable_number:03d}"
        drawings.append(_build_inter_device_drawing(conn, cable_designator))
        cable_number += 1
    return drawings
