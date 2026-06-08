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
    from collections.abc import Mapping

    from schematika.core.connection_registry import TerminalRegistry
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


def _route_wire_to_row(wire: Wire, fact: TerminalWireFact) -> list[str]:
    """One verbatim CSV row for an external/route wire (no terminal grouping).

    ``anchor`` picks the key-terminal endpoint (cols 2/3); the other endpoint
    goes to the FROM side (cols 0/1) when ``side == "top"``, else the TO side
    (cols 4/5) -- matching a hand-built ``internal_wiring`` tuple.
    """
    term = wire.source if fact.anchor == "source" else wire.target
    comp = wire.target if fact.anchor == "source" else wire.source
    if fact.side == "top":
        return [str(comp.device), comp.port_id, str(term.device), term.port_id, "", ""]
    return ["", "", str(term.device), term.port_id, str(comp.device), comp.port_id]


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
        route_wires: ``(Wire, TerminalWireFact)`` pairs appended one verbatim row
            each (no terminal grouping), matching hand-built ``internal_wiring``
            tuples.

    Returns:
        None. The CSV is written to ``csv_path`` as a side effect.

    Examples:
        >>> callable(terminal_csv_rows)
        True
    """
    grouped: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = defaultdict(
        lambda: {"top": [], "bottom": []}
    )
    for wire, fact in zip(wires, sidecar.facts, strict=True):
        term = wire.source if fact.anchor == "source" else wire.target
        comp = wire.target if fact.anchor == "source" else wire.source
        key = (str(term.device), term.port_id)
        grouped[key][fact.side].append((str(comp.device), comp.port_id))

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
                from_comp = " / ".join(c for c, _ in data["top"])
                from_pin = " / ".join(p for _, p in data["top"])
                to_comp = " / ".join(c for c, _ in data["bottom"])
                to_pin = " / ".join(p for _, p in data["bottom"])
                writer.writerow([from_comp, from_pin, t_tag, t_pin, to_comp, to_pin])
            else:
                writer.writerow(["", "", t_tag, t_pin, "", ""])

    appended = list(external_rows) + [
        _route_wire_to_row(wire, fact) for wire, fact in route_wires
    ]
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
