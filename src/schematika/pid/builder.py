"""Fluent builder for P&ID diagrams.

Provides :class:`PIDBuilder`, a named-graph builder where equipment is
referenced by name, placed via port-to-port alignment, and connected with
explicit pipe declarations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from schematika.catalog.registry import DeviceCatalog

from schematika.core.autonumbering import next_tag
from schematika.core.geometry import Element, Point, Vector
from schematika.core.state import GenerationState, create_initial_state
from schematika.core.symbol import Symbol, SymbolFactory
from schematika.core.transform import translate
from schematika.pid.connections import (
    PROCESS_PIPE,
    SIGNAL_LINE,
    PipeStyle,
    manhattan_route,
    render_pipe,
)
from schematika.pid.constants import (
    INSTRUMENT_BUBBLE_RADIUS,
    PID_LABEL_OFFSET,
    validate_isa_letters,
)
from schematika.pid.diagram import PIDDiagram
from schematika.pid.errors import PIDValidationError
from schematika.pid.layout import Placement, resolve_placements
from schematika.pid.symbols.instruments import instrument_bubble

_DEFAULT_INSTRUMENT_OFFSET: tuple[float, float] = (
    0.0,
    -(INSTRUMENT_BUBBLE_RADIUS * 2 + PID_LABEL_OFFSET),
)


@dataclass(frozen=True)
class EquipmentSpec:
    """Specification for a piece of process equipment.

    Attributes:
        factory: Symbol factory callable.
        tag_prefix: Prefix used for auto-tag generation (e.g. ``"P"`` → ``"P1"``).
        name: User-assigned name key.
        kwargs: Extra keyword arguments forwarded to the factory.
    """

    factory: SymbolFactory
    tag_prefix: str
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _InstrumentEntry:
    """Internal specification for an ISA 5.1 instrument bubble.

    Attributes:
        letters: ISA letter codes (e.g. ``"TT"``, ``"FIC"``).
        tag_prefix: Prefix for auto-tag generation; defaults to *letters*.
        on_equipment: Name of the equipment this instrument is attached to.
        on_port: Port ID on the equipment used as the placement anchor.
        location: ISA location string: ``"field"``, ``"panel"``, or ``"dcs"``.
        offset: (dx, dy) offset from the anchor port in mm.
        kwargs: Extra keyword arguments forwarded to ``instrument_bubble()``.
    """

    letters: str
    tag_prefix: str
    on_equipment: str
    on_port: str
    location: str
    offset: tuple[float, float]
    fixed_tag: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipeSpec:
    """A pipe connection between two pieces of equipment (or instruments).

    Attributes:
        from_equipment: Source name key.
        from_port: Port ID on the source symbol.
        to_equipment: Target name key.
        to_port: Port ID on the target symbol.
        line_spec: Optional pipe tag/label string placed on the line.
        style: Visual style; defaults to :data:`PROCESS_PIPE`.
    """

    from_equipment: str
    from_port: str
    to_equipment: str
    to_port: str
    line_spec: str = ""
    style: PipeStyle = field(default_factory=lambda: PROCESS_PIPE)


@dataclass(frozen=True)
class PIDBuildResult:
    """Result of building a P&ID diagram.

    Attributes:
        state: Updated :class:`GenerationState` (pass to the next builder).
        diagram: Assembled :class:`PIDDiagram`.
        equipment_map: Mapping of user name → generated tag
            (e.g. ``"pump"`` → ``"P1"``).
        instrument_map: Mapping of instrument name → generated tag
            (e.g. ``"tt101"`` → ``"TT1"``).
    """

    state: GenerationState
    diagram: PIDDiagram
    equipment_map: dict[str, str]
    instrument_map: dict[str, str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _EquipmentEntry:
    """Internal: all data associated with one piece of equipment."""

    spec: EquipmentSpec
    placement: Placement | None  # None for absolute / root placements
    abs_position: Point | None  # Set when placement is None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class PIDBuilder:
    """Fluent builder for P&ID diagrams.

    Uses a named-graph model: equipment is referenced by name, placed
    relative to other equipment via port-to-port alignment, and connected
    with explicit pipe declarations.

    Example::

        builder = PIDBuilder()
        (
            builder
            .add_equipment("tank", tank, "T", x=50, y=80)
            .add_equipment("pump", centrifugal_pump, "P",
                           relative_to="tank", from_port="outlet", to_port="inlet")
            .pipe("tank", "pump", line_spec="2-CW-101")
            .add_instrument("tt101", "TT", on_equipment="pump", on_port="outlet")
            .signal_line("tt101", "pump")
        )
        result = builder.build()
    """

    def __init__(self, state: GenerationState | None = None) -> None:
        self._state: GenerationState = state or create_initial_state()
        self._entries: dict[str, _EquipmentEntry] = {}
        self._instruments: dict[str, _InstrumentEntry] = {}
        self._pipes: list[PipeSpec] = []
        # Insertion-order tracking (Python 3.7+ dict preserves order, but
        # we keep a separate list for equipment and instrument ordering).
        self._equipment_order: list[str] = []
        self._instrument_order: list[str] = []

    # ------------------------------------------------------------------
    # Public builder methods
    # ------------------------------------------------------------------

    def add_equipment(
        self,
        name: str,
        /,
        factory: SymbolFactory,
        tag_prefix: str,
        *,
        relative_to: str | None = None,
        from_port: str = "outlet",
        to_port: str = "inlet",
        offset: tuple[float, float] = (0.0, 0.0),
        position: Point | None = None,
        x: float = 0.0,
        y: float = 0.0,
        **kwargs: Any,
    ) -> PIDBuilder:
        """Add process equipment to the diagram.

        The first piece of equipment added (and any equipment added with
        ``x``/``y`` but without ``relative_to``) is placed at absolute
        coordinates ``(x, y)``.

        Subsequent equipment can be placed relative to another piece by
        supplying ``relative_to``, ``from_port`` (the port *on the anchor*),
        and ``to_port`` (the port *on this new equipment*) so that
        ``to_port`` aligns to ``from_port + offset``.

        Args:
            name: Unique name key for this equipment.
            factory: Symbol factory callable (must accept ``label`` kwarg).
            tag_prefix: Prefix for auto-tag generation (e.g. ``"P"`` → ``"P1"``).
            relative_to: Name of the anchor equipment.  When omitted the
                equipment is placed at the absolute position ``(x, y)``.
            from_port: Port ID on the anchor to align from.
            to_port: Port ID on this equipment to align to the anchor port.
            offset: Additional (dx, dy) offset applied after port alignment.
            x: Absolute x-coordinate (used when ``relative_to`` is ``None``).
            y: Absolute y-coordinate (used when ``relative_to`` is ``None``).
            **kwargs: Extra keyword arguments forwarded to *factory*.

        Returns:
            ``self`` for method chaining.

        Raises:
            ValueError: If *name* is already registered, or *relative_to*
                references equipment that has not been registered yet.
        """
        if name in self._entries or name in self._instruments:
            raise PIDValidationError(f"Equipment '{name}' already registered")

        spec = EquipmentSpec(
            factory=factory, tag_prefix=tag_prefix, name=name, kwargs=kwargs
        )

        if relative_to is not None:
            if relative_to not in self._entries:
                raise PIDValidationError(
                    f"Cannot place '{name}' relative to '{relative_to}': "
                    f"'{relative_to}' has not been registered yet"
                )
            placement = Placement(
                anchor=relative_to,
                anchor_port=from_port,
                my_port=to_port,
                offset=Vector(*offset),
            )
            entry = _EquipmentEntry(spec=spec, placement=placement, abs_position=None)
        else:
            abs_pos = position if position is not None else Point(x, y)
            entry = _EquipmentEntry(spec=spec, placement=None, abs_position=abs_pos)

        self._entries[name] = entry
        self._equipment_order.append(name)
        return self

    def add_instrument(
        self,
        name: str,
        /,
        letters: str,
        *,
        on_equipment: str,
        on_port: str = "outlet",
        location: str = "field",
        offset: tuple[float, float] = _DEFAULT_INSTRUMENT_OFFSET,
        tag_prefix: str | None = None,
        **kwargs: Any,
    ) -> PIDBuilder:
        """Attach an ISA 5.1 instrument bubble to equipment.

        The instrument bubble is placed near the specified port of the
        equipment, offset by *offset* (default: 30 mm above the port).

        Args:
            name: Unique name key for this instrument.
            letters: ISA letter codes (e.g. ``"TT"``, ``"FIC"``).
            on_equipment: Name of the equipment to attach to.
            on_port: Port ID on the equipment used as placement anchor.
            location: ``"field"``, ``"panel"``, or ``"dcs"``.
            offset: ``(dx, dy)`` offset from the anchor port in mm.
            tag_prefix: Prefix for tag generation.  Defaults to *letters*.
            **kwargs: Extra keyword arguments forwarded to
                :func:`~schematika.pid.symbols.instruments.instrument_bubble`.

        Returns:
            ``self`` for method chaining.

        Raises:
            ValueError: If *name* is already registered, *on_equipment*
                has not been registered, or *letters* are not valid ISA 5.1
                codes.
        """
        if name in self._entries or name in self._instruments:
            raise PIDValidationError(f"Instrument '{name}' already registered")
        if on_equipment not in self._entries:
            raise PIDValidationError(
                f"Instrument '{name}' references unknown equipment '{on_equipment}'"
            )
        isa_errors = validate_isa_letters(letters)
        if isa_errors:
            raise PIDValidationError(
                f"Instrument '{name}' has invalid ISA 5.1 letter codes "
                f"'{letters}': {'; '.join(isa_errors)}"
            )

        self._instruments[name] = _InstrumentEntry(
            letters=letters,
            tag_prefix=tag_prefix or letters,
            on_equipment=on_equipment,
            on_port=on_port,
            location=location,
            offset=offset,
            kwargs=kwargs,
        )
        self._instrument_order.append(name)
        return self

    def add_instrument_from_catalog(
        self,
        name: str,
        /,
        catalog: DeviceCatalog,
        device_tag: str,
        *,
        on_equipment: str,
        on_port: str = "outlet",
        offset: tuple[float, float] = _DEFAULT_INSTRUMENT_OFFSET,
    ) -> PIDBuilder:
        """Add instrument from device catalog. Uses the catalog device's process spec.

        Args:
            name: Unique name key for this instrument.
            catalog: :class:`~schematika.catalog.registry.DeviceCatalog` to look up
                the device.
            device_tag: Tag of the device in the catalog (e.g. ``"TT-101"``).
            on_equipment: Name of the equipment to attach to.
            on_port: Port ID on the equipment used as placement anchor.
            offset: ``(dx, dy)`` offset from the anchor port in mm.

        Returns:
            ``self`` for method chaining.

        Raises:
            KeyError: If *device_tag* is not found in *catalog*.
            ValueError: If the device has no
                :class:`~schematika.catalog.device.ProcessSpec`.
        """
        device = catalog.get(device_tag)
        if device.process is None:
            raise PIDValidationError(f"Device '{device_tag}' has no ProcessSpec")
        spec = device.process.instrument

        if name in self._entries or name in self._instruments:
            raise PIDValidationError(f"Instrument '{name}' already registered")
        if on_equipment not in self._entries:
            raise PIDValidationError(
                f"Instrument '{name}' references unknown equipment '{on_equipment}'"
            )
        isa_errors = validate_isa_letters(spec.letters)
        if isa_errors:
            raise PIDValidationError(
                f"Catalog device '{device_tag}' has invalid ISA 5.1 letter "
                f"codes '{spec.letters}': {'; '.join(isa_errors)}"
            )

        self._instruments[name] = _InstrumentEntry(
            letters=spec.letters,
            tag_prefix=spec.letters,
            on_equipment=on_equipment,
            on_port=on_port,
            location=spec.location,
            offset=offset,
            fixed_tag=device_tag,
        )
        self._instrument_order.append(name)
        return self

    def pipe(
        self,
        from_name: str,
        to_name: str,
        *,
        from_port: str = "outlet",
        to_port: str = "inlet",
        line_spec: str = "",
        style: PipeStyle | None = None,
    ) -> PIDBuilder:
        """Declare a process pipe connection.

        Args:
            from_name: Source equipment/instrument name.
            to_name: Target equipment/instrument name.
            from_port: Port ID on the source.
            to_port: Port ID on the target.
            line_spec: Optional pipe tag/label placed on the line.
            style: Visual style (defaults to :data:`PROCESS_PIPE`).

        Returns:
            ``self`` for method chaining.
        """
        self._pipes.append(
            PipeSpec(
                from_equipment=from_name,
                from_port=from_port,
                to_equipment=to_name,
                to_port=to_port,
                line_spec=line_spec,
                style=style or PROCESS_PIPE,
            )
        )
        return self

    def signal_line(
        self,
        from_name: str,
        to_name: str,
        *,
        from_port: str = "signal_out",
        to_port: str = "process",
    ) -> PIDBuilder:
        """Declare an instrument signal line (dashed).

        Args:
            from_name: Source instrument/equipment name.
            to_name: Target equipment/instrument name.
            from_port: Port ID on the source (default ``"signal_out"``).
            to_port: Port ID on the target (default ``"process"``).

        Returns:
            ``self`` for method chaining.
        """
        self._pipes.append(
            PipeSpec(
                from_equipment=from_name,
                from_port=from_port,
                to_equipment=to_name,
                to_port=to_port,
                style=SIGNAL_LINE,
            )
        )
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(
        self,
        position: Point | None = None,
        *,
        x: float = 0.0,
        y: float = 0.0,
        state: GenerationState | None = None,
    ) -> PIDBuildResult:
        """Resolve placements, generate symbols, route pipes, and return the result.

        Build phases:

        1. Generate symbols from factories with auto-tags.
        2. Group equipment by connected placement subtrees, resolve each
           subtree via :func:`~schematika.pid.layout.resolve_placements`.
        3. Place instruments relative to their anchor equipment port.
        4. Route pipes/signal lines between placed symbols.
        5. Assemble and return :class:`PIDBuildResult`.

        Args:
            x: Global x-offset applied to all absolute-positioned roots.
            y: Global y-offset applied to all absolute-positioned roots.
            state: Optional state override; defaults to the builder's state.

        Returns:
            :class:`PIDBuildResult` with the assembled diagram and updated state.
        """
        current_state = state if state is not None else self._state
        if position is not None:
            x = position.x
            y = position.y

        # ----------------------------------------------------------------
        # Phase 1: Generate symbols with auto-tags
        # ----------------------------------------------------------------
        raw_symbols: dict[str, Symbol] = {}
        equipment_map: dict[str, str] = {}

        for name in self._equipment_order:
            spec = self._entries[name].spec
            current_state, tag = next_tag(current_state, spec.tag_prefix)
            symbol = spec.factory(label=tag, **spec.kwargs)
            raw_symbols[name] = symbol
            equipment_map[name] = tag

        # ----------------------------------------------------------------
        # Phase 2: Resolve placements
        #
        # Equipment without a placement (abs_position set) are independent
        # roots.  We resolve each connected subtree separately, applying the
        # global (x, y) offset to every absolute root.
        # ----------------------------------------------------------------
        placed: dict[str, Symbol] = {}

        # Identify all absolute-placement roots (no Placement anchor).
        abs_names = [
            name
            for name in self._equipment_order
            if self._entries[name].placement is None
        ]

        if not abs_names:
            # Degenerate: nothing to place (empty builder or all relative
            # with no root — this will raise in resolve_placements).
            pass

        # Build sub-dicts per connected component.
        # Each root spawns a subtree of all equipment that (transitively)
        # reference it via Placement.anchor.
        for root_name in abs_names:
            abs_pos = self._entries[root_name].abs_position
            assert abs_pos is not None  # guaranteed by construction
            root_pos = Point(abs_pos.x + x, abs_pos.y + y)

            # Collect all equipment in this subtree (root + descendants).
            subtree = _collect_subtree(root_name, self._equipment_order, self._entries)

            sub_symbols = {n: raw_symbols[n] for n in subtree}
            sub_placements = {
                n: self._entries[n].placement
                for n in subtree
                if self._entries[n].placement is not None
            }

            sub_placed = resolve_placements(
                sub_symbols,
                sub_placements,  # type: ignore[arg-type]
                root_name,
                root_pos,
            )
            placed.update(sub_placed)

        # ----------------------------------------------------------------
        # Phase 3: Place instruments
        # ----------------------------------------------------------------
        instrument_map: dict[str, str] = {}
        current_state, placed = self._place_instruments(
            current_state, placed, instrument_map
        )

        # ----------------------------------------------------------------
        # Phase 4: Route pipes and signal lines
        # ----------------------------------------------------------------
        pipe_elements = _route_pipes(self._pipes, placed)

        # ----------------------------------------------------------------
        # Phase 5: Assemble diagram
        # ----------------------------------------------------------------
        diagram = PIDDiagram()

        for name in self._equipment_order:
            if name in placed:
                sym = placed[name]
                diagram.equipment.append(sym)
                diagram.elements.extend(sym.elements)

        for name in self._instrument_order:
            if name in placed:
                sym = placed[name]
                diagram.equipment.append(sym)
                diagram.elements.extend(sym.elements)

        diagram.elements.extend(pipe_elements)

        return PIDBuildResult(
            state=current_state,
            diagram=diagram,
            equipment_map=equipment_map,
            instrument_map=instrument_map,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _place_instruments(
        self,
        state: GenerationState,
        placed: dict[str, Symbol],
        instrument_map: dict[str, str],
    ) -> tuple[GenerationState, dict[str, Symbol]]:
        """Generate and place all instrument bubbles.

        Updates *placed* and *instrument_map* in-place. Returns the updated state and placed dict.
        """
        placed = dict(placed)  # shallow copy — we add instruments to it

        for inst_name in self._instrument_order:
            inst_spec = self._instruments[inst_name]
            equip_name = inst_spec.on_equipment
            port_id = inst_spec.on_port

            if equip_name not in placed:
                raise PIDValidationError(
                    f"Instrument '{inst_name}' references equipment '{equip_name}' "
                    f"which was not placed"
                )

            equip_sym = placed[equip_name]
            if port_id not in equip_sym.ports:
                available = list(equip_sym.ports.keys())
                raise PIDValidationError(
                    f"Port '{port_id}' not found on equipment '{equip_name}'. "
                    f"Available: {available}"
                )

            port = equip_sym.ports[port_id]

            if inst_spec.fixed_tag is not None:
                tag = inst_spec.fixed_tag
            else:
                state, tag = next_tag(state, inst_spec.tag_prefix)

            tag_number = _numeric_suffix(tag)
            inst_sym = instrument_bubble(
                label=tag,
                letters=inst_spec.letters,
                location=inst_spec.location,
                tag_number=tag_number,
                **inst_spec.kwargs,
            )

            # Translate so that the instrument bubble origin sits at
            # port_position + offset.
            dx = port.position.x + inst_spec.offset[0]
            dy = port.position.y + inst_spec.offset[1]
            placed[inst_name] = translate(inst_sym, dx, dy)
            instrument_map[inst_name] = tag

        return state, placed


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _collect_subtree(
    root: str,
    order: list[str],
    entries: dict[str, _EquipmentEntry],
) -> list[str]:
    """Return all equipment names in the subtree rooted at *root*.

    Traverses the placement graph in insertion order, collecting *root* and
    all equipment whose Placement.anchor transitively points back to *root*.
    """
    members: set[str] = {root}
    # Repeat until stable (handles multi-level chains).
    changed = True
    while changed:
        changed = False
        for name in order:
            if name in members:
                continue
            entry = entries[name]
            if entry.placement is not None and entry.placement.anchor in members:
                members.add(name)
                changed = True
    # Return in original insertion order.
    return [n for n in order if n in members]


def _numeric_suffix(tag: str) -> str:
    """Return the trailing numeric part of *tag*, or empty string if none."""
    for i, ch in enumerate(tag):
        if ch.isdigit():
            return tag[i:]
    return ""


def _route_pipes(
    pipe_specs: list[PipeSpec],
    placed: dict[str, Symbol],
) -> list[Element]:
    """Resolve waypoints and render all declared pipes/signal lines.

    Args:
        pipe_specs: List of :class:`PipeSpec` declarations.
        placed: Mapping of name → placed symbol (equipment + instruments).

    Returns:
        Flat list of graphical elements (``Line``, optionally ``Polygon``
        and ``Text``).

    Raises:
        ValueError: If a pipe references an unknown name or a non-existent port.
    """
    elements: list[Element] = []
    seen_routes: set[tuple[float, float, float, float]] = set()

    for pipe_spec in pipe_specs:
        from_sym = placed.get(pipe_spec.from_equipment)
        to_sym = placed.get(pipe_spec.to_equipment)

        if from_sym is None:
            raise PIDValidationError(
                f"Pipe references unknown equipment/instrument "
                f"'{pipe_spec.from_equipment}'"
            )
        if to_sym is None:
            raise PIDValidationError(
                f"Pipe references unknown equipment/instrument "
                f"'{pipe_spec.to_equipment}'"
            )

        from_port = from_sym.ports.get(pipe_spec.from_port)
        to_port = to_sym.ports.get(pipe_spec.to_port)

        if from_port is None:
            available = list(from_sym.ports.keys())
            raise PIDValidationError(
                f"Port '{pipe_spec.from_port}' not found on "
                f"'{pipe_spec.from_equipment}'. Available: {available}"
            )
        if to_port is None:
            available = list(to_sym.ports.keys())
            raise PIDValidationError(
                f"Port '{pipe_spec.to_port}' not found on "
                f"'{pipe_spec.to_equipment}'. Available: {available}"
            )

        from_pos = from_port.position
        to_pos = to_port.position
        route_key = (
            round(from_pos.x, 1),
            round(from_pos.y, 1),
            round(to_pos.x, 1),
            round(to_pos.y, 1),
        )
        if route_key in seen_routes:
            continue
        seen_routes.add(route_key)

        # Infer routing preference from port directions:
        # If the from_port direction is primarily vertical, route
        # vertically first; otherwise route horizontally first.
        from_dir = from_port.direction
        prefer = "vertical" if abs(from_dir.dy) > abs(from_dir.dx) else "horizontal"
        waypoints = manhattan_route(from_pos, to_pos, prefer=prefer)
        elements.extend(
            render_pipe(waypoints, pipe_spec.style, label=pipe_spec.line_spec)
        )

    return elements
