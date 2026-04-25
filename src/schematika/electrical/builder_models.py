"""Data models for the Circuit Builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any


class BridgeMode(StrEnum):
    """Bridge control: NONE, ALL, AUTO (from Terminal attr), PER_PREFIX."""

    NONE = "none"
    ALL = "all"
    AUTO = "auto"
    PER_PREFIX = "per_prefix"


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from schematika.electrical.builder import CircuitBuilder
    from schematika.electrical.internal_device import InternalDevice
    from schematika.electrical.model.constants import LabelPosition, Position, Side
    from schematika.electrical.model.core import Symbol, SymbolFactory
    from schematika.electrical.model.state import GenerationState
    from schematika.electrical.system.system import Circuit


@dataclass(frozen=True)
class LayoutConfig:
    """Configuration for circuit layout."""

    start_x: float
    start_y: float
    spacing: float = 150  # Horizontal spacing between circuit instances
    symbol_spacing: float = 50  # Vertical spacing between components
    label_pos: LabelPosition = "left"  # Default label position for terminals


@dataclass(frozen=True)
class ComponentSpec:
    """Declarative specification for a component in a circuit."""

    func: SymbolFactory | None  # None for terminals
    kind: str = "symbol"  # 'symbol' or 'terminal'
    tag_prefix: str | None = None
    poles: int = 1
    pins: list[str] | tuple[str, ...] | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)

    # Layout control
    x_offset: float = 0.0
    y_increment: float | None = None

    # Connection control
    connect_to_next: bool = True
    connection_side: Side | None = (
        None  # Override auto-determined side ('top' or 'bottom')
    )
    pin_prefixes: tuple[str, ...] | None = (
        None  # Override terminal's default pin_prefixes
    )

    # Horizontal placement reference (index of component this was placed_right of)
    placed_right_of: int | None = None

    # Vertical placement reference (index of component + pin name to place above/below)
    placed_above_of: tuple[int, str] | None = None
    placed_below_of: tuple[int, str] | None = None

    # Device metadata for BOM tracking
    device: InternalDevice | None = None

    # Bridge control for terminals
    bridge: BridgeMode = BridgeMode.NONE

    # Per-connection wire labels for the wires directly above this component
    wire_labels_above: list[str] | tuple[str, ...] | None = None

    # New unified placement fields
    relative_to_idx: int | tuple[int, str] | None = (
        None  # comp_idx, or (comp_idx, pin_name)
    )
    position: Position = "below"  # "below", "above", "left", "right"
    connect_from_previous: bool = True
    spacing_override: float | None = None

    def get_y_increment(self, default: float) -> float:
        """Return the configured y-increment, or *default* if none is set."""
        return self.y_increment if self.y_increment is not None else default


@dataclass(frozen=True)
class PlannedConnection:
    """A connection recorded at add-time, rendered in Phase 4."""

    source_idx: int  # Component index of source symbol
    target_idx: int  # Component index of target symbol
    kind: str  # "chain", "manual", "pin_placement"
    source_pole: int | None = None  # For manual: specific pole on source
    target_pole: int | None = None  # For manual: specific pole on target
    side_a: Side = "bottom"  # Connection side on source
    side_b: Side = "top"  # Connection side on target
    wire_label: str | None = None


@dataclass
class CircuitSpec:
    """Complete specification for a circuit definition."""

    components: list[ComponentSpec] = field(default_factory=list)
    layout: LayoutConfig = field(default_factory=lambda: LayoutConfig(0, 0))
    planned_connections: list[PlannedConnection] = field(default_factory=list)
    manual_connections: list[tuple[int, int, int, int, str, str]] = field(
        default_factory=list
    )
    terminal_map: dict[str, Any] = field(default_factory=dict)
    # Horizontal matching connections: (idx_a, idx_b, pin_filter, side_a, side_b)
    matching_connections: list[tuple[int, int, list[str] | None, str, str]] = field(
        default_factory=list
    )
    # Per-connection wire labels keyed by manual_connections index
    connection_wire_labels: dict[int, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ComponentRef / PortRef — named component references (Task 9A)
# ---------------------------------------------------------------------------


@dataclass
class PortRef:
    """Reference to a specific port on a component."""

    component: ComponentRef
    port: str | int  # Pin name ("L", "A1") or pole index (0, 1, 2)


@dataclass
class ComponentRef:
    """Reference to a component in a CircuitBuilder."""

    _builder: CircuitBuilder
    _index: int
    tag_prefix: str = ""

    def pin(self, pin_id: str) -> PortRef:
        """Reference a specific port by pin name."""
        return PortRef(self, pin_id)

    def pole(self, pole_idx: int) -> PortRef:
        """Reference a port by pole index (backwards compatibility)."""
        return PortRef(self, pole_idx)


def merge_reuse_tags(
    *pairs: tuple[str, BuildResult],
) -> dict[str, BuildResult]:
    """Builds a reuse_tags dict from (prefix, result) pairs."""
    return dict(pairs)


@dataclass
class BuildResult:
    """Result of a circuit build operation."""

    state: GenerationState
    circuit: Circuit
    used_terminals: list[Any]
    component_map: dict[str, list[str]] = field(default_factory=dict)
    terminal_pin_map: dict[str, list[str]] = field(default_factory=dict)
    device_registry: dict[str, InternalDevice] = field(default_factory=dict)
    wire_connections: list[tuple[str, str, str, str]] = field(default_factory=list)
    bridge_groups: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    connection_log: list[str] = field(default_factory=list)

    def __iter__(self) -> Iterator[Any]:
        """Iterate over ``(state, circuit, used_terminals)`` for tuple-unpacking."""
        return iter((self.state, self.circuit, self.used_terminals))

    def component_tag(self, prefix: str) -> str:
        """First tag for *prefix*; raises KeyError if the prefix was not used."""
        tags = self.component_map.get(prefix)
        if not tags:
            msg = (
                f"No tags for prefix '{prefix}'. "
                f"Available: {list(self.component_map.keys())}"
            )
            raise KeyError(msg)
        return tags[0]

    def component_tags(self, prefix: str) -> list[str]:
        """All tags for *prefix*; empty list if unused."""
        return list(self.component_map.get(prefix, []))

    def get_symbol(self, tag: str) -> Symbol | None:
        """Searches `circuit.symbols` then falls back to `circuit.elements`."""
        from schematika.electrical.model.core import Symbol

        # Try circuit.symbols first (populated by add_symbol path)
        result = self.circuit.get_symbol_by_tag(tag)
        if result is not None:
            return result
        # Fall back to searching elements (populated by builder path)
        for elem in self.circuit.elements:
            if isinstance(elem, Symbol) and elem.label == tag:
                return elem
        return None

    def get_symbols(self, prefix: str) -> list[Symbol]:
        """Placed symbols whose tags match *prefix*."""
        tags = self.component_map.get(prefix, [])
        result = []
        for tag in tags:
            sym = self.get_symbol(tag)
            if sym is not None:
                result.append(sym)
        return result

    def reuse_tags(self, prefix: str) -> Callable:
        """Tag generator drawing from this result's `component_map[prefix]`."""
        tags = iter(self.component_map.get(prefix, []))

        def generator(
            state: GenerationState,
        ) -> tuple[GenerationState, str]:
            from schematika.electrical.exceptions import TagReuseError

            try:
                return state, next(tags)
            except StopIteration:
                raise TagReuseError(
                    prefix, list(self.component_map.get(prefix, []))
                ) from None

        return generator

    def reuse_terminals(self, key: str) -> Callable:
        """Pin generator drawing from this result's `terminal_pin_map[key]`."""
        pins = iter(self.terminal_pin_map.get(key, []))

        def generator(
            state: GenerationState, poles: int
        ) -> tuple[GenerationState, tuple[str, ...]]:
            from schematika.electrical.exceptions import TerminalReuseError

            result = []
            for _ in range(poles):
                try:
                    result.append(next(pins))
                except StopIteration:
                    raise TerminalReuseError(
                        key, list(self.terminal_pin_map.get(key, []))
                    ) from None
            return state, tuple(result)

        return generator
