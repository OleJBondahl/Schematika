"""A large, real-factory synthetic cabinet circuit for the round-2 deep dive.

Round 1's demo circuit was 14 hand-wired symbols. This is the same idea at
roughly an order of magnitude larger scale, and -- the actual point of round
2 -- built entirely through `CircuitBuilder`'s real public API plus real
`electrical.symbols` factories. Nothing here calls `translate()` or writes a
`Point()` by hand for a *component*; `CircuitBuilder` places every symbol.

Structure, scaling with `n_branches` (component count is `6*n_branches + 2`):

    Main row (one CircuitBuilder, one build()):
        S0 (e-stop, common-stop contact) -- F1 -- F2 -- ... -- Fn -- N1
        placed left-to-right with `position="right"`, fed by a hand-drawn
        top busbar `Line` (bus geometry, not a component -- same convention
        round 1's `synthetic_circuit.py` used). N1 is a shared neutral
        terminal every branch's coil return (A2) lands on -- see the
        pin-resolver note below for why it exists.

    Branch i, i = 1..n (one CircuitBuilder per branch, its own build()):
        Ki (contactor, 3-pole + coil)  ->  Mi (3-phase motor)
        chained top-to-bottom, `CircuitBuilder`'s own default wiring.

    Terminal strip (one CircuitBuilder, one build()):
        X1 .. X(3n), a flat row, unwired (representing spare/field terminals
        -- real symbols, real obstacles, no forced topology).

Why per-branch builders instead of one big builder: `CircuitBuilder`'s
relative-placement API (`placed_right_of` / `placed_above_of` /
`placed_below_of`) is built around ONE active vertical chain at a time
(`_last_chain_idx`); branching it into N independent parallel chains inside a
single builder instance is not what the API is for (confirmed empirically
while building this -- see the deep-dive doc). Building each branch as its
own small builder and merging them (`CircuitBuilder.merge`) is both simpler
and matches the documented common case (CLAUDE.md: "today's manual placement
already handles the common case... single vertical chain").

The unavoidable consequence: **cross-branch wiring cannot be expressed by any
builder's `connect()`** (each builder only knows its own component indices).
Two real cross-branch topologies are declared here as plain
`(from_tag, from_pin, to_tag, to_pin)` tuples -- the same shape
`BuildResult.wire_connections` already uses -- and handed to
`topology_bridge.derive_routing_input` as `extra_connections`:

1. `Fi -> Ki`: each branch's own supply feed from the main row.
2. `S0 -> Ki.A1` (all n branches): the common emergency-stop chain fanning
   out from one physical contact to every branch's contactor coil -- an
   n-way generalization of round 1's `K1_aux -> Q1, Q2` two-way fan-out,
   now at real cabinet scale and crossing every intervening branch column.

This *is* the bridge's job: a real cabinet's cross-functional-group wiring
(safety chain, shared supply) is exactly what a single chain-based builder
cannot express, and exactly what `Harness`/`Project.route()` exist for at
the `electrical` layer today for PLC-side wiring. This spike doesn't reuse
`Harness` (it batch-allocates PLC channels, which is not needed here) but
produces the same shaped input a `Harness`-level bridge would.

Not production code. Throwaway research spike, not imported by `src/schematika`.
"""

from __future__ import annotations

from dataclasses import dataclass

from schematika.core.geometry import Point
from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    PlacementOptions,
    SymbolConfig,
)
from schematika.core.parts import standard_style
from schematika.core.primitives import Line
from schematika.electrical import CircuitBuilder, create_initial_state
from schematika.electrical.builder_models import BuildResult
from schematika.electrical.model.constants import CIRCUIT_SPACING, SPACING_STANDARD
from schematika.electrical.symbols import contactor, estop, fuse, motor

