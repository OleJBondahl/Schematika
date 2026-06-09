"""Turn an OverviewInput snapshot into a fully-populated OverviewGraph."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from schematika.overview.layout import _natural_key
from schematika.overview.model import (
    OverviewGraph,
    Pin,
    Signal,
    build_graph,
    pin_id,
)

if TYPE_CHECKING:
    from schematika.overview.inputs import OverviewInput


def _mark_field_devices(
    graph: OverviewGraph, field_tags: frozenset[str]
) -> OverviewGraph:
    new_devices = tuple(
        dataclasses.replace(d, device_class="FIELD") if d.id in field_tags else d
        for d in graph.devices
    )
    new_pins = tuple(
        dataclasses.replace(p, device_class="FIELD") if p.device in field_tags else p
        for p in graph.pins
    )
    return dataclasses.replace(graph, devices=new_devices, pins=new_pins)


def _inject_spare_terminal_pins(graph: OverviewGraph) -> OverviewGraph:
    # Group pins by device for terminal devices (class "X")
    dev_pins: dict[str, list[Pin]] = {}
    for p in graph.pins:
        if p.device_class == "X":
            dev_pins.setdefault(p.device, []).append(p)

    max_sid = max((p.signal_id for p in graph.pins), default=-1)
    next_sid = max_sid + 1

    new_pins: list[Pin] = list(graph.pins)
    new_signals: list[Signal] = list(graph.signals)

    for dev, existing_pins in dev_pins.items():
        pin_labels = [p.pin for p in existing_pins]
        # Skip if any pin has a ":" (capacity not determinable)
        if any(":" in lbl for lbl in pin_labels):
            continue
        # Skip unless all pins are pure integers
        if not pin_labels or not all(lbl.isdigit() for lbl in pin_labels):
            continue
        int_vals = [int(lbl) for lbl in pin_labels]
        mn, mx = min(int_vals), max(int_vals)
        used = set(int_vals)
        conn_id = f"{dev}."  # connector id for empty-connector X devices
        for n in range(mn, mx + 1):
            if n in used:
                continue
            pin_label = str(n)
            pid = pin_id(dev, "", pin_label)
            sid = next_sid
            next_sid += 1
            new_pins.append(
                Pin(
                    id=pid,
                    device=dev,
                    connector="",
                    pin=pin_label,
                    signal_id=sid,
                    device_class="X",
                    parent=conn_id,
                    pin_role="normal",
                )
            )
            new_signals.append(
                Signal(
                    id=sid,
                    pins=(pid,),
                    labels=(),
                    boards=(),
                    net_class="signal",
                )
            )

    return dataclasses.replace(graph, pins=tuple(new_pins), signals=tuple(new_signals))


def _assign_terminal_anchors(graph: OverviewGraph) -> OverviewGraph:
    # Build ordered list of field devices
    field_ids = sorted(
        (d.id for d in graph.devices if d.device_class == "FIELD"),
        key=_natural_key,
    )
    field_order: dict[str, int] = {fid: i for i, fid in enumerate(field_ids)}

    # Map each pin_id to its device
    pin_to_device: dict[str, str] = {p.id: p.device for p in graph.pins}

    # For each terminal device, collect field-row indices it connects to via edges
    term_rows: dict[str, list[int]] = {}
    for edge in graph.edges:
        dev_a = pin_to_device.get(edge.a)
        dev_b = pin_to_device.get(edge.b)
        if dev_a in field_order and dev_b is not None:
            term_rows.setdefault(dev_b, []).append(field_order[dev_a])
        if dev_b in field_order and dev_a is not None:
            term_rows.setdefault(dev_a, []).append(field_order[dev_b])

    new_devices = tuple(
        dataclasses.replace(
            d,
            anchor=sum(term_rows[d.id]) / len(term_rows[d.id])
            if d.id in term_rows
            else 1e9,
        )
        if d.device_class == "X"
        else d
        for d in graph.devices
    )
    return dataclasses.replace(graph, devices=new_devices)


def graph_from_input(inp: OverviewInput) -> OverviewGraph:
    """Build a fully-populated OverviewGraph from an OverviewInput snapshot."""
    graph = build_graph(
        [(w.a, w.b, w.label) for w in inp.wires],
        [],
        [],
        [],
        {},
    )
    graph = _mark_field_devices(graph, inp.field_device_tags)
    graph = _inject_spare_terminal_pins(graph)
    return _assign_terminal_anchors(graph)
