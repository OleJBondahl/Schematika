"""Native Wire+sidecar terminal-CSV emission (C3a).

`terminal_csv_rows` rebuilds the panel rows from (wires, sidecar) exactly like
`export_registry_to_csv`, then reuses `finalize_terminal_csv` verbatim, so the
output is byte-identical to the legacy TerminalRegistry path.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire
from schematika.electrical.builder_models import BridgeMode
from schematika.electrical.terminal_sidecar import TerminalSidecar, TerminalWireFact
from schematika.electrical.utils.export_utils import finalize_terminal_csv

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from schematika.core.connection_registry import TerminalRegistry
    from schematika.electrical.harness import PlcAssignment
    from schematika.electrical.terminal import Terminal
    from schematika.electrical.utils.terminal_bridges import ConnectionDef

_HEADER = [
    "Component From",
    "Pin From",
    "Terminal Tag",
    "Terminal Pin",
    "Component To",
    "Pin To",
]


def _pin_sort_key(k: tuple[str, str]) -> tuple:
    """Sort key for (terminal_tag, pin) pairs — mirrors export_registry_to_csv."""
    t, p = k
    p_str = str(p)
    if ":" in p_str:
        prefix, num_str = p_str.rsplit(":", 1)
        try:
            return (t, 0, prefix, int(num_str))
        except ValueError:
            pass
    try:
        return (t, 1, "", int(p_str))
    except (ValueError, TypeError):
        return (t, 2, "", 0, p_str)


def _group_wire_facts_by_terminal(
    pairs: Iterable[tuple[Wire, TerminalWireFact]],
) -> dict[tuple[str, str], dict[str, list[tuple[str, str]]]]:
    """Group (wire, fact) pairs by key terminal, bucketed by side.

    ``anchor`` picks the key-terminal endpoint (cols 2/3 downstream); the
    other endpoint goes into the ``top`` (FROM, cols 0/1) or ``bottom`` (TO,
    cols 4/5) bucket per ``fact.side``. Shared by ``terminal_csv_rows``'s
    per-wire main pass and ``_route_wires_to_rows``'s route-wire pass below --
    both need multiple entries landing on one key terminal's same side joined
    together (via ``" / "``, applied by the caller) rather than built as
    independent rows, which would let ``merge_terminal_csv``'s duplicate-key
    merge combine them with its FROM/TO "balance" heuristic (built for a
    field-wire + external-wire pass-through) and fabricate a connection
    between the two *other* sides that never existed.
    """
    grouped: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = defaultdict(
        lambda: {"top": [], "bottom": []}
    )
    for wire, fact in pairs:
        term = wire.source if fact.anchor == "source" else wire.target
        comp = wire.target if fact.anchor == "source" else wire.source
        grouped[(str(term.device), term.port_id)][fact.side].append(
            (str(comp.device), comp.port_id)
        )
    return grouped


def _join_sides(sides: dict[str, list[tuple[str, str]]]) -> tuple[str, str, str, str]:
    """Join a key terminal's top/bottom entries into (from_comp, pin, to_comp, pin)."""
    from_comp = " / ".join(c for c, _ in sides["top"])
    from_pin = " / ".join(p for _, p in sides["top"])
    to_comp = " / ".join(c for c, _ in sides["bottom"])
    to_pin = " / ".join(p for _, p in sides["bottom"])
    return from_comp, from_pin, to_comp, to_pin


def _route_wires_to_rows(
    route_wires: tuple[tuple[Wire, TerminalWireFact], ...],
) -> list[list[str]]:
    """One CSV row per key terminal among ``route_wires``.

    Matches a hand-built ``internal_wiring`` tuple -- see
    ``_group_wire_facts_by_terminal`` for why grouping (rather than one row
    per entry) matters here.
    """
    grouped = _group_wire_facts_by_terminal(route_wires)
    rows: list[list[str]] = []
    for (tag, pin), sides in grouped.items():
        from_comp, from_pin, to_comp, to_pin = _join_sides(sides)
        rows.append([from_comp, from_pin, tag, pin, to_comp, to_pin])
    return rows