BRANCH_PITCH = CIRCUIT_SPACING  # 100mm between branch columns, existing constant
TERM_PITCH = BRANCH_PITCH / 3
CONTACTOR_Y = 2 * SPACING_STANDARD
TERMINAL_Y = 6 * SPACING_STANDARD
BUS_STYLE = standard_style()

CONTACTOR_PINS = ("L1", "T1", "L2", "T2", "L3", "T3")


@dataclass(frozen=True)
class LargeCabinet:
    """A merged BuildResult plus the cross-branch tuples the bridge needs."""

    result: BuildResult
    extra_connections: list[tuple[str, str, str, str]]
    n_branches: int
    bus_elements: list[Line]

    @property
    def n_components(self) -> int:
        """Total placed, tagged symbols (matches the `6*n_branches + 1` formula).

        Counts labeled `Symbol`s in `circuit.elements` directly rather than
        summing `component_map` -- see the `component_tags()` note in
        `build_large_cabinet` for why that dict undercounts here.
        """
        from schematika.core.symbol import Symbol

        return sum(
            1 for e in self.result.circuit.elements if isinstance(e, Symbol) and e.label
        )

    @property
    def symbols(self) -> list[Symbol]:
        """Every placed, tagged Symbol (drops the hand-drawn busbar Lines)."""
        from schematika.core.symbol import Symbol

        return [
            e for e in self.result.circuit.elements if isinstance(e, Symbol) and e.label
        ]


