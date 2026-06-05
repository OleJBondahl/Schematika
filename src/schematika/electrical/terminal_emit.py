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

from schematika.electrical.utils.export_utils import finalize_terminal_csv

if TYPE_CHECKING:
    from schematika.catalog.wires import Wire
    from schematika.electrical.terminal_sidecar import TerminalSidecar

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


def terminal_csv_rows(
    wires: tuple[Wire, ...],
    sidecar: TerminalSidecar,
    external_rows: list,
    csv_path: str,
) -> None:
    """Write ``system_terminals.csv`` from (wires, sidecar), reusing finalize.

    Each wire is described by ``sidecar.facts[i]``: ``anchor`` picks the
    key-terminal endpoint (cols 2/3), ``side`` picks top (FROM) vs bottom (TO).
    Rows are grouped by ``(terminal_tag, terminal_pin)`` and same-side component
    tags/pins joined with ``" / "``, exactly like ``export_registry_to_csv``;
    ``allocated_pin_keys`` add empty placeholder rows. Then
    ``finalize_terminal_csv`` (append externals, bridges, merge/sort) runs.

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

    finalize_terminal_csv(
        csv_path,
        bridge_defs=dict(sidecar.bridge_defs) or None,
        prefix_bridge_tags=set(sidecar.prefix_bridge_tags) or None,
        external_connections=external_rows or None,
    )
