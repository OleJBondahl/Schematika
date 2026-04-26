"""Unified Circuit Builder."""

from collections.abc import Callable
from datetime import UTC
from typing import TYPE_CHECKING, Any, Final

from schematika.core.exceptions import CircuitValidationError
from schematika.core.options import (
    ConnectionOptions,
    PlacementOptions,
    SymbolConfig,
    TerminalConfig,
    TerminalDisplayOptions,
)
from schematika.electrical.builder_models import (
    BridgeMode,
    BuildResult,
    CircuitSpec,
    ComponentRef,
    ComponentSpec,
    LayoutConfig,
    PlannedConnection,
    PortRef,
)
from schematika.electrical.builder_phases import _create_single_circuit_from_spec
from schematika.electrical.builder_utils import (
    _infer_default_pins,
    merge_build_results,
)
from schematika.electrical.layout.layout import create_horizontal_layout
from schematika.electrical.model.core import SymbolFactory
from schematika.electrical.system.system import Circuit
from schematika.electrical.utils.utils import set_tag_counter, set_terminal_counter

# Minimum number of poles/pins required to form a terminal bridge.
_MIN_BRIDGE_POLES: Final = 2

if TYPE_CHECKING:
    from pathlib import Path

    from schematika.core.geometry import Point
    from schematika.electrical.internal_device import InternalDevice
    from schematika.electrical.model.constants import LabelPosition, Position, Side
    from schematika.electrical.model.state import GenerationState
    from schematika.electrical.terminal import Terminal