def build_large_cabinet(n_branches: int) -> LargeCabinet:
    """Build an `n_branches`-branch cabinet from real factories via CircuitBuilder.

    Args:
        n_branches: Number of independent motor/control branches. Component
            count scales as `6*n_branches + 2` (1 e-stop + n fuses + 1
            neutral terminal + n contactors + n motors + 3n field terminals).

    Returns:
        `LargeCabinet` with the merged `BuildResult` (main row + every
        branch + terminal strip) and the cross-branch connection tuples that
        no single builder's `wire_connections` could produce.
    """
    state = create_initial_state()

    main_cb = CircuitBuilder(state=state)
    main_cb.set_layout(x=0, y=0)
    s0_ref = main_cb.add_symbol(
        estop,
        config=SymbolConfig(tag_prefix="S"),
        connection=ConnectionOptions(connect_to_next=False),
    )
    prev = s0_ref
    for i in range(n_branches):
        f_ref = main_cb.add_symbol(
            fuse,
            config=SymbolConfig(tag_prefix="F"),
            placement=PlacementOptions(
                relative_to=prev, position="right", x_offset=BRANCH_PITCH
            ),
            connection=ConnectionOptions(
                connect_from_previous=False, connect_to_next=False
            ),
        )
        prev = f_ref
    # Common neutral bus point every branch's coil return (A2) lands on. Also
    # closes a real pin-resolver defect found while building this circuit:
    # without *something* claiming each K_i.A2 via an exact-match query, the
    # position heuristic's down-facing pool for a contactor is [A2, T1, T2,
    # T3] sorted by x (A2, the coil return, sits left of the 3 power
    # contacts) and the *first* source-role query for that tag -- physically
    # T1, a power contact -- gets wrongly assigned to A2 instead. Wiring A2
    # to a real neutral terminal removes it from the pool via an exact match
    # before the heuristic ever runs. See pin_resolver.py's module docstring.
    main_cb.add_terminal(
        "N1",
        placement=PlacementOptions(
            relative_to=prev, position="right", x_offset=BRANCH_PITCH
        ),
        connection=ConnectionOptions(
            connect_from_previous=False, connect_to_next=False
        ),
    )
    main_result = main_cb.build(options=BuildOptions(state=state))
    state = main_result.state
    # NOTE: `component_tags("F")` is unreliable here -- a real gap found while
    # building this circuit. `component_map`/`captured_tags` records only the
    # *last* tag per prefix generated within a single build() call (it assumes
    # one component per prefix per circuit instance, the common case of a
    # repeated single-instance spec via `count=`). Since this spec places N
    # same-prefix fuses in one build(), `main_result.component_map["F"]` is
    # `["F{n}"]`, not all N tags, even though every fuse *is* correctly placed
    # and labeled in `circuit.elements`. Tags are reconstructed directly
    # instead, since autonumbering on a fresh state is deterministic.
    fuse_tags = [f"F{i + 1}" for i in range(n_branches)]
    s0_tag = "S1"

    # Hand-drawn main busbar (geometry, not a component -- matches round 1's
    # synthetic_circuit.py convention for power rails).
    top_y = -SPACING_STANDARD
    bus_elements: list[Line] = []
    first_x = main_result.get_symbol(fuse_tags[0]).ports["1"].position.x
    last_x = main_result.get_symbol(fuse_tags[-1]).ports["1"].position.x
    bus_elements.append(
        Line(Point(first_x, top_y), Point(last_x, top_y), style=BUS_STYLE)
    )
    for tag in fuse_tags:
        p = main_result.get_symbol(tag).ports["1"].position
        bus_elements.append(Line(Point(p.x, top_y), p, style=BUS_STYLE))

    branch_builders: list[CircuitBuilder] = []
    extra_connections: list[tuple[str, str, str, str]] = []
    for i, f_tag in enumerate(fuse_tags):
        branch_x = i * BRANCH_PITCH
        branch_cb = CircuitBuilder(state=state)
        branch_cb.set_layout(x=branch_x, y=CONTACTOR_Y)
        branch_cb.add_symbol(
            contactor,
            config=SymbolConfig(
                tag_prefix="K",
                poles=3,
                pins=CONTACTOR_PINS,
                factory_kwargs={"coil_pins": ("A1", "A2")},
            ),
            connection=ConnectionOptions(connect_from_previous=False),
        )
        branch_cb.add_symbol(
            motor,
            config=SymbolConfig(tag_prefix="M", poles=3, factory_kwargs={"poles": 3}),
        )
        branch_result = branch_cb.build(options=BuildOptions(state=state))
        state = branch_result.state
        branch_builders.append(branch_cb)

        k_tag = branch_result.component_tag("K")
        extra_connections.append((f_tag, "2", k_tag, "L1"))
        extra_connections.append((s0_tag, "2", k_tag, "A1"))
        extra_connections.append((k_tag, "A2", "N1", "1"))

    term_cb = CircuitBuilder(state=state)
    term_cb.set_layout(x=0, y=TERMINAL_Y)
    prev_term = None
    for i in range(3 * n_branches):
        placement = (
            None
            if prev_term is None
            else PlacementOptions(
                relative_to=prev_term, position="right", x_offset=TERM_PITCH
            )
        )
        connection = ConnectionOptions(
            connect_from_previous=False, connect_to_next=False
        )
        prev_term = term_cb.add_terminal(
            f"X{i + 1}", placement=placement, connection=connection
        )
    term_cb.build(options=BuildOptions(state=state))

    merged = CircuitBuilder.merge(main_cb, *branch_builders, term_cb)
    merged_result = merged.result
    # Splice in the hand-drawn busbar geometry (not part of any builder's
    # own `circuit.elements` since it isn't a component).
    from schematika.electrical.system.system import Circuit

    full_elements = list(merged_result.circuit.elements) + bus_elements
    patched_circuit = Circuit(elements=full_elements)
    patched_result = BuildResult(
        state=merged_result.state,
        circuit=patched_circuit,
        used_terminals=merged_result.used_terminals,
        component_map=merged_result.component_map,
        terminal_pin_map=merged_result.terminal_pin_map,
        device_registry=merged_result.device_registry,
        wire_connections=merged_result.wire_connections,
        bridge_groups=merged_result.bridge_groups,
        connection_log=merged_result.connection_log,
    )

    return LargeCabinet(
        result=patched_result,
        extra_connections=extra_connections,
        n_branches=n_branches,
        bus_elements=bus_elements,
    )
