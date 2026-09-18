"""The topology -> router bridge round 1 flagged as the real integration gap.

Round 1's `research/layout/grid-astar-router/synthetic_circuit.py` hand-authored
which symbols connect to which and passed real `Symbol.ports[...]` positions
straight to the router. That is not how a real cabinet's topology is known --
the only real source of truth is a `CircuitBuilder.build()` result: its
`wire_connections` (semantic `(from_tag, from_pin, to_tag, to_pin)` tuples) and
its `circuit.elements` (placed `Symbol`s).

This module is that bridge, built and tested for real in round 2:

    BuildResult.wire_connections + circuit.elements
        --[pin_resolver.build_pin_resolver]-->
    RoutingInput(pairs=[RoutePair(...)], obstacles, unresolved=[...])
        --[router_core.OrthogonalRouter]-->
    routed wires

`derive_routing_input` also accepts `extra_connections` in the exact same
4-tuple shape as `wire_connections`, because a real cabinet's *cross-branch*
wiring (an interlock, a shared e-stop chain, a supply feed into a separately
built motor branch) cannot be expressed inside a single `CircuitBuilder`
chain -- see `large_cabinet.py`'s module docstring for why -- and would in
a real `electrical.layout` module come from something Harness/Project-level
like `route()`. Feeding both through the same resolver proves the bridge
doesn't care about the tuple's origin, only its shape, which is the shape a
per-page circuit subset from `pagination-partitioner` could also plausibly
produce (see the deep-dive doc's Integration awareness section).

Not production code. Throwaway research spike, not imported by `src/schematika`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pin_resolver import build_pin_resolver

from schematika.core.bbox import BoundingBox, compute_bounding_box
from schematika.core.symbol import Symbol

if TYPE_CHECKING:
    from schematika.core.geometry import Point
    from schematika.electrical.builder_models import BuildResult

WireConnection = tuple[str, str, str, str]


@dataclass(frozen=True)
class RoutePair:
    """One resolved (port, port) pair the router needs to connect."""

    from_tag: str
    from_port_id: str
    from_point: Point
    to_tag: str
    to_port_id: str
    to_point: Point
    resolution_kind: str  # "exact" | "heuristic" -- see pin_resolver.build_pin_resolver


@dataclass(frozen=True)
class RoutingInput:
    """Everything `OrthogonalRouter` needs, derived from a real `BuildResult`."""

    symbols: dict[str, Symbol]
    pairs: list[RoutePair] = field(default_factory=list)
    unresolved: list[WireConnection] = field(default_factory=list)

    @property
    def heuristic_fraction(self) -> float:
        """Share of resolved pairs whose *both* endpoints were exact matches.

        The complement is pairs relying on the position heuristic for at
        least one endpoint -- i.e. a guess, not a certainty. See the
        deep-dive doc's quality section for why this number matters more
        than "0 unresolved".
        """
        if not self.pairs:
            return 0.0
        exact = sum(1 for p in self.pairs if p.resolution_kind == "exact")
        return 1.0 - exact / len(self.pairs)


def derive_routing_input(
    result: BuildResult,
    *,
    extra_connections: list[WireConnection] | None = None,
) -> RoutingInput:
    """Derive router-ready (port, port) pairs + a tag->Symbol map from a BuildResult.

    Args:
        result: Output of one or more merged `CircuitBuilder.build()` calls.
        extra_connections: Cross-branch wire tuples in the same
            `(from_tag, from_pin, to_tag, to_pin)` shape as
            `result.wire_connections`, for topology that spans more than one
            builder (see module docstring).

    Returns:
        `RoutingInput` with every resolvable pair as a `RoutePair` and every
        tuple the pin resolver couldn't map to a real port in `unresolved`.
    """
    symbols: dict[str, Symbol] = {}
    for elem in result.circuit.elements:
        if isinstance(elem, Symbol) and elem.label:
            symbols[elem.label] = elem

    all_connections = list(result.wire_connections) + list(extra_connections or [])
    known_connections = [
        (ft, fp, tt, tp)
        for ft, fp, tt, tp in all_connections
        if ft in symbols and tt in symbols
    ]
    queries: list[tuple[str, str, str]] = []
    for from_tag, from_pin, to_tag, to_pin in known_connections:
        queries.append((from_tag, from_pin, "source"))
        queries.append((to_tag, to_pin, "target"))

    resolved, resolution_kind, _unresolved_queries = build_pin_resolver(
        result.circuit.elements, queries
    )

    pairs: list[RoutePair] = []
    unresolved: list[WireConnection] = [
        (ft, fp, tt, tp)
        for ft, fp, tt, tp in all_connections
        if ft not in symbols or tt not in symbols
    ]
    for from_tag, from_pin, to_tag, to_pin in known_connections:
        real_from = resolved.get((from_tag, from_pin, "source"))
        real_to = resolved.get((to_tag, to_pin, "target"))
        if real_from is None or real_to is None:
            unresolved.append((from_tag, from_pin, to_tag, to_pin))
            continue
        from_sym, to_sym = symbols[from_tag], symbols[to_tag]
        both_exact = (
            resolution_kind.get((from_tag, from_pin, "source")) == "exact"
            and resolution_kind.get((to_tag, to_pin, "target")) == "exact"
        )
        pairs.append(
            RoutePair(
                from_tag=from_tag,
                from_port_id=real_from,
                from_point=from_sym.ports[real_from].position,
                to_tag=to_tag,
                to_port_id=real_to,
                to_point=to_sym.ports[real_to].position,
                resolution_kind="exact" if both_exact else "heuristic",
            )
        )

    return RoutingInput(symbols=symbols, pairs=pairs, unresolved=unresolved)


def obstacles_excluding(
    symbols: dict[str, Symbol], exclude_tags: set[str]
) -> list[BoundingBox]:
    """Bounding boxes of every symbol *except* the given tags (a route's own endpoints)."""
    return [
        compute_bounding_box(sym)
        for tag, sym in symbols.items()
        if tag not in exclude_tags
    ]


def all_symbols_bounds(symbols: dict[str, Symbol]) -> BoundingBox:
    """Bounding box enclosing every placed symbol (the router's page bounds)."""
    return compute_bounding_box(list(symbols.values()))  # type: ignore[arg-type]
