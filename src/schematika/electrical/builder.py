"""
Unified Circuit Builder.

This module provides a powerful, high-level API for constructing
electrical circuits. It abstracts away the complexity of coordinate
management, manual connection registration, and multi-pole wiring.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from schematika.electrical.builder_models import (
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

if TYPE_CHECKING:
    from pathlib import Path

    from schematika.electrical.internal_device import InternalDevice
    from schematika.electrical.model.state import GenerationState
    from schematika.electrical.terminal import Terminal


class CircuitBuilder:
    """Fluent builder for constructing custom linear circuits.

    CircuitBuilder is one of the intentional mutable builder classes in the
    library. It accumulates component specifications, connections, and layout
    settings via method chaining, then produces a ``BuildResult`` when
    ``.build()`` is called.

    Typical usage::

        builder = CircuitBuilder(state)
        tm_top = builder.add_terminal("X1", poles=3)
        cb = builder.add_symbol(circuit_breaker_symbol, "Q", poles=3,
                                pins=("1","2","3","4","5","6"))
        builder.build(count=2, wire_labels=["BK", "BK", "BK"])

    Warning:
        Do not share builder instances across multiple build contexts.
        Each builder should be used for a single ``.build()`` call.
    """

    def __init__(self, state: "GenerationState | None" = None) -> None:
        """Initialize a CircuitBuilder with optional autonumbering state.

        Args:
            state: The autonumbering state dict (from ``create_autonumberer()``
                or returned by a previous ``BuildResult.state``). If None,
                state must be provided at build time via ``build(state=...)``.
        """
        self._initial_state = state
        self._spec = CircuitSpec()
        # Fixed tag generators added by add_reference()
        self._fixed_tag_generators: dict[str, Callable] = {}
        self._frozen = False
        self._result: BuildResult | None = None
        self._last_chain_idx: int | None = None

    def _check_not_frozen(self) -> None:
        if self._frozen:
            raise RuntimeError(
                "Cannot modify a frozen CircuitBuilder. Create a new builder instead."
            )

    def set_layout(
        self,
        x: float = 0,
        y: float = 0,
        spacing: float = 150,
        symbol_spacing: float = 50,
    ) -> "CircuitBuilder":
        """Configure the layout geometry for the circuit.

        Args:
            x: Starting X coordinate in mm.
            y: Starting Y coordinate in mm.
            spacing: Horizontal distance between circuit instances in mm.
            symbol_spacing: Vertical distance between components in mm.

        Returns:
            self for method chaining.
        """
        self._check_not_frozen()
        self._spec.layout = LayoutConfig(
            start_x=x, start_y=y, spacing=spacing, symbol_spacing=symbol_spacing
        )
        return self

    def add_terminal(  # noqa: C901
        self,
        tm_id: "str | Terminal",
        poles: int = 1,
        pins: list[str] | tuple[str, ...] | None = None,
        relative_to: "ComponentRef | PortRef | None" = None,
        position: str = "below",
        autoconnect: bool = True,
        spacing: float | None = None,
        pin_prefixes: tuple[str, ...] | None = None,
        label_pos: str | None = None,
        pin_label_pos: str | None = None,
        logical_name: str | None = None,
        x_offset: float = 0.0,
        auto_connect_next: bool = True,
        connection_side: str | None = None,
        bridge: bool | str = False,
        wire_label: str | None = None,
        **kwargs,
    ) -> "ComponentRef":
        """Add a terminal block to the circuit chain.

        Args:
            tm_id: Terminal identifier (str or ``Terminal`` instance).
            poles: Number of poles (default 1).
            pins: Explicit pin labels. If None, auto-numbered.
            relative_to: ComponentRef or PortRef to place this terminal relative
                to. If None, defaults to the last chain component.
            position: Placement direction relative to ``relative_to``.
                One of "below", "above", "left", "right" (default "below").
            autoconnect: Whether to record an auto-connection from the reference
                component to this one (default True).
            spacing: Spacing override in mm. If None, uses ``symbol_spacing``.
            pin_prefixes: Override the terminal's default pin_prefixes for
                auto-allocation. E.g. ``("L1", "N")`` to select specific
                prefixes from a terminal that has ``("L1","L2","L3","N")``.
            label_pos: Position of tag label ('left' or 'right').
            pin_label_pos: Position of pin number label ('left' or 'right').
                Defaults to label_pos if None.
            logical_name: Register this terminal under a logical key in
                the terminal map (e.g. "MAIN" or "OUTPUT").
            x_offset: Horizontal offset from the default X position in mm.
            auto_connect_next: Auto-connect to next component (default True).
            connection_side: Override the auto-determined side ('top' or
                'bottom') for the terminal CSV from/to column.
            bridge: Bridge control. ``False`` (default) = no bridge.
                ``True`` = always bridge all poles. ``"auto"`` = derive
                from the Terminal object's ``bridge`` attribute.

        Returns:
            ComponentRef for the added terminal.
        """
        self._check_not_frozen()
        if logical_name:
            self._spec.terminal_map[logical_name] = tm_id

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

        (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_auto_connect_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            auto_connect_next,
            resolved_relative_to,
        )

        spec = ComponentSpec(
            func=None,
            kind="terminal",
            poles=poles,
            pins=pins,
            pin_prefixes=pin_prefixes,
            x_offset=effective_x_offset,
            y_increment=spacing,
            auto_connect_next=effective_auto_connect_next,
            connection_side=connection_side,
            bridge=bridge,
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            relative_to_idx=resolved_relative_to,
            position=position,
            autoconnect=autoconnect,
            spacing_override=spacing,
            kwargs={
                "tm_id": tm_id,
                "label_pos": label_pos,
                "pin_label_pos": pin_label_pos,
                "logical_name": logical_name,
                **kwargs,
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
            if prev_spec.auto_connect_next and autoconnect:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with autoconnect, record a pin_placement connection
        if not is_chain_component and autoconnect and resolved_relative_to is not None:
            if position == "above":
                # above: new terminal bottom → ref pin top (same as place_above)
                self.connect(
                    new_ref.pole(0),
                    relative_to,  # type: ignore[arg-type]
                    side_a="bottom",
                    side_b="top",
                    wire_label=wire_label,
                )
            elif position == "below":
                # below: ref pin bottom → new terminal top (same as place_below)
                self.connect(
                    relative_to,  # type: ignore[arg-type]
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

        # Update last chain index for normally-placed components
        if is_chain_component:
            self._last_chain_idx = idx

        return new_ref

    def _resolve_placement(
        self,
        relative_to: "ComponentRef | PortRef | None",
        position: str,
        spacing: float | None,
        x_offset: float,
        auto_connect_next: bool,
        resolved_relative_to: "int | tuple[int, str] | None",
    ) -> (
        "tuple[int | None, tuple[int, str] | None, tuple[int, str] | None, float, bool]"
    ):
        """Resolve new-style placement params to old-style placement fields.

        Returns: (placed_right_of, placed_above_of, placed_below_of,
                  effective_x_offset, effective_auto_connect_next)
        """
        placed_right_of: int | None = None
        placed_above_of: tuple[int, str] | None = None
        placed_below_of: tuple[int, str] | None = None
        effective_auto_connect_next = auto_connect_next
        effective_x_offset = x_offset

        if relative_to is None:
            return (
                placed_right_of,
                placed_above_of,
                placed_below_of,
                effective_x_offset,
                effective_auto_connect_next,
            )

        if position == "right" and isinstance(resolved_relative_to, int):
            placed_right_of = resolved_relative_to
            effective_auto_connect_next = False
        elif position == "above" and isinstance(resolved_relative_to, tuple):
            placed_above_of = resolved_relative_to
            effective_auto_connect_next = False
        elif position == "below" and isinstance(resolved_relative_to, tuple):
            placed_below_of = resolved_relative_to
            effective_auto_connect_next = False
        elif position == "left" and isinstance(resolved_relative_to, int):
            placed_right_of = resolved_relative_to
            effective_auto_connect_next = False
            effective_x_offset = -(spacing or 40.0)

        return (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_auto_connect_next,
        )

    def add_symbol(  # noqa: C901
        self,
        symbol_func: SymbolFactory,
        tag_prefix: str,
        poles: int = 1,
        pins: list[str] | tuple[str, ...] | None = None,
        relative_to: "ComponentRef | PortRef | None" = None,
        position: str = "below",
        autoconnect: bool = True,
        spacing: float | None = None,
        x_offset: float = 0.0,
        y_increment: float | None = None,
        auto_connect_next: bool = True,
        device: "InternalDevice | None" = None,
        wire_labels_above: list[str] | tuple[str, ...] | None = None,
        **kwargs,
    ) -> "ComponentRef":
        """Add a generic component to the circuit chain.

        Args:
            symbol_func: Symbol factory function (e.g. ``circuit_breaker_symbol``).
            tag_prefix: Tag prefix for autonumbering (e.g. "F", "Q", "K").
            poles: Number of poles (default 1).
            pins: Explicit pin labels. If None, auto-numbered.
            relative_to: ComponentRef or PortRef to place this component relative
                to. If None, defaults to the last chain component.
            position: Placement direction relative to ``relative_to``.
                One of "below", "above", "left", "right" (default "below").
            autoconnect: Whether to record an auto-connection from the reference
                component to this one (default True).
            spacing: Spacing override in mm. If None, uses ``y_increment`` or
                ``symbol_spacing``.
            x_offset: Horizontal offset from the default X position in mm.
            auto_connect_next: Auto-connect to next component (default True).
            device: Optional InternalDevice for BOM tracking.
            wire_labels_above: Wire labels for the wires above this component
                (connecting it to the previous component). One label per pole.
            **kwargs: Passed to the symbol factory function.

        Returns:
            ComponentRef for the added component.
        """
        self._check_not_frozen()

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

        # Map new position param to old placement fields for backward compat
        # during the transition (Phases 1 and 3 still read old fields)
        (
            placed_right_of,
            placed_above_of,
            placed_below_of,
            effective_x_offset,
            effective_auto_connect_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            auto_connect_next,
            resolved_relative_to,
        )

        if pins is None:
            pins = _infer_default_pins(symbol_func)

        spec = ComponentSpec(
            func=symbol_func,
            tag_prefix=tag_prefix,
            kind="symbol",
            poles=poles,
            pins=pins,
            x_offset=effective_x_offset,
            y_increment=effective_spacing,
            auto_connect_next=effective_auto_connect_next,
            device=device,
            wire_labels_above=wire_labels_above,
            kwargs=kwargs,
            # Old placement fields (populated from new params during transition)
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            # New fields
            relative_to_idx=resolved_relative_to,
            position=position,
            autoconnect=autoconnect,
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
            if prev_spec.auto_connect_next and autoconnect:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with autoconnect, connect via position
        new_ref = ComponentRef(self, idx, tag_prefix)
        if not is_chain_component and autoconnect and resolved_relative_to is not None:
            if position == "above" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    new_ref.pole(0),
                    relative_to,  # type: ignore[arg-type]
                    side_a="bottom",
                    side_b="top",
                )
            elif position == "below" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    relative_to,  # type: ignore[arg-type]
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

    def add_spdt(  # noqa: C901
        self,
        tag_prefix: str = "K",
        poles: int = 1,
        pins: list[str] | tuple[str, ...] | None = None,
        inverted: bool = False,
        relative_to: "ComponentRef | PortRef | None" = None,
        position: str = "below",
        autoconnect: bool = False,
        spacing: float | None = None,
        x_offset: float = 0.0,
        y_increment: float | None = None,
        device: "InternalDevice | None" = None,
        wire_labels_above: list[str] | tuple[str, ...] | None = None,
    ) -> "ComponentRef":
        """Add an SPDT (changeover) contact to the circuit.

        Supports both single-pole and multi-pole SPDT symbols.
        Port keys match pin labels (e.g. ``"11"`` for COM, ``"12"`` for NC,
        ``"14"`` for NO).  Use with :meth:`place_above` / :meth:`place_below`
        to attach terminals to individual pins.

        Default pins follow IEC numbering: ``("11","12","14")`` for 1 pole,
        ``("11","12","14","21","22","24",...)`` for N poles.

        Always sets ``auto_connect_next=False`` since SPDT contacts branch
        and cannot participate in a linear auto-connect chain.

        Args:
            tag_prefix: Tag prefix for autonumbering (default ``"K"``).
            poles: Number of poles (default 1).
            pins: Explicit pin labels.  If *None*, IEC defaults are generated.
            inverted: If *True*, COM is at top, NC/NO at bottom.
            relative_to: ComponentRef or PortRef to place this component relative
                to. If None, defaults to the last chain component.
            position: Placement direction relative to ``relative_to``.
                One of "below", "above", "left", "right" (default "below").
            autoconnect: Whether to record an auto-connection from the reference
                component to this one (default False — SPDT contacts branch).
            spacing: Spacing override in mm. If None, uses ``y_increment`` or
                ``symbol_spacing``.
            x_offset: Horizontal offset in mm.
            y_increment: Vertical spacing override in mm.
                Kept for backward compatibility.
            device: Optional InternalDevice for BOM tracking.
            wire_labels_above: Wire labels for the wires above this component
                (connecting it to the previous component). One label per pole.

        Returns:
            ComponentRef for the added SPDT component.
        """
        from schematika.electrical.symbols.contacts import (
            multi_pole_spdt_symbol,
            spdt_contact_symbol,
        )

        self._check_not_frozen()

        # Generate default IEC pins if not provided
        if pins is None:
            pins = tuple(
                f"{p}{s}" for p in range(1, poles + 1) for s in ("1", "2", "4")
            )

        if poles == 1:
            func = spdt_contact_symbol
        else:
            func = multi_pole_spdt_symbol

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
            _effective_auto_connect_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            False,  # add_spdt always has auto_connect_next=False
            resolved_relative_to,
        )

        spec = ComponentSpec(
            func=func,
            tag_prefix=tag_prefix,
            kind="symbol",
            poles=poles,
            pins=pins,
            x_offset=effective_x_offset,
            y_increment=effective_spacing,
            auto_connect_next=False,
            device=device,
            wire_labels_above=wire_labels_above,
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            relative_to_idx=resolved_relative_to,
            position=position,
            autoconnect=autoconnect,
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
            if prev_spec.auto_connect_next and autoconnect:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with autoconnect, connect via position
        new_ref = ComponentRef(self, idx, tag_prefix)
        if not is_chain_component and autoconnect and resolved_relative_to is not None:
            if position == "above" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    new_ref.pole(0),
                    relative_to,  # type: ignore[arg-type]
                    side_a="bottom",
                    side_b="top",
                )
            elif position == "below" and isinstance(resolved_relative_to, tuple):
                self.connect(
                    relative_to,  # type: ignore[arg-type]
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

        # Update last chain index (add_spdt always has auto_connect_next=False,
        # so _last_chain_idx advances here but won't emit a connection forward)
        self._last_chain_idx = idx

        return new_ref

    def add_reference(
        self,
        ref_id: str,
        relative_to: "ComponentRef | PortRef | None" = None,
        position: str = "below",
        autoconnect: bool = True,
        spacing: float | None = None,
        x_offset: float = 0.0,
        y_increment: float | None = None,
        auto_connect_next: bool = True,
        wire_label: str | None = None,
        **kwargs,
    ) -> "ComponentRef":
        """
        Add a reference symbol (e.g., PLC:DO, PLC:AI).

        Reference symbols always use their ID as the tag (not auto-numbered).
        No manual tag_generators setup needed.

        Args:
            ref_id: The reference identifier (e.g., "PLC:DO").
            relative_to: ComponentRef or PortRef to place this reference relative
                to. If None, defaults to the last chain component.
            position: Placement direction relative to ``relative_to``.
                One of "below", "above", "left", "right" (default "below").
            autoconnect: Whether to record an auto-connection from the reference
                component to this one (default True).
            spacing: Spacing override in mm. If None, uses ``y_increment`` or
                ``symbol_spacing``.
            x_offset: Horizontal offset.
            y_increment: Vertical spacing override.
                Kept for backward compatibility.
            auto_connect_next: Whether to auto-connect to next component.
                Kept for backward compatibility.
            wire_label: Wire label for the connecting wire
                (e.g. ``wire("RD", "0.5mm2")``).

        Returns: ComponentRef
        """
        self._check_not_frozen()
        from schematika.electrical.symbols.references import ref_symbol

        # Register a fixed tag generator for this reference ID
        def fixed_gen(state):
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
            effective_auto_connect_next,
        ) = self._resolve_placement(
            relative_to,
            position,
            spacing,
            x_offset,
            auto_connect_next,
            resolved_relative_to,
        )

        spec = ComponentSpec(
            func=ref_symbol,
            tag_prefix=ref_id,
            kind="reference",
            x_offset=effective_x_offset,
            y_increment=effective_spacing,
            auto_connect_next=effective_auto_connect_next,
            placed_right_of=placed_right_of,
            placed_above_of=placed_above_of,
            placed_below_of=placed_below_of,
            relative_to_idx=resolved_relative_to,
            position=position,
            autoconnect=autoconnect,
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
            if prev_spec.auto_connect_next and autoconnect:
                self._spec.planned_connections.append(
                    PlannedConnection(
                        source_idx=self._last_chain_idx,
                        target_idx=idx,
                        kind="chain",
                    )
                )

        # For non-chain placements with autoconnect, connect via position
        if not is_chain_component and autoconnect and resolved_relative_to is not None:
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
        position: str,
        resolved_relative_to: "int | tuple[int, str]",
        wire_label: str | None,
    ) -> None:
        """Connect a non-chain placed reference to its anchor component."""
        if position == "above" and isinstance(resolved_relative_to, tuple):
            self.connect(
                new_ref.pole(0),
                relative_to,  # type: ignore[arg-type]
                side_a="bottom",
                side_b="top",
                wire_label=wire_label,
            )
        elif position == "below" and isinstance(resolved_relative_to, tuple):
            self.connect(
                relative_to,  # type: ignore[arg-type]
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
        side_a: str = "right",
        side_b: str = "left",
    ) -> "CircuitBuilder":
        """
        Connect two components horizontally on pins that share the same name.

        Draws horizontal wires between matching pin pairs. Only pins with
        identical names on both components are connected.

        Args:
            ref_a: First component reference.
            ref_b: Second component reference.
            pins: Explicit pin filter. If None, connects all matching pins.
            side_a: Connection side on ref_a (default "right").
            side_b: Connection side on ref_b (default "left").

        Returns: self for chaining.
        """
        self._check_not_frozen()
        self._spec.matching_connections.append(
            (ref_a._index, ref_b._index, pins, side_a, side_b)
        )
        return self

    def connect(
        self,
        a: PortRef,
        b: PortRef,
        side_a: str | None = None,
        side_b: str | None = None,
        wire_label: str | None = None,
    ) -> "CircuitBuilder":
        """
        Connect two ports by pin name or pole index.

        This is the pin-based connection API that coexists with add_connection().

        Args:
            a: Source port reference (e.g., tm.pin("1") or cb.pole(0)).
            b: Target port reference (e.g., cb.pin("1") or psu.pin("L")).
            side_a: Connection side on component a. If None, inferred.
            side_b: Connection side on component b. If None, inferred.
            wire_label: Wire label string for this connection.

        Returns: self for chaining.
        """
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
                        return i // 2 if spec.kind == "symbol" else i // 2
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
        pole_idx_a: int,
        comp_idx_b: int,
        pole_idx_b: int,
        side_a: str = "bottom",
        side_b: str = "top",
        wire_label: str | None = None,
    ) -> "CircuitBuilder":
        """Add an explicit connection between components by index.

        Low-level connection API. Prefer ``connect()`` for pin-based
        connections using ``ComponentRef`` / ``PortRef``.

        Args:
            comp_idx_a: Source component index (0-based).
            pole_idx_a: Source pole index (0-based).
            comp_idx_b: Target component index (0-based).
            pole_idx_b: Target pole index (0-based).
            side_a: Connection side on component a ('top' or 'bottom').
            side_b: Connection side on component b ('top' or 'bottom').
            wire_label: Wire label string for this connection.

        Returns:
            self for method chaining.
        """
        self._check_not_frozen()
        self._spec.manual_connections.append(
            (comp_idx_a, pole_idx_a, comp_idx_b, pole_idx_b, side_a, side_b)
        )
        if wire_label is not None:
            conn_idx = len(self._spec.manual_connections) - 1
            self._spec.connection_wire_labels[conn_idx] = wire_label
        return self

    def _validate_connections(self) -> None:
        """
        Validate all connections before building.

        Raises:
            ComponentNotFoundError: If a connection references invalid component index
            PortNotFoundError: If a connection references invalid port
        """
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
        """
        Merge tag generators from all sources.

        Priority (highest wins):
            tag_generators > reuse_tags > fixed_tags > _fixed_tag_generators

        Args:
            reuse_tags: Dict mapping prefix to BuildResult whose tags to reuse.
            tag_generators: Custom tag generator callables keyed by prefix.
            fixed_tags: Dict mapping prefix to a fixed tag string, e.g.
                ``{"K": "K1"}``. Converted internally to generator lambdas.

        Returns:
            The merged dict, or None if no generators were specified.
        """
        effective: dict[str, Callable] = {**self._fixed_tag_generators}
        if fixed_tags:
            for prefix, tag_value in fixed_tags.items():
                effective[prefix] = lambda s, _t=tag_value: (s, _t)
        if reuse_tags:
            for prefix, source_result in reuse_tags.items():
                effective[prefix] = source_result.reuse_tags(prefix)
        if tag_generators:
            for prefix, gen in tag_generators.items():
                effective[prefix] = gen
        return effective if effective else None

    def _build_terminal_reuse_generators(
        self,
        reuse_terminals: "dict[str, BuildResult | CircuitBuilder | Callable] | None",
    ) -> dict[str, Callable]:
        """
        Convert reuse_terminals mapping to callable pin generators.

        Returns a dict mapping terminal key strings to pin generator callables.
        Returns an empty dict if reuse_terminals is None or empty.
        """
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
            if comp.kind != "terminal" or comp.bridge is False:
                continue
            if comp.poles < 2:
                continue

            tm_id = comp.kwargs.get("tm_id")
            tid = str(tm_id)

            # For bridge="auto", check the Terminal object's bridge attribute
            if comp.bridge == "auto":
                term_bridge = getattr(tm_id, "bridge", None)
                if term_bridge != "all":
                    continue

            pins = terminal_pin_map.get(tid, [])
            if len(pins) < 2:
                continue

            # Group pins by poles per instance
            poles = comp.poles
            for i in range(0, len(pins), poles):
                chunk = pins[i : i + poles]
                if len(chunk) >= 2:
                    int_pins = sorted(int(p.split(":")[-1]) for p in chunk)
                    bridge_groups.setdefault(tid, []).append(
                        (int_pins[0], int_pins[-1])
                    )

        return bridge_groups

    def build(  # noqa: C901
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
        """
        Generate the circuits.

        Args:
            count: Number of circuit instances to create.
            start_indices: Override tag counters (e.g., {"K": 3}).
            terminal_start_indices: Override terminal pin counters.
            tag_generators: Custom tag generator callables keyed by prefix.
            fixed_tags: Dict mapping prefix to a fixed tag string, e.g.
                ``{"K": "K1"}``. Lower priority than ``tag_generators`` and
                ``reuse_tags``, but higher than internal fixed generators.
            terminal_maps: Terminal ID overrides by logical name.
            reuse_tags: Dict mapping tag prefix to BuildResult whose tags to reuse.
                        e.g., {"K": coil_result} reuses K tags from coil_result.
            reuse_terminals: Dict mapping terminal key to BuildResult whose
                        terminal pins to reuse. Keys can be terminal tag strings
                        (e.g., "X008") or logical names.
                        e.g., {Terminals.IO_EXT: pump_result} reuses IO_EXT pins.
            wire_labels: Wire label strings to apply to vertical wires.
                         When count > 1, provide count * labels_per_instance labels.
            state: Override the state for this build. If provided, takes
                   precedence over the state passed to ``CircuitBuilder()``.

        Returns:
            BuildResult with state, circuit, used_terminals, component_map,
            and terminal_pin_map.

        Raises:
            ComponentNotFoundError: If a connection references an invalid index.
            PortNotFoundError: If a connection references an invalid port.
            TagReuseError: If reuse_tags runs out of tags from the source.
            TerminalReuseError: If reuse_terminals runs out of pins.
            WireLabelMismatchError: If label count doesn't match vertical wire count.
        """
        self._check_not_frozen()
        self._validate_connections()
        effective_state = state if state is not None else self._initial_state
        if effective_state is None:
            raise ValueError(
                "No state provided. Pass state to CircuitBuilder() or build(state=...)."
            )

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
        captured_device_registry: dict[str, "InternalDevice"] = {}

        def single_instance_gen(s, x, y, gens, tm):
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
            # res is (state, elements, instance_tags, wire_connections)
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
            generator_func_single=lambda s, x, y, gens, tm, instance: (
                single_instance_gen(s, x, y, gens, tm)
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
            with open(log_path, "w") as f:
                f.write(f"# Connection Log — {datetime.now().isoformat()}\n")
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
            raise RuntimeError(
                "CircuitBuilder has not been built yet. Call build() first."
            )
        return self._result

    @property
    def result(self) -> BuildResult:
        return self._check_built()

    @property
    def state(self) -> "GenerationState":
        return self._check_built().state

    @property
    def circuit(self) -> Circuit:
        return self._check_built().circuit

    @property
    def used_terminals(self) -> list[Any]:
        return self._check_built().used_terminals

    @property
    def component_map(self) -> dict[str, list[str]]:
        return self._check_built().component_map

    @property
    def terminal_pin_map(self) -> dict[str, list[str]]:
        return self._check_built().terminal_pin_map

    @property
    def device_registry(self) -> "dict[str, InternalDevice]":
        return self._check_built().device_registry

    @property
    def wire_connections(self) -> list[tuple[str, str, str, str]]:
        return self._check_built().wire_connections

    @property
    def bridge_groups(self) -> dict[str, list[tuple[int, int]]]:
        return self._check_built().bridge_groups

    # ------------------------------------------------------------------
    # Reuse helpers — forwarded to stored BuildResult
    # ------------------------------------------------------------------

    def reuse_tags(self, prefix: str) -> Callable:
        return self._check_built().reuse_tags(prefix)

    def reuse_terminals(self, key: str) -> Callable:
        return self._check_built().reuse_terminals(key)

    # ------------------------------------------------------------------
    # Merge — combine multiple frozen builders into one
    # ------------------------------------------------------------------

    @staticmethod
    def merge(*builders: "CircuitBuilder") -> "CircuitBuilder":
        """Merge multiple frozen CircuitBuilders into one.

        All builders must be frozen (already built). Returns a new frozen
        CircuitBuilder with merged circuits, terminals, wire_connections,
        device_registry, bridge_groups, component_map, and terminal_pin_map.
        State is taken from the last builder.
        """
        if not builders:
            raise ValueError("merge() requires at least one CircuitBuilder")
        for b in builders:
            if not b._frozen:
                raise RuntimeError("All builders must be frozen (built) before merging")

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
