"""Prototype: generic layered-graph (Sugiyama-style) auto-layout for P&ID
equipment.

Equipment are nodes, process pipes are edges, flow direction is the
layering axis. Longest-path layering assigns each node a column (x); a
`lane` on the edge (declared by the caller, e.g. "this is a bypass") moves
a node to a parallel row (y). Recycle/return lines are marked `back_edge`
so they don't participate in layering — the same generic-graph approach
`pure-python-graph-layout` uses for `electrical`.

Column spacing is measured from real symbol bounding boxes
(`schematika.core.renderer.calculate_bounds`) plus `PID_MIN_EQUIPMENT_GAP`,
not from a hand-picked pipe-run length. That is the one substantive
difference from the manual workflow in `manual_layout.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from schematika.core.geometry import Point
from schematika.core.renderer import calculate_bounds
from schematika.pid.constants import PID_MIN_EQUIPMENT_GAP, PID_MIN_LEG_SPACING

if TYPE_CHECKING:
    from schematika.core.symbol import Symbol

    from scenario import PipeDef


def layer_by_longest_path(
    nodes: list[str], edges: list[PipeDef]
) -> dict[str, int]:
    """Longest-path layering over the forward (non-back-edge) subgraph.

    Raises:
        ValueError: If the forward subgraph still has a cycle (a real
            recycle/bypass edge wasn't marked ``back_edge=True``).
    """
    forward = [e for e in edges if not e.back_edge]
    preds: dict[str, list[str]] = {n: [] for n in nodes}
    for e in forward:
        preds[e.dst].append(e.src)

    layer: dict[str, int] = {}

    def resolve(node: str, trail: frozenset[str]) -> int:
        if node in layer:
            return layer[node]
        if node in trail:
            msg = f"Cycle in forward flow graph at {node!r} — mark it back_edge=True"
            raise ValueError(msg)
        if not preds[node]:
            layer[node] = 0
        else:
            layer[node] = 1 + max(
                resolve(p, trail | {node}) for p in preds[node]
            )
        return layer[node]

    for n in nodes:
        resolve(n, frozenset())
    return layer


def compute_positions(
    nodes: list[str],
    edges: list[PipeDef],
    symbols: dict[str, Symbol],
) -> dict[str, Point]:
    """Column (x) from longest-path layer + measured half-width; lane -> row (y)."""
    layers = layer_by_longest_path(nodes, edges)

    # A node that touches any lane-0 (main line) edge stays on the main
    # line even if it *also* touches a branch edge (e.g. the pump feeds
    # both the main line and the bypass) -- only a node exclusive to the
    # branch moves to that branch's lane.
    main_nodes = {n for e in edges if e.lane == 0 for n in (e.src, e.dst)}
    lane_of: dict[str, int] = dict.fromkeys(nodes, 0)
    for e in edges:
        if not e.lane:
            continue
        if e.src not in main_nodes:
            lane_of[e.src] = e.lane
        if e.dst not in main_nodes:
            lane_of[e.dst] = e.lane

    half_width: dict[str, float] = {}
    for n in nodes:
        min_x, _, max_x, _ = calculate_bounds(symbols[n].elements)
        half_width[n] = max(abs(min_x), abs(max_x))

    by_layer: dict[int, list[str]] = {}
    for n in nodes:
        by_layer.setdefault(layers[n], []).append(n)

    x_of: dict[str, float] = {}
    cursor = 0.0
    prev_half = 0.0
    for layer_idx in sorted(by_layer):
        layer_nodes = by_layer[layer_idx]
        layer_half = max(half_width[n] for n in layer_nodes)
        cursor = layer_half if layer_idx == 0 else cursor + prev_half + PID_MIN_EQUIPMENT_GAP + layer_half
        for n in layer_nodes:
            x_of[n] = cursor
        prev_half = layer_half

    return {n: Point(x_of[n], lane_of[n] * PID_MIN_LEG_SPACING) for n in nodes}
