"""
Fluent builder for block diagrams.

Provides :class:`BlockBuilder`, a named-graph builder where blocks are
referenced by name, placed via side-based alignment or absolute coordinates,
and connected with explicit cable declarations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.cables import CableRegistry

from schematika.block.connections import manhattan_route, render_cable
from schematika.block.constants import BLOCK_DEFAULT_HEIGHT, BLOCK_DEFAULT_WIDTH
from schematika.block.diagram import BlockDiagram
from schematika.block.model import CABLE_TYPE_STYLES, BlockPort, CableStyle
from schematika.block.symbols import block_symbol, legend_symbol
from schematika.block.templates import BlockTemplate, instantiate_template
from schematika.core.autonumbering import next_tag
from schematika.core.geometry import Element, Point
from schematika.core.state import GenerationState, create_initial_state
from schematika.core.symbol import Symbol
from schematika.core.transform import translate

__all__ = [
    "BlockBuildResult",
    "BlockBuilder",
]

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

_SIDE_PORT_MAP: dict[str, str] = {
    "left": "left",
    "right": "right",
    "top": "top",
    "bottom": "bottom",
}

_OPPOSITE_SIDE: dict[str, str] = {
    "left": "right",
    "right": "left",
    "top": "bottom",
    "bottom": "top",
}


@dataclass
class _BlockEntry:
    """Internal: all data for one block."""

    label: str
    tag: str | None
    tag_prefix: str
    width: float
    height: float
    fill: str
    ports: list[BlockPort] | None
    content: list[Element] | None
    abs_position: Point | None
    relative_to: str | None
    from_side: str
    to_side: str
    offset: tuple[float, float]


@dataclass(frozen=True)
class _CableEntry:
    """Internal: a cable connection between two named blocks."""

    from_name: str
    to_name: str
    cable_tag: str | None
    spec: str
    cable_type: str
    from_port: str
    to_port: str
    label: str
    style: CableStyle | None
    waypoints: list[tuple[float, float]] | None


@dataclass
class _LegendEntry:
    """Internal: legend configuration."""

    x: float
    y: float
    entries: list[tuple[str, CableStyle]] | None
    notes: list[str] | None


# ---------------------------------------------------------------------------
# Build result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockBuildResult:
    """Result of building a block diagram.

    Attributes:
        state: Updated :class:`GenerationState` (pass to the next builder).
        diagram: Assembled :class:`BlockDiagram`.
        block_map: Mapping of user name to generated tag
            (e.g. ``"psu"`` -> ``"BLK1"``).
    """

    state: GenerationState
    diagram: BlockDiagram
    block_map: dict[str, str]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class BlockBuilder:
    """Fluent builder for block diagrams.

    Uses a named-graph model: blocks are referenced by name, placed
    relative to other blocks via side-based alignment, and connected
    with explicit cable declarations.

    Example::

        builder = BlockBuilder()
        (
            builder
            .add_block("psu", "24V PSU", x=50, y=80)
            .add_block("plc", "PLC", relative_to="psu",
                       from_side="right", to_side="left")
            .cable("psu", "plc", cable_type="power_dc", spec="2x1.5")
        )
        result = builder.build()
    """

    def __init__(
        self,
        state: GenerationState | None = None,
        cable_registry: CableRegistry | None = None,
    ) -> None:
        self._state: GenerationState = state or create_initial_state()
        self._cable_registry = cable_registry
        self._entries: dict[str, _BlockEntry] = {}
        self._cables: list[_CableEntry] = []
        self._block_order: list[str] = []
        self._legend: _LegendEntry | None = None

    # ------------------------------------------------------------------
    # Public builder methods
    # ------------------------------------------------------------------

    def add_block(
        self,
        name: str,
        label: str,
        *,
        tag: str | None = None,
        tag_prefix: str = "BLK",
        width: float = BLOCK_DEFAULT_WIDTH,
        height: float = BLOCK_DEFAULT_HEIGHT,
        x: float = 0.0,
        y: float = 0.0,
        relative_to: str | None = None,
        from_side: str = "right",
        to_side: str = "left",
        offset: tuple[float, float] = (0.0, 0.0),
        fill: str = "none",
        ports: list[BlockPort] | None = None,
        content: list[Element] | None = None,
    ) -> BlockBuilder:
        """Add a block to the diagram.

        If ``relative_to`` is given, the block is placed so that the
        centre of its *to_side* aligns with the centre of the anchor
        block's *from_side*, plus *offset*.

        Otherwise the block is placed at the absolute position ``(x, y)``.

        Args:
            name: Unique name key for this block.
            label: Text label displayed inside the block.
            tag: Explicit tag; when ``None`` a tag is auto-generated from
                *tag_prefix*.
            tag_prefix: Prefix for auto-tag generation (default ``"BLK"``).
            width: Block width in mm.
            height: Block height in mm.
            x: Absolute x-coordinate (used when ``relative_to`` is ``None``).
            y: Absolute y-coordinate (used when ``relative_to`` is ``None``).
            relative_to: Name of the anchor block for relative placement.
            from_side: Side of the anchor block to align from.
            to_side: Side of this block to align to the anchor side.
            offset: Additional ``(dx, dy)`` offset after side alignment.
            fill: CSS fill color for the block interior.
            ports: Custom port definitions.  If ``None``, default ports at
                the centre of each side are created.
            content: Additional graphical elements to include inside the block.

        Returns:
            ``self`` for method chaining.

        Raises:
            ValueError: If *name* is already registered, or *relative_to*
                references a block that has not been registered yet.
        """
        if name in self._entries:
            raise ValueError(f"Block '{name}' already registered")

        if relative_to is not None:
            if relative_to not in self._entries:
                raise ValueError(
                    f"Cannot place '{name}' relative to '{relative_to}': "
                    f"'{relative_to}' has not been registered yet"
                )
            abs_position = None
        else:
            abs_position = Point(x, y)

        self._entries[name] = _BlockEntry(
            label=label,
            tag=tag,
            tag_prefix=tag_prefix,
            width=width,
            height=height,
            fill=fill,
            ports=ports,
            content=content,
            abs_position=abs_position,
            relative_to=relative_to,
            from_side=from_side,
            to_side=to_side,
            offset=offset,
        )
        self._block_order.append(name)
        return self

    def cable(
        self,
        from_name: str,
        to_name: str,
        *,
        cable_tag: str | None = None,
        spec: str = "",
        cable_type: str = "signal",
        from_port: str = "right",
        to_port: str = "left",
        label: str = "",
        style: CableStyle | None = None,
        waypoints: list[tuple[float, float]] | None = None,
    ) -> BlockBuilder:
        """Declare a cable connection between two blocks.

        If *cable_tag* is given and a :class:`CableRegistry` was provided
        to the builder, the registry entry is used to fill in *spec*,
        *cable_type*, and the display *label* (unless explicitly overridden).

        Args:
            from_name: Source block name.
            to_name: Target block name.
            cable_tag: Optional cable tag for registry lookup.
            spec: Inline cable specification string (e.g. ``"4x2.5"``).
            cable_type: Cable type for style mapping (default ``"signal"``).
            from_port: Port ID on the source block (default ``"right"``).
            to_port: Port ID on the target block (default ``"left"``).
            label: Override display label for the cable.
            style: Override visual style.
            waypoints: Explicit waypoints; when ``None``, manhattan routing
                is used.

        Returns:
            ``self`` for method chaining.
        """
        self._cables.append(
            _CableEntry(
                from_name=from_name,
                to_name=to_name,
                cable_tag=cable_tag,
                spec=spec,
                cable_type=cable_type,
                from_port=from_port,
                to_port=to_port,
                label=label,
                style=style,
                waypoints=waypoints,
            )
        )
        return self

    def add_legend(
        self,
        x: float,
        y: float,
        *,
        entries: list[tuple[str, CableStyle]] | None = None,
        notes: list[str] | None = None,
    ) -> BlockBuilder:
        """Add a legend at absolute position ``(x, y)``.

        Args:
            x: X-coordinate for the legend origin.
            y: Y-coordinate for the legend origin.
            entries: List of ``(label, CableStyle)`` tuples to show.
                If ``None``, the legend is auto-populated from the cable
                types used in the diagram.
            notes: Optional note strings displayed below the legend entries.

        Returns:
            ``self`` for method chaining.
        """
        self._legend = _LegendEntry(x=x, y=y, entries=entries, notes=notes)
        return self

    def add_template(
        self,
        template: BlockTemplate,
        prefix: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        mirror_x: bool = False,
    ) -> BlockBuilder:
        """Instantiate a template into the diagram.

        Each template block gets a name of ``f"{prefix}-{role}"`` and is
        placed at absolute coordinates derived from the template origin
        ``(x, y)`` plus each block's relative offset.

        When *mirror_x* is ``True``, ``rel_x`` values are negated and
        left/right port sides are swapped on cables.

        Args:
            template: The :class:`BlockTemplate` to instantiate.
            prefix: Name prefix for template blocks (e.g. ``"ups1"``).
            x: X-coordinate of the template origin.
            y: Y-coordinate of the template origin.
            mirror_x: If ``True``, flip layout horizontally.

        Returns:
            ``self`` for method chaining.
        """
        instantiate_template(self, template, prefix, x=x, y=y, mirror_x=mirror_x)
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(
        self,
        x: float = 0.0,
        y: float = 0.0,
        state: GenerationState | None = None,
    ) -> BlockBuildResult:
        """Resolve placements, generate symbols, route cables, and return the result.

        Build phases:

        1. Generate block symbols with auto-tags.
        2. Resolve placements (absolute + relative side alignment).
        3. Route cables between block ports.
        4. Build legend if requested.
        5. Assemble :class:`BlockDiagram` and return :class:`BlockBuildResult`.

        Args:
            x: Global x-offset applied to all absolute-positioned blocks.
            y: Global y-offset applied to all absolute-positioned blocks.
            state: Optional state override; defaults to the builder's state.

        Returns:
            :class:`BlockBuildResult` with the assembled diagram and updated state.
        """
        current_state = state if state is not None else self._state

        # Phase 1: Generate symbols with auto-tags
        current_state, raw_symbols, block_map = self._generate_symbols(current_state)

        # Phase 2: Resolve placements
        placed = self._resolve_placements(raw_symbols, x, y)

        # Phase 3: Route cables
        cable_elements = _route_cables(self._cables, placed, self._cable_registry)

        # Phase 4: Legend
        legend_elements = _build_legend(self._legend, self._cables)

        # Phase 5: Assemble diagram
        diagram = _assemble_diagram(
            self._block_order, placed, cable_elements, legend_elements
        )

        return BlockBuildResult(
            state=current_state,
            diagram=diagram,
            block_map=block_map,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_symbols(
        self,
        state: GenerationState,
    ) -> tuple[GenerationState, dict[str, Symbol], dict[str, str]]:
        """Phase 1: generate block symbols with auto-tags."""
        raw_symbols: dict[str, Symbol] = {}
        block_map: dict[str, str] = {}

        for name in self._block_order:
            entry = self._entries[name]
            if entry.tag is not None:
                tag = entry.tag
            else:
                state, tag = next_tag(state, entry.tag_prefix)
            sym = block_symbol(
                label=entry.label,
                width=entry.width,
                height=entry.height,
                ports=entry.ports,
                fill=entry.fill,
            )
            raw_symbols[name] = sym
            block_map[name] = tag

        return state, raw_symbols, block_map

    def _resolve_placements(
        self,
        raw_symbols: dict[str, Symbol],
        x: float,
        y: float,
    ) -> dict[str, Symbol]:
        """Phase 2: resolve absolute and relative placements."""
        placed: dict[str, Symbol] = {}

        for name in self._block_order:
            entry = self._entries[name]
            sym = raw_symbols[name]

            if entry.relative_to is None:
                assert entry.abs_position is not None
                placed[name] = translate(
                    sym, entry.abs_position.x + x, entry.abs_position.y + y
                )
            else:
                placed[name] = _place_relative(name, entry, sym, placed)

        return placed


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _place_relative(
    name: str,
    entry: _BlockEntry,
    sym: Symbol,
    placed: dict[str, Symbol],
) -> Symbol:
    """Place a block relative to an anchor block via side alignment."""
    anchor_sym = placed[entry.relative_to]  # type: ignore[index]
    anchor_port_id = _SIDE_PORT_MAP.get(entry.from_side, entry.from_side)
    my_port_id = _SIDE_PORT_MAP.get(entry.to_side, entry.to_side)

    if anchor_port_id not in anchor_sym.ports:
        available = list(anchor_sym.ports.keys())
        raise ValueError(
            f"Port '{anchor_port_id}' not found on anchor block "
            f"'{entry.relative_to}'. Available: {available}"
        )
    if my_port_id not in sym.ports:
        available = list(sym.ports.keys())
        raise ValueError(
            f"Port '{my_port_id}' not found on block '{name}'. Available: {available}"
        )

    anchor_pos = anchor_sym.ports[anchor_port_id].position
    my_pos = sym.ports[my_port_id].position
    dx = anchor_pos.x - my_pos.x + entry.offset[0]
    dy = anchor_pos.y - my_pos.y + entry.offset[1]
    return translate(sym, dx, dy)


def _build_legend(
    legend: _LegendEntry | None,
    cables: list[_CableEntry],
) -> list[Element]:
    """Phase 4: build legend elements if requested."""
    if legend is None:
        return []
    entries = legend.entries
    if entries is None:
        entries = _auto_legend_entries(cables)
    if not entries:
        return []
    leg_sym = legend_symbol(entries, notes=legend.notes)
    leg_placed = translate(leg_sym, legend.x, legend.y)
    return list(leg_placed.elements)


def _assemble_diagram(
    block_order: list[str],
    placed: dict[str, Symbol],
    cable_elements: list[Element],
    legend_elements: list[Element],
) -> BlockDiagram:
    """Phase 5: assemble block diagram from placed symbols and elements."""
    diagram = BlockDiagram()
    for name in block_order:
        if name in placed:
            sym = placed[name]
            diagram.blocks.append(sym)
            diagram.elements.extend(sym.elements)
    diagram.elements.extend(cable_elements)
    diagram.elements.extend(legend_elements)
    return diagram


def _resolve_cable_from_registry(
    entry: _CableEntry,
    cable_registry: CableRegistry | None,
) -> tuple[str, str, str, object | None]:
    """Resolve cable spec, type, label, and registry_spec from entry + registry."""
    spec = entry.spec
    cable_type = entry.cable_type
    label = entry.label
    registry_spec = None

    if entry.cable_tag is not None and cable_registry is not None:
        registry_spec = cable_registry.get(entry.cable_tag)
        if not spec:
            spec = registry_spec.spec
        if cable_type == "signal" and registry_spec.cable_type != "signal":
            cable_type = registry_spec.cable_type

    if not label:
        if registry_spec is not None:
            label = registry_spec.label
        elif spec and entry.cable_tag:
            label = f"{spec} ({entry.cable_tag})"
        elif spec:
            label = spec
        elif entry.cable_tag:
            label = entry.cable_tag

    return spec, cable_type, label, registry_spec


def _get_cable_endpoints(
    entry: _CableEntry,
    placed: dict[str, Symbol],
) -> tuple[Point, Point, Point]:
    """Validate and return from/to port positions and from_port direction point."""
    from_sym = placed.get(entry.from_name)
    to_sym = placed.get(entry.to_name)

    if from_sym is None:
        raise ValueError(f"Cable references unknown block '{entry.from_name}'")
    if to_sym is None:
        raise ValueError(f"Cable references unknown block '{entry.to_name}'")

    from_port = from_sym.ports.get(entry.from_port)
    to_port = to_sym.ports.get(entry.to_port)

    if from_port is None:
        available = list(from_sym.ports.keys())
        raise ValueError(
            f"Port '{entry.from_port}' not found on block "
            f"'{entry.from_name}'. Available: {available}"
        )
    if to_port is None:
        available = list(to_sym.ports.keys())
        raise ValueError(
            f"Port '{entry.to_port}' not found on block "
            f"'{entry.to_name}'. Available: {available}"
        )

    # Return from_pos, to_pos, and encode direction as a Point for simplicity
    return (
        from_port.position,
        to_port.position,
        Point(from_port.direction.dx, from_port.direction.dy),
    )


def _route_cables(
    cable_specs: list[_CableEntry],
    placed: dict[str, Symbol],
    cable_registry: CableRegistry | None,
) -> list[Element]:
    """Resolve cable styles and route all declared cables."""
    elements: list[Element] = []

    for entry in cable_specs:
        from_pos, to_pos, from_dir = _get_cable_endpoints(entry, placed)
        _, cable_type, label, _ = _resolve_cable_from_registry(entry, cable_registry)

        style = entry.style or CABLE_TYPE_STYLES.get(
            cable_type, CABLE_TYPE_STYLES["signal"]
        )

        if entry.waypoints is not None:
            wp = [Point(wx, wy) for wx, wy in entry.waypoints]
            waypoints = [from_pos, *wp, to_pos]
        else:
            prefer = "vertical" if abs(from_dir.y) > abs(from_dir.x) else "horizontal"
            waypoints = manhattan_route(from_pos, to_pos, prefer=prefer)

        elements.extend(render_cable(waypoints, style, label=label))

    return elements


_TYPE_LABELS: dict[str, str] = {
    "power_ac": "AC Power",
    "power_dc": "DC Power",
    "signal": "Signal",
    "ethernet": "Ethernet",
    "control": "Control",
}


def _auto_legend_entries(
    cables: list[_CableEntry],
) -> list[tuple[str, CableStyle]]:
    """Build legend entries from the unique cable types used."""
    seen: dict[str, CableStyle] = {}
    for entry in cables:
        ctype = entry.cable_type
        if ctype not in seen:
            style = CABLE_TYPE_STYLES.get(ctype, CABLE_TYPE_STYLES["signal"])
            seen[ctype] = style
    return [(_TYPE_LABELS.get(ctype, ctype), style) for ctype, style in seen.items()]
