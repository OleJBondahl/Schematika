"""z3-solver (SMT) model for the same three placement rules.

Models the full pairwise no-overlap disjunction explicitly (`Or(a left of
b, b left of a)`) per zone, the way you would naturally reach for it before
noticing the column-ordering constraint already fixes the direction. This
is deliberately the "honest first draft" a person would write, not the
collapsed DAG form -- see `deterministic_allocator.py` for that.
"""

from __future__ import annotations

import time

from z3 import Int, Optimize, Or, sat

from circuit import GAP, Component


def solve(components: list[Component]) -> tuple[dict[str, float], float, str]:
    """Solve for X positions with z3.

    Args:
        components: The synthetic cabinet to place.

    Returns:
        Tuple of (`{component_id: x_position}`, solve wall-clock seconds,
        z3 check-result string).
    """
    circuits = sorted({c.circuit for c in components})
    col_x = {circuit: Int(f"col_{circuit}") for circuit in circuits}
    x = {c.id: Int(f"x_{c.id}") for c in components}

    by_circuit: dict[int, list[Component]] = {}
    by_kind: dict[str, list[Component]] = {}
    for c in components:
        by_circuit.setdefault(c.circuit, []).append(c)
        by_kind.setdefault(c.kind, []).append(c)

    opt = Optimize()

    # Zone pinning is handled outside the model (Y = ZONE_Y[kind], a fixed
    # lookup); only X is a decision variable here.

    # Column ordering by circuit index: strictly increasing column X,
    # spaced by the widest component that circuit places in any zone.
    opt.add(col_x[circuits[0]] >= 0)
    for a, b in zip(circuits, circuits[1:]):
        max_width = max(c.width for c in by_circuit[a])
        opt.add(col_x[b] >= col_x[a] + max_width + GAP)

    for c in components:
        opt.add(x[c.id] == col_x[c.circuit])

    # No-overlap within each zone: pairwise disjunction over bounding boxes.
    for comps in by_kind.values():
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                ci, cj = comps[i], comps[j]
                opt.add(
                    Or(
                        x[ci.id] + ci.width + GAP <= x[cj.id],
                        x[cj.id] + cj.width + GAP <= x[ci.id],
                    )
                )

    opt.minimize(col_x[circuits[-1]])

    start = time.perf_counter()
    result = opt.check()
    elapsed = time.perf_counter() - start

    positions: dict[str, float] = {}
    if result == sat:
        model = opt.model()
        positions = {c.id: float(model[x[c.id]].as_long()) for c in components}

    return positions, elapsed, str(result)
