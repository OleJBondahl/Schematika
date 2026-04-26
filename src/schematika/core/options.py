"""Frozen option-bundle dataclasses for CircuitBuilder.add_* / build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from schematika.core.geometry import Point
    from schematika.core.symbol import SymbolFactory
    from schematika.electrical.builder_models import BridgeMode, ComponentRef, PortRef
    from schematika.electrical.internal_device import InternalDevice
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


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolConfig:
    """Tag prefix, pin layout, device, wire labels, factory passthrough for a Symbol."""

    tag_prefix: str  # required
    poles: int = 1
    pins: tuple[str, ...] | None = None
    device: InternalDevice | None = None
    wire_labels_above: tuple[str, ...] | None = None
    factory_kwargs: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SpdtConfig:
    """Pin layout + IEC inversion + device + wire labels for an SPDT contact."""

    poles: int = 1
    pins: tuple[str, ...] | None = None
    inverted: bool = False
    device: InternalDevice | None = None
    wire_labels_above: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentConfig:
    """PID equipment factory + tag prefix + factory passthrough."""

    factory: SymbolFactory  # PID's SymbolFactory protocol
    tag_prefix: str
    factory_kwargs: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentPlacement:
    """PID equipment placement: anchor-relative or absolute (position/x/y)."""

    relative_to: str | None = None
    from_port: str = "outlet"
    to_port: str = "inlet"
    offset: tuple[float, float] = (0.0, 0.0)
    position: Point | None = None
    x: float = 0.0
    y: float = 0.0
