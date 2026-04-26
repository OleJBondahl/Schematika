"""Frozen option-bundle dataclasses for CircuitBuilder.add_* / build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.electrical.builder_models import BridgeMode, ComponentRef, PortRef
    from schematika.electrical.model.constants import LabelPosition, Position, Side


@dataclass(frozen=True, slots=True, kw_only=True)
class PlacementOptions:
    """Where a new component sits relative to the chain head or another component."""

    relative_to: ComponentRef | PortRef | None = None
    position: Position = "below"
    spacing: float | None = None
    x_offset: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalDisplayOptions:
    """Label-position knobs for a terminal's text labels."""

    label_pos: LabelPosition | None = None
    pin_label_pos: LabelPosition | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectionOptions:
    """Chain-wiring: previous/next, side, bridge (None=BridgeMode.NONE), wire label."""

    connect_from_previous: bool = True
    connect_to_next: bool = True
    connection_side: Side | None = None
    bridge: BridgeMode | None = None
    wire_label: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalConfig:
    """Pin layout + logical mapping for a Terminal."""

    poles: int = 1
    pins: tuple[str, ...] | None = None
    pin_prefixes: tuple[str, ...] | None = None
    logical_name: str | None = None
