"""Inline circuit descriptors for Schematika.

Provides lightweight descriptor types for defining linear circuits
declaratively without needing a builder function.

Usage:
    from schematika.electrical import ref, comp, term
    from schematika.electrical.symbols import coil

    components = [
        ref("PLC:DO"),
        comp(coil, "K", pins=("A1", "A2")),
        term("X103"),
    ]
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.model.core import SymbolFactory

if TYPE_CHECKING:
    from schematika.core.geometry import Point
    from schematika.electrical.builder import BuildResult
    from schematika.electrical.model.state import GenerationState


@dataclass(frozen=True)
class RefDescriptor:
    """Describes a reference symbol (PLC, etc.)."""

    terminal_id: str


@dataclass(frozen=True)
class CompDescriptor:
    """Describes a component with tag prefix and pins."""

    symbol_fn: SymbolFactory  # symbol factory function
    tag_prefix: str
    pins: tuple[str, ...] = ()


@dataclass(frozen=True)
class TermDescriptor:
    """Describes a physical terminal."""

    terminal_id: str
    poles: int = 1
    pins: tuple[str, ...] | None = None


def ref(terminal_id: str) -> RefDescriptor:
    """Create a reference descriptor (PLC, etc.)."""
    return RefDescriptor(terminal_id)


def comp(
    symbol_fn: SymbolFactory, tag_prefix: str, pins: tuple[str, ...] = ()
) -> CompDescriptor:
    """Create a component descriptor."""
    return CompDescriptor(symbol_fn, tag_prefix, pins)


def term(
    terminal_id: str, poles: int = 1, pins: tuple[str, ...] | None = None
) -> TermDescriptor:
    """Create a terminal descriptor."""
    return TermDescriptor(terminal_id, poles, pins)


Descriptor = RefDescriptor | CompDescriptor | TermDescriptor


def build_from_descriptors(
    state: "GenerationState",
    descriptors: list[Descriptor],
    x: float = 0.0,
    y: float = 0.0,
    *,
    position: "Point | None" = None,
    spacing: float = 80.0,
    count: int = 1,
    wire_labels: list[str] | None = None,
    reuse_tags: dict[str, Any] | None = None,
    tag_generators: dict[str, Callable] | None = None,
    start_indices: dict[str, int] | None = None,
    terminal_start_indices: dict[str, int] | None = None,
) -> "BuildResult":
    """Build a circuit from a list of descriptors.

    Creates a CircuitBuilder internally, calls add_reference/add_symbol/add_terminal
    for each descriptor, and builds with the given parameters.

    Args:
        state: Autonumbering state.
        descriptors: List of RefDescriptor, CompDescriptor, or TermDescriptor.
        x: Start X position.
        y: Start Y position.
        position: Starting ``Point`` — when set, overrides *x* and *y*.
        spacing: Horizontal spacing between instances.
        count: Number of instances to build.
        wire_labels: Wire label strings per instance.
        reuse_tags: Dict mapping tag prefix to BuildResult for tag reuse.
        tag_generators: Custom tag generator functions.
        start_indices: Override tag counters.
        terminal_start_indices: Override terminal pin counters.

    Returns:
        BuildResult with state, circuit, used_terminals, and component_map.
    """
    if not descriptors:
        msg = "Cannot build circuit with empty descriptor list"
        raise CircuitValidationError(msg)
    if position is not None:
        x, y = position.x, position.y
    from schematika.electrical.builder import CircuitBuilder

    builder = CircuitBuilder(state)
    builder.set_layout(x=x, y=y, spacing=spacing)

    for desc in descriptors:
        if isinstance(desc, RefDescriptor):
            builder.add_reference(desc.terminal_id)
        elif isinstance(desc, CompDescriptor):
            pins = desc.pins if desc.pins else None
            builder.add_symbol(desc.symbol_fn, desc.tag_prefix, pins=pins)
        elif isinstance(desc, TermDescriptor):
            builder.add_terminal(desc.terminal_id, poles=desc.poles, pins=desc.pins)

    return builder.build(
        count=count,
        wire_labels=wire_labels,
        reuse_tags=reuse_tags,
        tag_generators=tag_generators,
        start_indices=start_indices,
        terminal_start_indices=terminal_start_indices,
    )