def plc_assignments_by_net(
    assignments: tuple[PlcAssignment, ...],
) -> dict[NetId, PlcAssignment]:
    """Index PLC assignments by the net the channel serves (one per net).

    A field-device route carries a unique net per device pin, so each net maps
    to at most one assignment; the device->terminal wire on that net recovers
    its PLC designation/channel pin from here. Reused by the PLC-report path.
    """
    return {a.net: a for a in assignments}


def field_device_rows(
    wires: tuple[Wire, ...],
    assignments: tuple[PlcAssignment, ...],
) -> list[list[str]]:
    """One verbatim CSV row per field-device pin, recovered from harness wires.

    A field-device pin is a route ``device -> terminal[-> plc]``. The
    device->terminal leg supplies cols 0-3; if its net has a ``PlcAssignment``
    (a ``-> plc`` leg existed), that supplies the resolved PLC designation
    (col 4, ``"PLC:<module>"``) and channel pin (col 5). Pins with no PLC leave
    cols 4/5 empty -- byte-identical to the legacy ``generate_field_connections``
    tuple ``(device, pin, terminal, terminal_pin, plc_designation, channel_pin)``.

    The device->terminal leg is identified as the wire whose source is not the
    target of another wire sharing its net (i.e. the route's first leg).
    """
    by_net: dict[NetId, list[Wire]] = defaultdict(list)
    for w in wires:
        by_net[w.net].append(w)
    plc = plc_assignments_by_net(assignments)

    rows: list[list[str]] = []
    for net, net_wires in by_net.items():
        targets = {(str(w.target.device), w.target.port_id) for w in net_wires}
        first = next(
            w
            for w in net_wires
            if (str(w.source.device), w.source.port_id) not in targets
        )
        assignment = plc.get(net)
        comp_to = f"PLC:{assignment.module}" if assignment else ""
        pin_to = assignment.pin_label if assignment else ""
        rows.append(
            [
                str(first.source.device),
                first.source.port_id,
                str(first.target.device),
                first.target.port_id,
                comp_to,
                pin_to,
            ]
        )
    return rows


def terminal_csv_rows(
    wires: tuple[Wire, ...],
    sidecar: TerminalSidecar,
    external_rows: list,
    csv_path: str,
    route_wires: tuple[tuple[Wire, TerminalWireFact], ...] = (),
) -> None:
    """Write ``system_terminals.csv`` from (wires, sidecar), reusing finalize.

    Each wire is described by ``sidecar.facts[i]``: ``anchor`` picks the
    key-terminal endpoint (cols 2/3), ``side`` picks top (FROM) vs bottom (TO).
    Rows are grouped by ``(terminal_tag, terminal_pin)`` and same-side component
    tags/pins joined with ``" / "``, exactly like ``export_registry_to_csv``;
    ``allocated_pin_keys`` add empty placeholder rows. Then
    ``finalize_terminal_csv`` (append externals, bridges, merge/sort) runs.

    Args:
        wires: Terminal-strip wires, one per ``sidecar.facts`` entry.
        sidecar: Per-wire anchor/side facts plus allocated pin keys, bridge
            definitions and prefix-bridge tags.
        external_rows: External connection rows appended by ``finalize_terminal_csv``.
        csv_path: Destination path for ``system_terminals.csv``.
        route_wires: ``(Wire, TerminalWireFact)`` pairs grouped by key terminal
            and appended one row per key (joining same-side entries with
            ``" / "``, like the main per-wire pass below), matching hand-built
            ``internal_wiring`` tuples.

    Returns:
        None. The CSV is written to ``csv_path`` as a side effect.

    Examples:
        >>> callable(terminal_csv_rows)
        True
    """
    grouped = _group_wire_facts_by_terminal(zip(wires, sidecar.facts, strict=True))

    # Write all allocated keys pre-bridge: connected ones with data, unconnected
    # ones as empty placeholder rows ["","",tag,pin,"",""].  Writing them here
    # (before finalize_terminal_csv) means update_csv_with_internal_connections
    # sees those pins and assigns bridge values to them — matching the legacy
    # export_registry_to_csv(state=...) path.  Purely gap-fill keys (within
    # 1..max_connected but not allocated) are added later by _fill_empty_pin_slots
    # after bridges, and those correctly get no bridge value.
    write_keys = sorted(
        set(grouped) | set(sidecar.allocated_pin_keys),
        key=_pin_sort_key,
    )

    with Path(csv_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_HEADER)
        for t_tag, t_pin in write_keys:
            data = grouped.get((t_tag, t_pin))
            if data:
                from_comp, from_pin, to_comp, to_pin = _join_sides(data)
                writer.writerow([from_comp, from_pin, t_tag, t_pin, to_comp, to_pin])
            else:
                writer.writerow(["", "", t_tag, t_pin, "", ""])

    appended = list(external_rows) + _route_wires_to_rows(route_wires)
    finalize_terminal_csv(
        csv_path,
        bridge_defs=dict(sidecar.bridge_defs) or None,
        prefix_bridge_tags=set(sidecar.prefix_bridge_tags) or None,
        external_connections=appended or None,
    )


