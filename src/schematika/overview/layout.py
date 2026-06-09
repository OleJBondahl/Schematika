"""Default 3-zone device positioning: internal | terminals | field."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from schematika.overview.model import DeviceNode, OverviewGraph

_COL_GAP = 760
_ROW_GAP = 640
_FIELD_ROW_GAP = 190
_FIELD_GROUP_GAP = 150
_X_ROW_GAP = 240

_INTERNAL_ORDER = ("PLC", "G", "PSU", "U", "K", "FT", "F", "Q", "CT")

Layout = Callable[[OverviewGraph], OverviewGraph]


def _natural_key(device_id: str) -> tuple[str, int, str]:
    """Stable sort key: (prefix, numeric suffix, full id)."""
    i = len(device_id)
    while i > 0 and device_id[i - 1].isdigit():
        i -= 1
    num = int(device_id[i:]) if i < len(device_id) else -1
    return (device_id[:i], num, device_id)


def _location(device_id: str) -> str:
    """Last hyphen-separated segment, e.g. 'PU-01-CX' -> 'CX'; '' if none."""
    return device_id.rpartition("-")[2] if "-" in device_id else ""


def _column_rank(cls: str) -> tuple[int, int]:
    if cls == "FIELD":
        return (3, 0)
    if cls == "X":
        return (2, 0)
    if cls in _INTERNAL_ORDER:
        return (0, _INTERNAL_ORDER.index(cls))
    return (1, 0)


def _place_uniform(members: list[DeviceNode], x: float, gap: float) -> list[DeviceNode]:
    members = sorted(members, key=lambda d: _natural_key(d.id))
    n = len(members)
    return [
        dataclasses.replace(
            d, x=round(float(x), 2), y=round((row - (n - 1) / 2) * gap, 2)
        )
        for row, d in enumerate(members)
    ]


def _place_terminals(members: list[DeviceNode], x: float) -> list[DeviceNode]:
    """Tightly stack terminals ordered by anchor (then natural id)."""
    members = sorted(
        members,
        key=lambda d: (d.anchor if d.anchor is not None else 1e9, _natural_key(d.id)),
    )
    n = len(members)
    return [
        dataclasses.replace(
            d,
            x=round(float(x), 2),
            y=round((row - (n - 1) / 2) * _X_ROW_GAP, 2),
        )
        for row, d in enumerate(members)
    ]


def _place_field(members: list[DeviceNode], x: float) -> list[DeviceNode]:
    members = sorted(members, key=lambda d: (_location(d.id), _natural_key(d.id)))
    ys: list[float] = []
    y = 0.0
    prev_loc: str | None = None
    for d in members:
        loc = _location(d.id)
        if prev_loc is not None and loc != prev_loc:
            y += _FIELD_GROUP_GAP
        ys.append(y)
        y += _FIELD_ROW_GAP
        prev_loc = loc
    mid = (ys[0] + ys[-1]) / 2 if ys else 0.0
    return [
        dataclasses.replace(d, x=round(float(x), 2), y=round(yy - mid, 2))
        for d, yy in zip(members, ys, strict=True)
    ]


def compute_device_positions(graph: OverviewGraph) -> OverviewGraph:
    """Return a new OverviewGraph with deterministic x/y set on each DeviceNode."""
    if not graph.devices:
        return graph

    by_class: dict[str, list[DeviceNode]] = {}
    for d in graph.devices:
        by_class.setdefault(d.device_class, []).append(d)

    all_placed: list[DeviceNode] = []
    for col, cls in enumerate(sorted(by_class, key=_column_rank)):
        x = col * _COL_GAP
        if cls == "FIELD":
            all_placed.extend(_place_field(by_class[cls], x))
        elif cls == "X":
            all_placed.extend(_place_terminals(by_class[cls], x))
        else:
            all_placed.extend(_place_uniform(by_class[cls], x, _ROW_GAP))

    return dataclasses.replace(graph, devices=tuple(all_placed))
