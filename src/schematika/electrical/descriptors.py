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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.core.exceptions import CircuitValidationError
from schematika.core.options import (
    BuildOptions,
    DescriptorBuildOptions,
    SymbolConfig,
    TerminalConfig,
)
from schematika.electrical.model.core import SymbolFactory

if TYPE_CHECKING:
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
    *,
    options: DescriptorBuildOptions | None = None,
) -> "BuildResult":
    """Build a circuit from a list of descriptors.

    Args:
        state: Autonumbering state.
        descriptors: List of RefDescriptor, CompDescriptor, or TermDescriptor.
        options: Layout + tagging knobs. ``None`` uses defaults
            (``x=0, y=0, spacing=80, count=1``, all reuse fields ``None``).
            See :class:`DescriptorBuildOptions`.

    Returns:
        BuildResult with state, circuit, used_terminals, and component_map.
    """
    opts = options or DescriptorBuildOptions()

    if not descriptors:
        msg = "Cannot build circuit with empty descriptor list"
        raise CircuitValidationError(msg)
    x, y = (opts.position.x, opts.position.y) if opts.position else (opts.x, opts.y)

    from schematika.electrical.builder import CircuitBuilder

    builder = CircuitBuilder(state)
    builder.set_layout(x=x, y=y, spacing=opts.spacing)

    for desc in descriptors:
        if isinstance(desc, RefDescriptor):
            builder.add_reference(desc.terminal_id)
        elif isinstance(desc, CompDescriptor):
            pins = desc.pins if desc.pins else None
            builder.add_symbol(
                desc.symbol_fn,
                config=SymbolConfig(tag_prefix=desc.tag_prefix, pins=pins),
            )
        elif isinstance(desc, TermDescriptor):
            builder.add_terminal(
                desc.terminal_id,
                config=TerminalConfig(poles=desc.poles, pins=desc.pins),
            )

    return builder.build(
        options=BuildOptions(
            count=opts.count,
            wire_labels=opts.wire_labels,
            reuse_tags=opts.reuse_tags,
            tag_generators=opts.tag_generators,
            start_indices=opts.start_indices,
            terminal_start_indices=opts.terminal_start_indices,
        )
    )
