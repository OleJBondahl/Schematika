"""Walk a built ``Project`` plus a containment dict, return ``(units, wires)``.

Reads three private attributes of ``Project`` (``_results``,
``_external_connections``, ``_terminals``) through the three adapter
helpers below, so a future shape change in ``Project`` lands in exactly
one place. See ``docs/overview-module/05-overview-api.md`` for the
rationale.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from schematika.overview.errors import (
    OverviewContainmentError,
    OverviewExtractionError,
)
from schematika.overview.model import ConnectionKey, Unit, Wire

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from schematika.electrical.builder_models import BuildResult
    from schematika.electrical.terminal import Terminal
    from schematika.overview.model import ContainerSpec
    from schematika.project import Project


SYSTEM_CONTAINER_ID = "<system>"
SYSTEM_CONTAINER_LABEL = "System"
SYSTEM_CONTAINER_KIND = "system"

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


# ---------------------------------------------------------------------------
# Adapters — the three sites that read Project's private state
# ---------------------------------------------------------------------------


def _get_results(project: Project) -> dict[str, BuildResult]:
    results = project._results
    if not isinstance(results, dict):
        msg = (
            f"project._results is {type(results).__name__}, expected dict. "
            f"See docs/overview-module/05-overview-api.md."
        )
        raise OverviewExtractionError(msg)
    return results


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
# Containment validation + circuit -> container lookup
# ---------------------------------------------------------------------------


def _validate_containment(
    containment: Mapping[str, ContainerSpec],
    results: Mapping[str, BuildResult],
) -> None:
    """Raise ``OverviewContainmentError`` for any of the documented errors."""
    _check_id_collisions(containment, results)
    _check_parents_exist(containment)
    _check_no_cycles(containment)
    _check_circuits_exist_and_unique(containment, results)


def _check_id_collisions(
    containment: Mapping[str, ContainerSpec],
    results: Mapping[str, BuildResult],
) -> None:
    collisions = sorted(set(containment) & set(results))
    if collisions:
        msg = (
            f"Container id(s) collide with circuit key(s): {collisions}. "
            "Container ids and circuit keys share a flat namespace."
        )
        raise OverviewContainmentError(msg)


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


def _check_circuits_exist_and_unique(
    containment: Mapping[str, ContainerSpec],
    results: Mapping[str, BuildResult],
) -> None:
    seen_circuits: dict[str, str] = {}
    for cid, spec in containment.items():
        for circuit_key in spec.circuits:
            if circuit_key not in results:
                msg = (
                    f"Container '{cid}' lists circuit '{circuit_key}', "
                    f"which is not in project._results. "
                    f"Available: {sorted(results)}"
                )
                raise OverviewContainmentError(msg)
            if circuit_key in seen_circuits:
                msg = (
                    f"Circuit '{circuit_key}' is listed in two containers: "
                    f"'{seen_circuits[circuit_key]}' and '{cid}'."
                )
                raise OverviewContainmentError(msg)
            seen_circuits[circuit_key] = cid


def _circuit_to_container(
    containment: Mapping[str, ContainerSpec],
) -> dict[str, str]:
    return {
        circuit_key: cid
        for cid, spec in containment.items()
        for circuit_key in spec.circuits
    }


# ---------------------------------------------------------------------------
# Unit / wire extraction
# ---------------------------------------------------------------------------


def _container_units(
    containment: Mapping[str, ContainerSpec],
    *,
    include_system: bool,
) -> list[Unit]:
    units: list[Unit] = []
    if include_system:
        units.append(
            Unit(
                id=SYSTEM_CONTAINER_ID,
                label=SYSTEM_CONTAINER_LABEL,
                parent=None,
                is_container=True,
                ports=(),
                kind=SYSTEM_CONTAINER_KIND,
            )
        )
    for cid, spec in containment.items():
        units.append(
            Unit(
                id=cid,
                label=spec.label,
                parent=spec.parent,
                is_container=True,
                ports=(),
                kind=spec.kind,
            )
        )
    return units


def _device_units(
    results: Mapping[str, BuildResult],
    circuit_to_container: Mapping[str, str],
) -> tuple[list[Unit], set[str]]:
    units: list[Unit] = []
    unreferenced: set[str] = set()
    seen: set[str] = set()
    for circuit_key, result in results.items():
        parent = circuit_to_container.get(circuit_key)
        if parent is None:
            unreferenced.add(circuit_key)
            parent = SYSTEM_CONTAINER_ID
        for tag in result.device_registry:
            if tag in seen:
                continue
            seen.add(tag)
            units.append(
                Unit(
                    id=tag,
                    label=tag,
                    parent=parent,
                    is_container=False,
                    ports=_device_ports(result, tag),
                    kind="device",
                )
            )
        for tag, pins in result.terminal_pin_map.items():
            if tag in seen:
                continue
            seen.add(tag)
            units.append(
                Unit(
                    id=tag,
                    label=tag,
                    parent=parent,
                    is_container=False,
                    ports=tuple(pins),
                    kind="terminal",
                )
            )
    return units, unreferenced


def _device_ports(result: BuildResult, tag: str) -> tuple[str, ...]:
    """Collect distinct ports referenced by wire_connections for *tag*, in order."""
    seen: dict[str, None] = {}
    for term_tag, term_pin, comp_tag, comp_pin in result.wire_connections:
        if comp_tag == tag:
            seen.setdefault(comp_pin, None)
        if term_tag == tag:
            seen.setdefault(term_pin, None)
    return tuple(seen)


def _wire_from_row(
    row: tuple[str, str, str, str],
    classifier: Callable[[ConnectionKey], str],
) -> Wire:
    term_tag, term_pin, comp_tag, comp_pin = row
    key = ConnectionKey(
        from_unit=term_tag,
        from_port=term_pin,
        to_unit=comp_tag,
        to_port=comp_pin,
    )
    return Wire(
        from_unit=key.from_unit,
        from_port=key.from_port,
        to_unit=key.to_unit,
        to_port=key.to_port,
        kind=classifier(key),
    )


def _wire_from_external(
    row: tuple,
    classifier: Callable[[ConnectionKey], str],
) -> Wire:
    _component_from, _pin_from, terminal, terminal_pin, component_to, pin_to = row
    key = ConnectionKey(
        from_unit=str(terminal),
        from_port=str(terminal_pin),
        to_unit=str(component_to),
        to_port=str(pin_to),
    )
    return Wire(
        from_unit=key.from_unit,
        from_port=key.from_port,
        to_unit=key.to_unit,
        to_port=key.to_port,
        kind=classifier(key),
    )


def _extract_wires(
    results: Mapping[str, BuildResult],
    external: list,
    classifier: Callable[[ConnectionKey], str],
) -> list[Wire]:
    wires: list[Wire] = [
        _wire_from_row(row, classifier)
        for result in results.values()
        for row in result.wire_connections
    ]
    wires.extend(_wire_from_external(row, classifier) for row in external)
    return wires


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract(
    project: Project,
    *,
    containment: Mapping[str, ContainerSpec],
    signal_kind: Callable[[ConnectionKey], str] | None = None,
) -> tuple[list[Unit], list[Wire]]:
    """Walk a built Project plus a containment dict, return the overview graph."""
    results = _get_results(project)
    external = _get_external_connections(project)
    _get_terminals(project)  # shape-check; not yet consumed beyond external rows.

    _validate_containment(containment, results)
    classifier = signal_kind if signal_kind is not None else _default_signal_kind

    circuit_to_container = _circuit_to_container(containment)
    device_units, unreferenced = _device_units(results, circuit_to_container)

    if unreferenced:
        warnings.warn(
            f"Circuits not listed in any ContainerSpec.circuits, "
            f"falling into '{SYSTEM_CONTAINER_ID}': {sorted(unreferenced)}",
            stacklevel=2,
        )

    needs_system = bool(unreferenced) or (not results and not containment)
    units = _container_units(containment, include_system=needs_system) + device_units
    wires = _extract_wires(results, external, classifier)

    units.sort(key=lambda u: (u.parent or "", u.id))
    wires.sort(key=lambda w: (w.from_unit, w.from_port, w.to_unit, w.to_port))
    return units, wires
