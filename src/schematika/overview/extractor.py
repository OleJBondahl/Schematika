"""Walk a built ``Project`` plus a containment dict, return ``(units, wires)``.

The overview is a *boundary* view: the cabinet is one cluster containing
only the terminals that have external wiring, and field devices sit
outside that cluster as separate boxes. Cabinet-internal wires are
omitted entirely — only ``project._external_connections`` is consumed.
See ``docs/overview-module/05-overview-api.md`` for the rationale.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import TYPE_CHECKING

from schematika.overview.errors import (
    OverviewContainmentError,
    OverviewExtractionError,
)
from schematika.overview.model import ConnectionKey, Unit, Wire

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from schematika.electrical.terminal import Terminal
    from schematika.overview.model import ContainerSpec
    from schematika.project import Project


# Case-insensitive substring patterns matched against either port name.
_POWER_PATTERNS: tuple[str, ...] = (
    "+24V",
    "+12V",
    "+5V",
    "+3V3",
    "VCC",
    "VDD",
    "PWR",
    "L1",
    "L2",
    "L3",
    "PE",
    "GND",
)
# Whole-name (case-insensitive) power markers — too short for substring match.
_POWER_EXACT: frozenset[str] = frozenset({"N"})

# Field-device kind classification — matched against the device tag in order.
# First hit wins; unmatched tags fall through to "other".
_FIELD_KIND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("power", re.compile(r"^\d+V\b|\bMAIN\b|\bEM\b")),
    ("motors", re.compile(r"^(PU|FAN|F)-\d")),
    ("valves", re.compile(r"^(XV|FV|VALVE)-")),
    ("switches", re.compile(r"^S\d")),
    ("sensors", re.compile(r"^(G|LT|PT|TT|FT|LSH|LSL)-")),
)
_FIELD_KIND_LABELS: dict[str, str] = {
    "power": "Power",
    "motors": "Motors",
    "valves": "Valves",
    "switches": "Switches",
    "sensors": "Sensors",
    "other": "Other",
}
# Render order — controls which kind-cluster appears first in the DOT.
_FIELD_KIND_ORDER: tuple[str, ...] = (
    "power",
    "motors",
    "valves",
    "switches",
    "sensors",
    "other",
)


def _classify_field_kind(tag: str) -> str:
    upper = tag.upper()
    for kind, pat in _FIELD_KIND_PATTERNS:
        if pat.search(upper):
            return kind
    return "other"


def _field_container_id(kind: str) -> str:
    return f"<field_{kind}>"


# ---------------------------------------------------------------------------
# Adapters — the two sites that read Project's private state
# ---------------------------------------------------------------------------


def _get_external_connections(project: Project) -> list:
    rows = project._external_connections
    if not isinstance(rows, list):
        msg = (
            f"project._external_connections is {type(rows).__name__}, "
            f"expected list. See docs/overview-module/05-overview-api.md."
        )
        raise OverviewExtractionError(msg)
    return rows


def _get_terminals(project: Project) -> dict[str, Terminal]:
    terminals = project._terminals
    if not isinstance(terminals, dict):
        msg = (
            f"project._terminals is {type(terminals).__name__}, expected dict. "
            f"See docs/overview-module/05-overview-api.md."
        )
        raise OverviewExtractionError(msg)
    return terminals


# ---------------------------------------------------------------------------
# Default signal_kind classifier
# ---------------------------------------------------------------------------


def _default_signal_kind(key: ConnectionKey) -> str:
    for port in (key.from_port, key.to_port):
        upper = port.upper()
        if upper in _POWER_EXACT:
            return "power"
        for pat in _POWER_PATTERNS:
            if pat.upper() in upper:
                return "power"
    return "signal"


# ---------------------------------------------------------------------------
# Containment validation
# ---------------------------------------------------------------------------


def _find_cabinet_id(containment: Mapping[str, ContainerSpec]) -> str | None:
    cabinets = [cid for cid, spec in containment.items() if spec.kind == "cabinet"]
    if len(cabinets) > 1:
        msg = (
            f"Multiple containers with kind='cabinet': {sorted(cabinets)}. "
            f"v0 supports a single cabinet per overview."
        )
        raise OverviewContainmentError(msg)
    return cabinets[0] if cabinets else None


def _validate_containment(containment: Mapping[str, ContainerSpec]) -> None:
    _check_parents_exist(containment)
    _check_no_cycles(containment)


def _check_parents_exist(containment: Mapping[str, ContainerSpec]) -> None:
    for cid, spec in containment.items():
        if spec.parent is not None and spec.parent not in containment:
            msg = (
                f"Container '{cid}' has parent='{spec.parent}', "
                f"which is not a defined container id."
            )
            raise OverviewContainmentError(msg)


def _check_no_cycles(containment: Mapping[str, ContainerSpec]) -> None:
    for start in containment:
        seen: list[str] = []
        node: str | None = start
        while node is not None:
            if node in seen:
                cycle = [*seen[seen.index(node) :], node]
                msg = f"Containment cycle detected: {' -> '.join(cycle)}"
                raise OverviewContainmentError(msg)
            seen.append(node)
            node = containment[node].parent


# ---------------------------------------------------------------------------
# Boundary extraction
# ---------------------------------------------------------------------------


_MIN_ROW_LEN = 4


def _classify_rows(rows: list) -> list[tuple[str, str, str, str]]:
    """Reduce ``_external_connections`` to deduplicated boundary 4-tuples.

    Each row is ``(component_from, pin_from, terminal, terminal_pin,
    component_to, pin_to)``. The boundary crossing is terminal -> field
    device, so we project to ``(terminal, terminal_pin, device, device_pin)``
    and drop rows where either side is empty.
    """
    seen: OrderedDict[tuple[str, str, str, str], None] = OrderedDict()
    for row in rows:
        if len(row) < _MIN_ROW_LEN:
            continue
        component_from, pin_from, terminal, terminal_pin = (
            row[0],
            row[1],
            row[2],
            row[3],
        )
        if not component_from or not pin_from:
            continue
        if not terminal or not terminal_pin:
            continue
        key = (str(terminal), str(terminal_pin), str(component_from), str(pin_from))
        seen.setdefault(key, None)
    return list(seen)


def _terminal_label(terminal_id: str, terminals: Mapping[str, Terminal]) -> str:
    obj = terminals.get(terminal_id)
    title = getattr(obj, "title", "") if obj is not None else ""
    return f"{terminal_id} — {title}" if title else terminal_id


def _build_terminal_units(
    boundary: list[tuple[str, str, str, str]],
    terminals: Mapping[str, Terminal],
    cabinet_id: str | None,
) -> list[Unit]:
    """One Unit per terminal with a boundary row. Cable view — no ports."""
    seen: OrderedDict[str, None] = OrderedDict()
    for term_id, _, _, _ in boundary:
        seen.setdefault(term_id, None)

    return [
        Unit(
            id=term_id,
            label=_terminal_label(term_id, terminals),
            parent=cabinet_id,
            is_container=False,
            ports=(),
            kind="terminal",
        )
        for term_id in seen
    ]


def _build_field_units(
    boundary: list[tuple[str, str, str, str]],
) -> tuple[list[Unit], set[str]]:
    """Return (device units, set of kinds in use). No ports — cable view."""
    seen: OrderedDict[str, None] = OrderedDict()
    for _, _, device_tag, _ in boundary:
        seen.setdefault(device_tag, None)

    units: list[Unit] = []
    kinds_in_use: set[str] = set()
    for device_tag in sorted(seen):
        kind = _classify_field_kind(device_tag)
        kinds_in_use.add(kind)
        units.append(
            Unit(
                id=device_tag,
                label=device_tag,
                parent=_field_container_id(kind),
                is_container=False,
                ports=(),
                kind="field_device",
            )
        )
    return units, kinds_in_use


def _field_kind_containers(kinds_in_use: set[str]) -> list[Unit]:
    """One synthetic container per used kind, in deterministic render order."""
    return [
        Unit(
            id=_field_container_id(kind),
            label=_FIELD_KIND_LABELS[kind],
            parent=None,
            is_container=True,
            ports=(),
            kind=f"field_{kind}",
        )
        for kind in _FIELD_KIND_ORDER
        if kind in kinds_in_use
    ]


def _build_wires(
    boundary: list[tuple[str, str, str, str]],
    classifier: Callable[[ConnectionKey], str],
) -> list[Wire]:
    """Aggregate boundary rows into one cable per (terminal, device, kind) tuple.

    A "cable" stands for the bundle of physical wires running between a
    cabinet terminal and a field device. Splitting by classified kind
    keeps the power vs. signal palette honest when a single device
    happens to mix both (e.g. a motor with thermistor leads).
    """
    seen: OrderedDict[tuple[str, str, str], None] = OrderedDict()
    for term_id, term_pin, device_tag, device_pin in boundary:
        kind = classifier(
            ConnectionKey(
                from_unit=term_id,
                from_port=term_pin,
                to_unit=device_tag,
                to_port=device_pin,
            )
        )
        seen.setdefault((term_id, device_tag, kind), None)
    return [
        Wire(
            from_unit=term_id,
            from_port="",
            to_unit=device_tag,
            to_port="",
            kind=kind,
        )
        for term_id, device_tag, kind in seen
    ]


def _container_units(containment: Mapping[str, ContainerSpec]) -> list[Unit]:
    return [
        Unit(
            id=cid,
            label=spec.label,
            parent=spec.parent,
            is_container=True,
            ports=(),
            kind=spec.kind,
        )
        for cid, spec in containment.items()
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract(
    project: Project,
    *,
    containment: Mapping[str, ContainerSpec],
    signal_kind: Callable[[ConnectionKey], str] | None = None,
) -> tuple[list[Unit], list[Wire]]:
    """Return the boundary-crossing overview graph for ``project``."""
    external = _get_external_connections(project)
    terminals = _get_terminals(project)

    _validate_containment(containment)
    classifier = signal_kind if signal_kind is not None else _default_signal_kind

    boundary = _classify_rows(external)
    cabinet_id = _find_cabinet_id(containment)

    terminal_units = _build_terminal_units(boundary, terminals, cabinet_id)
    field_units, kinds_in_use = _build_field_units(boundary)
    wires = _build_wires(boundary, classifier)

    # Containers preserve render order (containment dict order, then
    # _FIELD_KIND_ORDER). Leaves sort alphabetically inside their parent.
    units = [
        *_container_units(containment),
        *_field_kind_containers(kinds_in_use),
        *sorted(terminal_units, key=lambda u: u.id),
        *sorted(field_units, key=lambda u: (u.parent or "", u.id)),
    ]
    wires.sort(key=lambda w: (w.from_unit, w.from_port, w.to_unit, w.to_port))
    return units, wires
