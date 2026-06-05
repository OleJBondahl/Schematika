"""Wire-based inter-device cable: CableRun -> CableDrawing.

Reuses the legacy drawing helpers so the output is byte-identical to the
InterDeviceConnection path; only the input is redesigned around catalog Wires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.cable.builder import (
    DEFAULT_PIN_SORT,
    _build_cable_def,
    _build_connector_from_override,
    _fmt_des,
    _should_sort,
    _sort_synthesized_pins,
)
from schematika.cable.model import CableConnection, CableDrawing

if TYPE_CHECKING:
    from schematika.cable.builder import PinSortConfig
    from schematika.catalog.cables import CableData, ConnectorData
    from schematika.catalog.refs import PinRef
    from schematika.catalog.wires import Wire


@dataclass(frozen=True, slots=True, kw_only=True)
class CableRun:
    """A device-to-device cable declared as catalog Wires.

    A single source connector fans out to one or more targets. The cable
    designator is assigned by ``cable_pages()``, not stored here.

    Attributes:
        wires: Per-wire connections; ``net`` carries the wire label, ``color``
            the conductor color. All wires share one source connector.
            ``Wire.net`` is mandatory, so net names are always rendered as
            wire labels — there is no opt-out.
        cable: Inline cable-level spec (gauge, colors, length, note).
        connectors: Per-connector metadata, identified by the ``(device,
            connector)`` of each ``PinRef`` (``port_id`` ignored). A connector
            absent here (or carrying empty ``pins``) gets synthesized + sorted
            pins.

    Examples:
        >>> from schematika.cable.cable_run import CableRun
        >>> from schematika.catalog.cables import CableData
        >>> from schematika.catalog.identifiers import (
        ...     ConnectorId, DeviceTag, NetId)
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.catalog.wires import Wire
        >>> run = CableRun(
        ...     wires=(Wire(net=NetId("n"),
        ...         source=PinRef(device=DeviceTag("A"),
        ...             connector=ConnectorId("J1"), port_id="1"),
        ...         target=PinRef(device=DeviceTag("B"),
        ...             connector=ConnectorId("J2"), port_id="1")),),
        ...     cable=CableData(wire_gauge=0.5))
        >>> len(run.wires)
        1
    """

    wires: tuple[Wire, ...]
    cable: CableData
    connectors: tuple[tuple[PinRef, ConnectorData], ...] = ()


def _conn_key(ref: PinRef) -> tuple[str, str]:
    """Identity of the connector a pin sits on: (device, connector-or-empty)."""
    return (str(ref.device), str(ref.connector) if ref.connector is not None else "")


def cable_run_to_drawing(
    run: CableRun,
    cable_designator: str,
    pin_sort: PinSortConfig = DEFAULT_PIN_SORT,
) -> CableDrawing:
    """Build one CableDrawing for a (possibly fan-out) CableRun.

    Mirrors the fan-out branch of ``_build_inter_device_drawing`` over Wire
    input, reusing the same connector/cable/sort helpers so the drawing is
    byte-identical to the legacy InterDeviceConnection path.

    Args:
        run: The cable's wires + inline cable/connector metadata.
        cable_designator: The assigned cable tag (e.g. ``"A-W001"``).
        pin_sort: How synthesized pins are sorted.

    Returns:
        A ``CableDrawing`` ready for ``render_cable_svg``.

    Examples:
        >>> from schematika.cable.cable_run import (
        ...     CableRun, cable_run_to_drawing)
        >>> from schematika.catalog.cables import CableData
        >>> from schematika.catalog.identifiers import (
        ...     ConnectorId, DeviceTag, NetId)
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.catalog.wires import Wire
        >>> run = CableRun(
        ...     wires=(Wire(net=NetId("n"),
        ...         source=PinRef(device=DeviceTag("A"),
        ...             connector=ConnectorId("J1"), port_id="1"),
        ...         target=PinRef(device=DeviceTag("B"),
        ...             connector=ConnectorId("J2"), port_id="1")),),
        ...     cable=CableData(wire_gauge=0.5))
        >>> cable_run_to_drawing(run, "A-W001").title
        'A-J1 <-> B-J2'
    """
    cd_map = {_conn_key(ref): cd for ref, cd in run.connectors}

    # Source connector (single, shared by all wires): pins in wire order.
    src = run.wires[0].source
    from_designator = _fmt_des(*_conn_key(src))
    from_cd = cd_map.get(_conn_key(src))
    from_pins = tuple(w.source.port_id for w in run.wires)
    if _should_sort(from_cd):
        from_pins = _sort_synthesized_pins(
            from_pins,
            sort_integers=pin_sort.sort_integers,
            sort_alphabetic=pin_sort.sort_alphabetic,
        )
    source = _build_connector_from_override(from_designator, from_pins, from_cd)

    # Target connectors: collect pins in wire-first-seen order.
    target_pins: dict[tuple[str, str], list[str]] = {}
    target_order: list[tuple[str, str]] = []
    for w in run.wires:
        key = _conn_key(w.target)
        if key not in target_pins:
            target_pins[key] = []
            target_order.append(key)
        target_pins[key].append(w.target.port_id)

    target_designators: dict[tuple[str, str], str] = {}
    target_connectors = []
    for key in target_order:
        des = _fmt_des(*key)
        target_designators[key] = des
        pins = tuple(target_pins[key])
        cd = cd_map.get(key)
        if _should_sort(cd):
            pins = _sort_synthesized_pins(
                pins,
                sort_integers=pin_sort.sort_integers,
                sort_alphabetic=pin_sort.sort_alphabetic,
            )
        target_connectors.append(_build_connector_from_override(des, pins, cd))

    wirelabels = tuple(str(w.net) for w in run.wires)
    cable = _build_cable_def(
        cable_designator, len(run.wires), run.cable, wirelabels=wirelabels
    )

    connections = tuple(
        CableConnection(
            from_connector=from_designator,
            from_pin=w.source.port_id,
            cable=cable_designator,
            wire=i + 1,
            to_connector=target_designators[_conn_key(w.target)],
            to_pin=w.target.port_id,
        )
        for i, w in enumerate(run.wires)
    )

    to_designators = tuple(target_designators[key] for key in target_order)
    title = f"{from_designator} <-> {', '.join(to_designators)}"

    return CableDrawing(
        cable=cable,
        connectors=(source, *target_connectors),
        connections=connections,
        title=title,
        from_designator=from_designator,
        to_designators=to_designators,
    )
