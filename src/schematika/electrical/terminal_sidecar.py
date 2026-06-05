"""Terminal-CSV residue carried alongside Wires (the C3a sidecar).

A `Wire` carries only topology + net. The terminal CSV also needs, per wire,
which endpoint is the key terminal (CSV col 2/3) and its top/bottom side, plus
terminal-level metadata (placeholder pins, bridge defs). That residue lives here
so Layer-1 `Wire`/`PinRef` stay pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from schematika.electrical.utils.terminal_bridges import ConnectionDef


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalWireFact:
    """Per-wire terminal-CSV role for one terminal-touching Wire.

    Attributes:
        anchor: Which endpoint is the key terminal (CSV "Terminal Tag"/"Terminal
            Pin", cols 2/3) -- ``"source"`` or ``"target"``.
        side: ``"top"`` (FROM/panel cols 0/1) or ``"bottom"`` (TO/field cols 4/5).

    Examples:
        >>> from schematika.electrical.terminal_sidecar import TerminalWireFact
        >>> TerminalWireFact(anchor="source", side="top").side
        'top'
    """

    anchor: Literal["source", "target"]
    side: Literal["top", "bottom"]


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalSidecar:
    """The terminal-CSV residue paired with an emitted wires tuple.

    ``facts`` is parallel (by index) to the wires it describes. The rest is
    terminal-level metadata reproduced from the panel ``Terminal``/``BuildResult``
    state, enough to rebuild ``system_terminals.csv`` via ``terminal_csv_rows``.

    Attributes:
        facts: One `TerminalWireFact` per wire, same index order as the wires.
        allocated_pin_keys: ``(terminal_tag, terminal_pin)`` for every allocated
            pin (including unconnected ones -> placeholder rows).
        bridge_defs: ``terminal_tag -> ConnectionDef`` (non-prefix bridges).
        prefix_bridge_tags: terminals with ``BridgeMode.PER_PREFIX``.

    Examples:
        >>> from schematika.electrical.terminal_sidecar import (
        ...     TerminalSidecar, TerminalWireFact)
        >>> sc = TerminalSidecar(facts=(TerminalWireFact(anchor="target",
        ...     side="bottom"),), allocated_pin_keys=(("X1", "1"),),
        ...     bridge_defs={}, prefix_bridge_tags=frozenset())
        >>> sc.allocated_pin_keys
        (('X1', '1'),)
    """

    facts: tuple[TerminalWireFact, ...]
    allocated_pin_keys: tuple[tuple[str, str], ...]
    bridge_defs: Mapping[str, ConnectionDef]
    prefix_bridge_tags: frozenset[str]
