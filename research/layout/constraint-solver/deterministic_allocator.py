"""Plain deterministic placement -- no solver, direct assignment logic.

The three rules (zone pinning, no-overlap, column ordering by circuit index)
form a total order once you notice that "column ordering" already sorts
every component by circuit index. That collapses no-overlap from a real
disjunctive choice ("place A left of B, or B left of A -- pick one") into a
single forced direction. What's left is a one-pass prefix-sum over circuits
sorted by index, which is exactly a longest-path computation on a DAG of
difference constraints (`col_x[c+1] >= col_x[c] + max_width[c] + GAP`) --
solvable in O(n) with no search or backtracking at all.
"""

from __future__ import annotations

from circuit import GAP, Component


def allocate(components: list[Component]) -> dict[str, float]:
    """Assign every component an X position (mm); Y is fixed by zone.

    Args:
        components: The synthetic cabinet to place.

    Returns:
        `{component_id: x_position}`, one shared X per circuit (a "column"),
        packed left to right with `GAP` mm clearance against the widest
        component that circuit contributes to any zone.
    """
    by_circuit: dict[int, list[Component]] = {}
    for c in components:
        by_circuit.setdefault(c.circuit, []).append(c)

    col_x: dict[int, float] = {}
    x = 0.0
    for circuit in sorted(by_circuit):
        col_x[circuit] = x
        max_width = max(c.width for c in by_circuit[circuit])
        x += max_width + GAP

    return {c.id: col_x[c.circuit] for c in components}
