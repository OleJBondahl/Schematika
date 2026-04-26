"""Frozen option-bundle dataclasses for CircuitBuilder.add_* / build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from schematika.core.geometry import Point
    from schematika.core.symbol import SymbolFactory
    from schematika.electrical.builder import CircuitBuilder
    from schematika.electrical.builder_models import (
        BridgeMode,
        BuildResult,
        ComponentRef,
        PortRef,
    )
    from schematika.electrical.internal_device import InternalDevice
    from schematika.electrical.model.constants import LabelPosition, Position, Side
    from schematika.electrical.model.state import GenerationState


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


@dataclass(frozen=True, slots=True, kw_only=True)
class BuildOptions:
    """Options bundle for :meth:`CircuitBuilder.build` (count, state, reuse, labels)."""

    count: int = 1
    state: GenerationState | None = None
    wire_labels: Sequence[str] | None = None
    connection_log_path: str | Path | None = None
    start_indices: Mapping[str, int] | None = None
    terminal_start_indices: Mapping[str, int] | None = None
    tag_generators: Mapping[str, Callable[..., Any]] | None = None
    fixed_tags: Mapping[str, str] | None = None
    terminal_maps: Mapping[str, Any] | None = None
    reuse_tags: Mapping[str, BuildResult] | None = None
    reuse_terminals: (
        Mapping[str, BuildResult | CircuitBuilder | Callable[..., Any]] | None
    ) = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DescriptorBuildOptions:
    """Layout + tagging options for build_from_descriptors."""

    position: Point | None = None
    x: float = 0.0
    y: float = 0.0
    spacing: float = 80.0
    count: int = 1
    wire_labels: tuple[str, ...] | None = None
    reuse_tags: Mapping[str, Any] | None = None
    tag_generators: Mapping[str, Callable[..., Any]] | None = None
    start_indices: Mapping[str, int] | None = None
    terminal_start_indices: Mapping[str, int] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class HorizontalLayoutConfig:
    """All knobs for create_horizontal_layout."""

    start_x: float
    start_y: float
    count: int
    spacing: float
    generator_func_single: Callable[..., Any]
    default_tag_generators: Mapping[str, Callable[..., Any]]
    tag_generators: Mapping[str, Callable[..., Any]] | None = None
    terminal_maps: Mapping[str, Any] | None = None


# private — convention: underscore-prefixed bundles for tier-3 callers
# placed/walked_chain_nets/placed_slices: contents are mutated in place
# during walk; frozen=True only blocks attribute reassignment.
@dataclass(frozen=True, slots=True, kw_only=True)
class _WalkLoopContext:
    """Mutable working state shared across _walk_loop iterations."""

    placed: list[Any]  # list[_PlacedSymbol] — forward-ref via Any to avoid pcb import
    ir: Any  # CircuitIR
    mapping: Any  # SymbolMapping
    net_kinds: Mapping[str, Any]  # dict[str, _NetKind]
    walked_chain_nets: set[str]
    placed_slices: set[tuple[str, int]]
    net_by_pin: Mapping[tuple[str, str], Any]  # NetRef


@dataclass(frozen=True, slots=True, kw_only=True)
class _ConnectionPair:
    """Endpoint pair (from + to) for _register_connection_pair dispatch."""

    # dict (not Mapping) — _resolve_registry_pin requires dict[str, Any].
    comp_from: dict[str, Any]
    pin_from: str
    side_from: str | None
    p_from: int
    comp_to: dict[str, Any]
    pin_to: str
    side_to: str | None
    p_to: int