class CircuitBuilder:
    """Fluent builder for IEC 60617 electrical circuits; freezes on :meth:`build`.

    Add components with ``add_terminal``, ``add_component``, etc., then call
    :meth:`build` to get an immutable :class:`BuildResult`.  Do not reuse a
    builder instance after :meth:`build` — create a fresh one instead.

    Examples:
        >>> from schematika.electrical import CircuitBuilder, create_initial_state
        >>> state = create_initial_state()
        >>> cb = CircuitBuilder(state=state)
        >>> result = cb.build()
        >>> result.used_terminals
        []
    """

    def __init__(self, state: "GenerationState | None" = None) -> None:
        """If `state` is None, it must be passed to `build(state=...)`."""
        self._initial_state = state
        self._spec = CircuitSpec()
        # Fixed tag generators added by add_reference()
        self._fixed_tag_generators: dict[str, Callable] = {}
        self._frozen = False
        self._result: BuildResult | None = None
        self._last_chain_idx: int | None = None

    def _check_not_frozen(self) -> None:
        if self._frozen:
            msg = "Cannot modify a frozen CircuitBuilder. Create a new builder instead."
            raise RuntimeError(msg)

    def set_layout(
        self,
        position: "Point | None" = None,
        /,
        *,
        x: float = 0,
        y: float = 0,
        spacing: float = 150,
        symbol_spacing: float = 50,
    ) -> "CircuitBuilder":
        """`position` overrides `x`/`y` when provided; all distances in mm."""
        self._check_not_frozen()
        start_x = position.x if position is not None else x
        start_y = position.y if position is not None else y
        self._spec.layout = LayoutConfig(
            start_x=start_x,
            start_y=start_y,
            spacing=spacing,
            symbol_spacing=symbol_spacing,
        )
        return self

    def add_terminal(
        self,
        tm_id: "str | Terminal",
        /,
        *,
        config: TerminalConfig | None = None,
        placement: PlacementOptions | None = None,
        display: TerminalDisplayOptions | None = None,
        connection: ConnectionOptions | None = None,
    ) -> "ComponentRef":
        """Register a terminal in the chain; freezes nothing.

        Args:
            tm_id: Terminal identity — either a ``str`` or a :class:`Terminal`.
                Used as the symbol-factory's ``tm_id`` kwarg and as the chain key.
            config: Pin layout + logical name. ``None`` means single-pole, no pins,
                no mapping. See :class:`~schematika.core.options.TerminalConfig`.
            placement: Where to place this terminal. ``None`` means below the
                previous chain head with default spacing.
                See :class:`~schematika.core.options.PlacementOptions`.
            display: Label-position knobs. ``None`` means use the symbol-factory
                defaults. See :class:`~schematika.core.options.TerminalDisplayOptions`.
            connection: Chain-wiring knobs. ``None`` means auto-connect from
                previous and to next.
                See :class:`~schematika.core.options.ConnectionOptions`.

        Returns:
            ``ComponentRef`` to this terminal — usable as ``relative_to`` for subsequent
            components and as a source/target in :meth:`connect`.

        Raises:
            RuntimeError: If the builder has been frozen by :meth:`build`.

        Examples:
            >>> from schematika.electrical import CircuitBuilder, create_initial_state
            >>> from schematika.core.options import TerminalConfig
            >>> b = CircuitBuilder(state=create_initial_state())
            >>> cfg = TerminalConfig(poles=2, pins=("L", "N"))
            >>> ref = b.add_terminal("X1", config=cfg)
            >>> ref._index
            0
        """
        self._check_not_frozen()
        cfg = config or TerminalConfig()
        plc = placement or PlacementOptions()
        dsp = display or TerminalDisplayOptions()
        con = connection or ConnectionOptions()

        if cfg.logical_name:
            self._spec.terminal_map[cfg.logical_name] = tm_id

        # Resolve relative_to to index/pin tuple
        resolved_relative_to: int | tuple[int, str] | None = None
        if plc.relative_to is not None:
            if isinstance(plc.relative_to, PortRef):
                resolved_relative_to = (
                    plc.relative_to.component._index,
                    str(plc.relative_to.port),
                )
            elif isinstance(plc.relative_to, ComponentRef):
                resolved_relative_to = plc.relative_to._index
        elif self._last_chain_idx is not None:
            resolved_relative_to = self._last_chain_idx

        (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_connect_to_next,
        ) = self._resolve_placement(
            plc.relative_to,
            plc.position,
            plc.spacing,
            plc.x_offset,
            connect_to_next=con.connect_to_next,
            resolved_relative_to=resolved_relative_to,
        )

        bridge = con.bridge if con.bridge is not None else BridgeMode.NONE

        spec = ComponentSpec(
            func=None,
            kind="terminal",
            poles=cfg.poles,
            pins=cfg.pins,
            pin_prefixes=cfg.pin_prefixes,
            x_offset=effective_x_offset,
            y_increment=plc.spacing,
            connect_to_next=effective_connect_to_next,
            connection_side=con.connection_side,
            bridge=bridge,
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            relative_to_idx=resolved_relative_to,
            position=plc.position,
            connect_from_previous=con.connect_from_previous,
            spacing_override=plc.spacing,
            kwargs={
                "tm_id": tm_id,
                "label_pos": dsp.label_pos,
                "pin_label_pos": dsp.pin_label_pos,
                "logical_name": cfg.logical_name,
            },
        )
        self._spec.components.append(spec)
        idx = len(self._spec.components) - 1
        new_ref = ComponentRef(self, idx, str(tm_id))

        # Determine whether this is a chain component (no explicit placement)
        is_chain_component = (
            placed_right_of is None
            and placed_above_of is None
            and placed_below_of is None
        )

        # Record chain connection from previous chain component
        if is_chain_component and self._last_chain_idx is not None:
            prev_spec = self._spec.components[self._last_chain_idx]
            if prev_spec.connect_to_next and con.connect_from_previous:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # Non-chain placements with connect_from_previous: pin_placement connection
        if (
            not is_chain_component
            and con.connect_from_previous
            and resolved_relative_to is not None
        ):
            if plc.position == "above":
                # above: new terminal bottom → ref pin top (same as place_above)
                self.connect(
                    new_ref.pole(0),
                    plc.relative_to,  # ty: ignore[invalid-argument-type]
                    side_a="bottom",
                    side_b="top",
                    wire_label=con.wire_label,
                )
            elif plc.position == "below":
                # below: ref pin bottom → new terminal top (same as place_below)
                self.connect(
                    plc.relative_to,  # ty: ignore[invalid-argument-type]
                    new_ref.pole(0),
                    side_a="bottom",
                    side_b="top",
                    wire_label=con.wire_label,
                )
            else:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=(
                            resolved_relative_to
                            if isinstance(resolved_relative_to, int)
                            else resolved_relative_to[0]
                        ),
                        target_idx=idx,
                        kind="pin_placement",
                    )
                )

        # Update last chain index for normally-placed components
        if is_chain_component:
            self._last_chain_idx = idx

        return new_ref

    def _resolve_placement(
        self,
        relative_to: "ComponentRef | PortRef | None",
        position: "Position",
        spacing: float | None,
        x_offset: float,
        *,
        connect_to_next: bool,
        resolved_relative_to: "int | tuple[int, str] | None",
    ) -> (
        "tuple[int | None, tuple[int, str] | None, tuple[int, str] | None, float, bool]"
    ):
        """Returns placement fields + x_offset + connect_to_next."""
        placed_right_of: int | None = None
        placed_above_of: tuple[int, str] | None = None
        placed_below_of: tuple[int, str] | None = None
        effective_connect_to_next = connect_to_next
        effective_x_offset = x_offset

        if relative_to is None:
            return (
                placed_right_of,
                placed_above_of,
                placed_below_of,
                effective_x_offset,
                effective_connect_to_next,
            )

        if position == "right" and isinstance(resolved_relative_to, int):
            placed_right_of = resolved_relative_to
            effective_connect_to_next = False
        elif position == "above" and isinstance(resolved_relative_to, tuple):
            placed_above_of = resolved_relative_to
            effective_connect_to_next = False
        elif position == "below" and isinstance(resolved_relative_to, tuple):
            placed_below_of = resolved_relative_to
            effective_connect_to_next = False
        elif position == "left" and isinstance(resolved_relative_to, int):
            placed_right_of = resolved_relative_to
            effective_connect_to_next = False
            effective_x_offset = -(spacing or 40.0)

        return (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_connect_to_next,
        )

    def add_symbol(
        self,
        symbol_func: SymbolFactory,
        /,
        *,
        config: SymbolConfig,
        placement: PlacementOptions | None = None,
        connection: ConnectionOptions | None = None,
    ) -> "ComponentRef":
        """Register a symbol-factory-built component in the chain.

        Args:
            symbol_func: Factory callable producing a :class:`Symbol`. Receives ``tag``,
                optional ``poles``, optional ``pins``, plus any ``factory_kwargs``.
            config: Required tag/pin/device/wire-label/factory-kwargs bundle. See
                :class:`SymbolConfig`.
            placement: Where to place this component. ``None`` means below the previous
                chain head with default spacing. See :class:`PlacementOptions`.
            connection: Chain-wiring knobs. ``None`` means auto-connect from previous
                and to next. See :class:`ConnectionOptions`.

        Returns:
            ``ComponentRef`` to this symbol — usable as ``relative_to`` for subsequent
            components and as a source/target in :meth:`connect`.

        Raises:
            RuntimeError: If the builder has been frozen by :meth:`build`.

        Examples:
            >>> from schematika.electrical import CircuitBuilder, create_initial_state
            >>> from schematika.electrical.symbols.contacts import no_contact
            >>> from schematika.core.options import SymbolConfig
            >>> b = CircuitBuilder(state=create_initial_state())
            >>> ref = b.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
            >>> ref._index
            0
        """
        self._check_not_frozen()
        plc = placement or PlacementOptions()
        con = connection or ConnectionOptions()

        tag_prefix = config.tag_prefix
        poles = config.poles
        pins = config.pins
        device = config.device
        wire_labels_above = config.wire_labels_above
        kwargs_for_factory = (
            dict(config.factory_kwargs) if config.factory_kwargs else {}
        )

        relative_to = plc.relative_to
        position = plc.position
        spacing = plc.spacing
        x_offset = plc.x_offset
        connect_from_previous = con.connect_from_previous
        connect_to_next = con.connect_to_next

        # Resolve relative_to to index/pin tuple
        resolved_relative_to: int | tuple[int, str] | None = None
        if relative_to is not None:
            if isinstance(relative_to, PortRef):
                resolved_relative_to = (
                    relative_to.component._index,
                    str(relative_to.port),
                )
            elif isinstance(relative_to, ComponentRef):
                resolved_relative_to = relative_to._index
        elif self._last_chain_idx is not None:
            resolved_relative_to = self._last_chain_idx

        # Map new position param to old placement fields for backward compat
        # during the transition (Phases 1 and 3 still read old fields)
        (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_connect_to_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            connect_to_next=connect_to_next,
            resolved_relative_to=resolved_relative_to,
        )

        if pins is None:
            pins = _infer_default_pins(symbol_func)
        # For multipole symbols with pins=None defaults (e.g. breaker(poles=N)),
        # generate IEC-standard sequential pins: ("1","2","3","4",...,"2*poles")
        if pins is None and poles > 1:
            pins = [str(i) for i in range(1, poles * 2 + 1)]

        spec = ComponentSpec(
            func=symbol_func,
            tag_prefix=tag_prefix,
            kind="symbol",
            poles=poles,
            pins=pins,
            x_offset=effective_x_offset,
            y_increment=spacing,
            connect_to_next=effective_connect_to_next,
            device=device,
            wire_labels_above=wire_labels_above,
            kwargs=kwargs_for_factory,
            # Old placement fields (populated from new params during transition)
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            # New fields
            relative_to_idx=resolved_relative_to,
            position=position,
            connect_from_previous=connect_from_previous,
            spacing_override=spacing,
        )
        self._spec.components.append(spec)
        idx = len(self._spec.components) - 1

        # Determine whether this is a chain component (no explicit placement)
        is_chain_component = (
            placed_right_of is None
            and placed_above_of is None
            and placed_below_of is None
        )

        # Record chain connection from previous chain component
        if is_chain_component and self._last_chain_idx is not None:
            prev_spec = self._spec.components[self._last_chain_idx]
            if prev_spec.connect_to_next and connect_from_previous:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with connect_from_previous, connect via position
        new_ref = ComponentRef(self, idx, tag_prefix)
        if (
            not is_chain_component
            and connect_from_previous
            and resolved_relative_to is not None
        ):
            if position == "above" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    new_ref.pole(0),
                    relative_to,  # ty: ignore[invalid-argument-type]
                    side_a="bottom",
                    side_b="top",
                )
            elif position == "below" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    relative_to,  # ty: ignore[invalid-argument-type]
                    new_ref.pole(0),
                    side_a="bottom",
                    side_b="top",
                )
            else:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=(
                            resolved_relative_to
                            if isinstance(resolved_relative_to, int)
                            else resolved_relative_to[0]
                        ),
                        target_idx=idx,
                        kind="pin_placement",
                    )
                )

        # Update last chain index for normally-placed components
        if is_chain_component:
            self._last_chain_idx = idx

        return new_ref

    def add_spdt(
        self,
        tag_prefix: str = "K",
        /,
        *,
        poles: int = 1,
        pins: list[str] | tuple[str, ...] | None = None,
        inverted: bool = False,
        relative_to: "ComponentRef | PortRef | None" = None,
        position: "Position" = "below",
        connect_from_previous: bool = False,
        spacing: float | None = None,
        x_offset: float = 0.0,
        y_increment: float | None = None,
        device: "InternalDevice | None" = None,
        wire_labels_above: list[str] | tuple[str, ...] | None = None,
    ) -> "ComponentRef":
        """Default IEC pins: 11/12/14 (COM/NC/NO); `inverted` puts COM on top."""
        from schematika.electrical.symbols.contacts import spdt_contact

        self._check_not_frozen()

        # Generate default IEC pins if not provided
        if pins is None:
            pins = tuple(
                f"{p}{s}" for p in range(1, poles + 1) for s in ("1", "2", "4")
            )

        func = spdt_contact

        # Build kwargs for the symbol factory (poles + inverted)
        sym_kwargs: dict = {}
        if poles > 1:
            sym_kwargs["poles"] = poles
        if inverted:
            sym_kwargs["inverted"] = inverted

        # Resolve relative_to to index/pin tuple
        resolved_relative_to: int | tuple[int, str] | None = None
        if relative_to is not None:
            if isinstance(relative_to, PortRef):
                resolved_relative_to = (
                    relative_to.component._index,
                    str(relative_to.port),
                )
            elif isinstance(relative_to, ComponentRef):
                resolved_relative_to = relative_to._index
        elif self._last_chain_idx is not None:
            resolved_relative_to = self._last_chain_idx

        # Use spacing if provided, fall back to y_increment for backward compat
        effective_spacing = spacing if spacing is not None else y_increment

        (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            _effective_connect_to_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            connect_to_next=False,  # add_spdt always has connect_to_next=False
            resolved_relative_to=resolved_relative_to,
        )

        spec = ComponentSpec(
            func=func,
            tag_prefix=tag_prefix,
            kind="symbol",
            poles=poles,
            pins=pins,
            x_offset=effective_x_offset,
            y_increment=effective_spacing,
            connect_to_next=False,
            device=device,
            wire_labels_above=wire_labels_above,
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            relative_to_idx=resolved_relative_to,
            position=position,
            connect_from_previous=connect_from_previous,
            spacing_override=spacing,
            kwargs=sym_kwargs,
        )
        self._spec.components.append(spec)
        idx = len(self._spec.components) - 1

        # Determine whether this is a chain component (no explicit placement)
        is_chain_component = (
            placed_right_of is None
            and placed_above_of is None
            and placed_below_of is None
        )

        # Record chain connection from previous chain component
        if is_chain_component and self._last_chain_idx is not None:
            prev_spec = self._spec.components[self._last_chain_idx]
            if prev_spec.connect_to_next and connect_from_previous:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with connect_from_previous, connect via position
        new_ref = ComponentRef(self, idx, tag_prefix)
        if (
            not is_chain_component
            and connect_from_previous
            and resolved_relative_to is not None
        ):
            if position == "above" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    new_ref.pole(0),
                    relative_to,  # ty: ignore[invalid-argument-type]
                    side_a="bottom",
                    side_b="top",
                )
            elif position == "below" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    relative_to,  # ty: ignore[invalid-argument-type]
                    new_ref.pole(0),
                    side_a="bottom",
                    side_b="top",
                )
            else:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=(
                            resolved_relative_to
                            if isinstance(resolved_relative_to, int)
                            else resolved_relative_to[0]
                        ),
                        target_idx=idx,
                        kind="pin_placement",
                    )
                )

        # Update last chain index (add_spdt always has connect_to_next=False,
        # so _last_chain_idx advances here but won't emit a connection forward)
        self._last_chain_idx = idx

        return new_ref

    def add_reference(
        self,
        ref_id: str,
        /,
        *,
        relative_to: "ComponentRef | PortRef | None" = None,
        position: "Position" = "below",
        connect_from_previous: bool = True,
        spacing: float | None = None,
        x_offset: float = 0.0,
        y_increment: float | None = None,
        connect_to_next: bool = True,
        wire_label: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> "ComponentRef":
        """Reference symbols use `ref_id` as the tag (not auto-numbered)."""
        self._check_not_frozen()
        from schematika.electrical.symbols.references import ref as ref_symbol

        # Register a fixed tag generator for this reference ID
        def fixed_gen(state: "GenerationState") -> "tuple[GenerationState, str]":
            return state, ref_id

        self._fixed_tag_generators[ref_id] = fixed_gen

        # Resolve relative_to to index/pin tuple
        resolved_relative_to: int | tuple[int, str] | None = None
        if relative_to is not None:
            if isinstance(relative_to, PortRef):
                resolved_relative_to = (
                    relative_to.component._index,
                    str(relative_to.port),
                )
            elif isinstance(relative_to, ComponentRef):
                resolved_relative_to = relative_to._index
        elif self._last_chain_idx is not None:
            resolved_relative_to = self._last_chain_idx

        # Use spacing if provided, fall back to y_increment for backward compat
        effective_spacing = spacing if spacing is not None else y_increment

        (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_connect_to_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            connect_to_next=connect_to_next,
            resolved_relative_to=resolved_relative_to,
        )

        spec = ComponentSpec(
            func=ref_symbol,
            tag_prefix=ref_id,
            kind="reference",
            x_offset=effective_x_offset,
            y_increment=effective_spacing,
            connect_to_next=effective_connect_to_next,
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            relative_to_idx=resolved_relative_to,
            position=position,
            connect_from_previous=connect_from_previous,
            spacing_override=spacing,
            kwargs=kwargs,
        )
        self._spec.components.append(spec)
        idx = len(self._spec.components) - 1
        new_ref = ComponentRef(self, idx, ref_id)

        # Determine whether this is a chain component (no explicit placement)
        is_chain_component = (
            placed_right_of is None
            and placed_above_of is None
            and placed_below_of is None
        )

        # Record chain connection from previous chain component
        if is_chain_component and self._last_chain_idx is not None:
            prev_spec = self._spec.components[self._last_chain_idx]
            if prev_spec.connect_to_next and connect_from_previous:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with connect_from_previous, connect via position
        if (
            not is_chain_component
            and connect_from_previous
            and resolved_relative_to is not None
        ):
            self._connect_placed_reference(
                new_ref,
                idx,
                relative_to,
                position,
                resolved_relative_to,
                wire_label,
            )

        # Update last chain index for normally-placed components
        if is_chain_component:
            self._last_chain_idx = idx

        return new_ref

    def _connect_placed_reference(
        self,
        new_ref: "ComponentRef",
        idx: int,
        relative_to: "ComponentRef | PortRef | None",
        position: "Position",
        resolved_relative_to: "int | tuple[int, str]",
        wire_label: str | None,
    ) -> None:
        """Connect a non-chain placed reference to its anchor component."""
        if position == "above" and isinstance(resolved_relative_to, tuple):
            self.connect(
                new_ref.pole(0),
                relative_to,  # ty: ignore[invalid-argument-type]
                side_a="bottom",
                side_b="top",
                wire_label=wire_label,
            )
        elif position == "below" and isinstance(resolved_relative_to, tuple):
            self.connect(
                relative_to,  # ty: ignore[invalid-argument-type]
                new_ref.pole(0),
                side_a="bottom",
                side_b="top",
                wire_label=wire_label,
            )
        else:
            self._spec.planned_connections.append(
                PlannedConnection(
                    source_idx=(
                        resolved_relative_to
                        if isinstance(resolved_relative_to, int)
                        else resolved_relative_to[0]
                    ),
                    target_idx=idx,
                    kind="pin_placement",
                )
            )

    def connect_matching(
        self,
        ref_a: "ComponentRef",
        ref_b: "ComponentRef",
        pins: list[str] | None = None,
        side_a: "LabelPosition" = "right",
        side_b: "LabelPosition" = "left",
    ) -> "CircuitBuilder":
        """Draws horizontal wires between matching pin names on both components."""
        self._check_not_frozen()
        self._spec.matching_connections.append(
            (ref_a._index, ref_b._index, pins, side_a, side_b)
        )
        return self

    def connect(
        self,
        a: PortRef,
        b: PortRef,
        side_a: "Side | None" = None,
        side_b: "Side | None" = None,
        wire_label: str | None = None,
    ) -> "CircuitBuilder":
        """Pin-based connection API; coexists with index-based `add_connection()`."""
        self._check_not_frozen()
        # Resolve pin names to pole indices
        idx_a = a.component._index
        idx_b = b.component._index
        pole_a = self._resolve_port_ref_to_pole(a)
        pole_b = self._resolve_port_ref_to_pole(b)

        # Default sides
        if side_a is None:
            side_a = "bottom"
        if side_b is None:
            side_b = "top"

        return self.add_connection(
            idx_a, pole_a, idx_b, pole_b, side_a, side_b, wire_label=wire_label
        )

    def _resolve_port_ref_to_pole(self, port_ref: PortRef) -> int:
        """Resolve a PortRef to a pole index."""
        if isinstance(port_ref.port, int):
            return port_ref.port

        # It's a pin name — find the pole index
        idx = port_ref.component._index
        spec = self._spec.components[idx]

        if spec.pins:
            pins_list = list(spec.pins)
            # Check for interleaved In/Out pairs (poles * 2 pins)
            if len(pins_list) == spec.poles * 2:
                # Find the pin in the interleaved list, convert to pole
                for i, pin in enumerate(pins_list):
                    if pin == port_ref.port:
                        return i // 2
                # Also check direct index
                try:
                    return pins_list.index(port_ref.port)
                except ValueError:
                    pass
            else:
                # Direct indexing
                try:
                    return pins_list.index(port_ref.port)
                except ValueError:
                    pass

        from schematika.electrical.exceptions import PortNotFoundError

        available = list(spec.pins) if spec.pins else []
        tag = spec.tag_prefix or spec.kwargs.get("tm_id", "unknown")
        raise PortNotFoundError(str(tag), str(port_ref.port), available)

    def add_connection(
        self,
        comp_idx_a: int,
        /,
        pole_idx_a: int,
        comp_idx_b: int,
        pole_idx_b: int,
        side_a: "Side" = "bottom",
        side_b: "Side" = "top",
        wire_label: str | None = None,
    ) -> "CircuitBuilder":
        """Low-level index-based connection; prefer `connect()` (pin-based)."""
        self._check_not_frozen()
        self._spec.manual_connections.append(
            (comp_idx_a, pole_idx_a, comp_idx_b, pole_idx_b, side_a, side_b)
        )
        if wire_label is not None:
            conn_idx = len(self._spec.manual_connections) - 1
            self._spec.connection_wire_labels[conn_idx] = wire_label
        return self

    def _validate_connections(self) -> None:
        """Raises ComponentNotFoundError or PortNotFoundError on invalid references."""
        from schematika.electrical.exceptions import ComponentNotFoundError

        max_idx = len(self._spec.components) - 1

        for idx_a, _p_a, idx_b, _p_b, _side_a, _side_b in self._spec.manual_connections:
            if idx_a > max_idx:
                raise ComponentNotFoundError(idx_a, max_idx)
            if idx_b > max_idx:
                raise ComponentNotFoundError(idx_b, max_idx)

    def _build_effective_tag_generators(
        self,
        reuse_tags: dict[str, "BuildResult"] | None,
        tag_generators: dict[str, Callable] | None,
        fixed_tags: dict[str, str] | None = None,
    ) -> dict[str, Callable] | None:
        """Priority: tag_generators > reuse_tags > fixed_tags > internal fixed."""
        effective: dict[str, Callable] = {**self._fixed_tag_generators}
        if fixed_tags:
            for prefix, tag_value in fixed_tags.items():
                effective[prefix] = lambda s, _t=tag_value: (s, _t)
        if reuse_tags:
            for prefix, source_result in reuse_tags.items():
                effective[prefix] = source_result.reuse_tags(prefix)
        if tag_generators:
            effective.update(tag_generators)
        return effective if effective else None

    def _build_terminal_reuse_generators(
        self,
        reuse_terminals: "dict[str, BuildResult | CircuitBuilder | Callable] | None",
    ) -> dict[str, Callable]:
        """Maps terminal-key strings to pin generator callables."""
        result: dict[str, Callable] = {}
        if not reuse_terminals:
            return result
        for key, source in reuse_terminals.items():
            str_key = str(key)
            if isinstance(source, (BuildResult, CircuitBuilder)):
                result[str_key] = source.reuse_terminals(str_key)
            elif callable(source):
                result[str_key] = source
        return result

    def _derive_bridge_groups(
        self, terminal_pin_map: dict[str, list[str]]
    ) -> dict[str, list[tuple[int, int]]]:
        """Auto-derive bridge groups from terminals with bridge enabled."""
        bridge_groups: dict[str, list[tuple[int, int]]] = {}
        for comp in self._spec.components:
            if comp.kind != "terminal" or comp.bridge is BridgeMode.NONE:
                continue
            if comp.poles < _MIN_BRIDGE_POLES:
                continue

            tm_id = comp.kwargs.get("tm_id")
            tid = str(tm_id)

            # For BridgeMode.AUTO, check the Terminal object's bridge attribute
            if comp.bridge is BridgeMode.AUTO:
                term_bridge = getattr(tm_id, "bridge", None)
                if term_bridge != BridgeMode.ALL:
                    continue

            pins = terminal_pin_map.get(tid, [])
            if len(pins) < _MIN_BRIDGE_POLES:
                continue

            # Group pins by poles per instance
            poles = comp.poles
            for i in range(0, len(pins), poles):
                chunk = pins[i : i + poles]
                if len(chunk) >= _MIN_BRIDGE_POLES:
                    int_pins = sorted(int(p.split(":")[-1]) for p in chunk)
                    bridge_groups.setdefault(tid, []).append(
                        (int_pins[0], int_pins[-1])
                    )

        return bridge_groups

    def build(
        self,
        count: int = 1,
        start_indices: dict[str, int] | None = None,
        terminal_start_indices: dict[str, int] | None = None,
        tag_generators: dict[str, Callable] | None = None,
        fixed_tags: dict[str, str] | None = None,
        terminal_maps: dict[str, Any] | None = None,
        reuse_tags: dict[str, "BuildResult"] | None = None,
        reuse_terminals: (
            dict[str, "BuildResult | CircuitBuilder | Callable"] | None
        ) = None,
        wire_labels: list[str] | None = None,
        state: "GenerationState | None" = None,
        connection_log_path: "str | Path | None" = None,
    ) -> BuildResult:
        """With `count > 1`, supply `count * labels_per_instance` wire_labels."""
        self._check_not_frozen()
        self._validate_connections()
        effective_state = state if state is not None else self._initial_state
        if effective_state is None:
            msg = (
                "No state provided. Pass state to CircuitBuilder() or build(state=...)."
            )
            raise CircuitValidationError(msg)

        # Apply override counters
        if start_indices:
            for prefix, val in start_indices.items():
                effective_state = set_tag_counter(effective_state, prefix, val)
        if terminal_start_indices:
            for t_id, val in terminal_start_indices.items():
                effective_state = set_terminal_counter(effective_state, t_id, val)

        # Build effective tag_generators and terminal reuse generators
        final_tag_generators = self._build_effective_tag_generators(
            reuse_tags, tag_generators, fixed_tags
        )
        terminal_reuse_generators = self._build_terminal_reuse_generators(
            reuse_terminals
        )

        captured_tags: dict[str, list[str]] = {}
        captured_terminal_pins: dict[str, list[str]] = {}
        captured_wire_connections: list[tuple[str, str, str, str]] = []
        captured_device_registry: dict[str, InternalDevice] = {}

        def _single_instance_gen(
            s: "GenerationState",
            x: float,
            y: float,
            gens: dict[str, Callable],
            tm: dict[str, Any],
        ) -> "tuple[GenerationState, list[Any]]":
            res = _create_single_circuit_from_spec(
                s,
                x,
                y,
                self._spec,
                gens,
                tm,
                terminal_reuse_generators=terminal_reuse_generators or None,
                pin_accumulator=captured_terminal_pins,
            )
            # Update captured tags and device registry
            for prefix, tag_val in res[2].items():
                if prefix not in captured_tags:
                    captured_tags[prefix] = []
                captured_tags[prefix].append(tag_val)
            captured_wire_connections.extend(res[3])
            # Populate device_registry from spec components
            for comp_spec in self._spec.components:
                if (
                    comp_spec.device
                    and comp_spec.tag_prefix
                    and comp_spec.tag_prefix in res[2]
                ):
                    captured_device_registry[res[2][comp_spec.tag_prefix]] = (
                        comp_spec.device
                    )
            return res[0], res[1]

        # Use generic layout
        final_state, elements = create_horizontal_layout(
            state=effective_state,
            start_x=self._spec.layout.start_x,
            start_y=self._spec.layout.start_y,
            count=count,
            spacing=self._spec.layout.spacing,
            generator_func_single=lambda s, x, y, gens, tm, _instance: (
                _single_instance_gen(s, x, y, gens, tm)
            ),
            default_tag_generators={},
            tag_generators=final_tag_generators,
            terminal_maps=terminal_maps,
        )

        c = Circuit(elements=elements)

        # Apply wire labels — per-connection labels (inline in Phase 4) take
        # priority; the flat list is only used when no per-connection labels exist.
        has_per_connection = bool(self._spec.connection_wire_labels) or any(
            comp.wire_labels_above for comp in self._spec.components
        )
        if not has_per_connection:
            from schematika.electrical.layout.wire_labels import apply_wire_labels

            c = apply_wire_labels(c, wire_labels)

        # Extract used terminals
        used_terminals = []
        for comp in self._spec.components:
            if comp.kind == "terminal":
                tid = comp.kwargs.get("tm_id")
                lname = comp.kwargs.get("logical_name")
                if lname and lname in self._spec.terminal_map:
                    tid = self._spec.terminal_map[lname]
                if tid not in used_terminals:
                    used_terminals.append(tid)

        # Auto-derive bridge groups from terminal specs
        auto_bridges = self._derive_bridge_groups(captured_terminal_pins)

        # Build connection log from resolved wire connections
        connection_log_entries = [
            f"{src_tag}:{src_pin} -> {tgt_tag}:{tgt_pin}"
            for src_tag, src_pin, tgt_tag, tgt_pin in captured_wire_connections
        ]

        # Write log file if path provided
        if connection_log_path is not None:
            from datetime import datetime
            from pathlib import Path

            log_path = Path(connection_log_path)
            with log_path.open("w") as f:
                f.write(f"# Connection Log — {datetime.now(tz=UTC).isoformat()}\n")
                for entry in connection_log_entries:
                    f.write(f"{entry}\n")

        result = BuildResult(
            state=final_state,
            circuit=c,
            used_terminals=used_terminals,
            component_map=captured_tags,
            terminal_pin_map=captured_terminal_pins,
            device_registry=captured_device_registry,
            wire_connections=captured_wire_connections,
            bridge_groups=auto_bridges,
            connection_log=connection_log_entries,
        )
        self._result = result
        self._frozen = True
        return result

    # ------------------------------------------------------------------
    # Properties — accessible only after build()
    # ------------------------------------------------------------------

    def _check_built(self) -> BuildResult:
        if not self._frozen or self._result is None:
            msg = "CircuitBuilder has not been built yet. Call build() first."
            raise RuntimeError(msg)
        return self._result

    @property
    def result(self) -> BuildResult:
        """Return the full BuildResult; raises if `build()` has not been called."""
        return self._check_built()

    @property
    def state(self) -> "GenerationState":
        """Return the autonumbering state from the built result."""
        return self._check_built().state

    @property
    def circuit(self) -> Circuit:
        """Return the rendered ``Circuit`` from the built result."""
        return self._check_built().circuit

    @property
    def used_terminals(self) -> list[Any]:
        """Return the list of terminal symbols used in the built circuit."""
        return self._check_built().used_terminals

    @property
    def component_map(self) -> dict[str, list[str]]:
        """Return a mapping from component tag to its assigned pin labels."""
        return self._check_built().component_map

    @property
    def terminal_pin_map(self) -> dict[str, list[str]]:
        """Return a mapping from terminal tag to its allocated pin identifiers."""
        return self._check_built().terminal_pin_map

    @property
    def device_registry(self) -> "dict[str, InternalDevice]":
        """Return the internal device registry keyed by component tag."""
        return self._check_built().device_registry

    @property
    def wire_connections(self) -> list[tuple[str, str, str, str]]:
        """Return the list of wire connection tuples from the built result."""
        return self._check_built().wire_connections

    @property
    def bridge_groups(self) -> dict[str, list[tuple[int, int]]]:
        """Return bridging groups (terminal bridging spans) from the built result."""
        return self._check_built().bridge_groups

    # ------------------------------------------------------------------
    # Reuse helpers — forwarded to stored BuildResult
    # ------------------------------------------------------------------

    def reuse_tags(self, prefix: str) -> Callable:
        """Return a tag-reuse callable for *prefix* from the built result."""
        return self._check_built().reuse_tags(prefix)

    def reuse_terminals(self, key: str) -> Callable:
        """Return a terminal-reuse callable for *key* from the built result."""
        return self._check_built().reuse_terminals(key)

    # ------------------------------------------------------------------
    # Merge — combine multiple frozen builders into one
    # ------------------------------------------------------------------

    @staticmethod
    def merge(*builders: "CircuitBuilder") -> "CircuitBuilder":
        """All inputs must be frozen; state is taken from the last builder."""
        if not builders:
            msg = "merge() requires at least one CircuitBuilder"
            raise CircuitValidationError(msg)
        for b in builders:
            if not b._frozen:
                msg = "All builders must be frozen (built) before merging"
                raise RuntimeError(msg)

        results = [r for b in builders if (r := b._result) is not None]
        merged_result = merge_build_results(results)

        # Create a new frozen builder with the merged result
        new_builder = CircuitBuilder.__new__(CircuitBuilder)
        new_builder._frozen = True
        new_builder._result = merged_result
        new_builder._initial_state = merged_result.state
        new_builder._spec = CircuitSpec()
        new_builder._fixed_tag_generators = {}
        return new_builder