def panel_terminal_emit(
    registry: TerminalRegistry,
    terminals: Mapping[str, Terminal],
    *,
    allocated_pin_keys: tuple[tuple[str, str], ...],
    bridge_groups: Mapping[str, list[tuple[int, int]]],
) -> tuple[tuple[Wire, ...], TerminalSidecar]:
    """Convert a panel TerminalRegistry + Terminal/bridge metadata into Wire+sidecar.

    Each `Connection` becomes one `Wire` (component endpoint -> terminal endpoint,
    anchor="target"); `side` is copied into the fact.

    bridge_defs/prefix_bridge_tags are assembled exactly as `_generate_system_csv`:
    Terminal.bridge (set and not Terminal.reference) -> PER_PREFIX to prefix tags,
    else to bridge_defs; then bridge_groups extended per key.

    Args:
        registry: Panel terminal registry whose connections become wires.
        terminals: Terminal metadata by id, supplying bridge/reference info.
        allocated_pin_keys: ``(terminal_tag, terminal_pin)`` keys to materialise,
            including unconnected placeholders.
        bridge_groups: Per-terminal bridge pin-index groups to merge into
            ``bridge_defs``.

    Returns:
        A ``(wires, sidecar)`` pair: one ``Wire`` per registry connection plus the
        ``TerminalSidecar`` carrying facts, allocated keys and bridge data.

    Examples:
        >>> callable(panel_terminal_emit)
        True
    """
    wires: list[Wire] = []
    facts: list[TerminalWireFact] = []
    for conn in registry.connections:
        wires.append(
            Wire(
                net=NetId(f"{conn.component_tag}_{conn.component_pin}"),
                source=PinRef(
                    device=DeviceTag(conn.component_tag), port_id=conn.component_pin
                ),
                target=PinRef(
                    device=DeviceTag(conn.terminal_tag), port_id=conn.terminal_pin
                ),
            )
        )
        facts.append(TerminalWireFact(anchor="target", side=conn.side))  # ty: ignore[invalid-argument-type]

    bridge_defs: dict[str, ConnectionDef] = {}
    prefix_bridge_tags: set[str] = set()
    for tid, t in terminals.items():
        if t.bridge and not t.reference:
            if t.bridge == BridgeMode.PER_PREFIX:
                prefix_bridge_tags.add(tid)
            else:
                bridge_defs[tid] = t.bridge
    for key, groups in bridge_groups.items():
        existing = bridge_defs.setdefault(key, [])
        if isinstance(existing, list):
            existing.extend(groups)

    sidecar = TerminalSidecar(
        facts=tuple(facts),
        allocated_pin_keys=allocated_pin_keys,
        bridge_defs=bridge_defs,
        prefix_bridge_tags=frozenset(prefix_bridge_tags),
    )
    return tuple(wires), sidecar
