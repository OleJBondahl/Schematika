"""OR-tools CP-SAT model for the same three placement rules.

CP-SAT has native `NewIntervalVar` + `AddNoOverlap`, purpose-built for
"these things must not overlap on an axis" -- so the no-overlap rule is one
call per zone instead of z3's hand-written pairwise `Or()` loop. Column
ordering and zone pinning are modeled the same way as `solve_z3.py`.
"""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from circuit import GAP, Component

_BIG_M = 10_000  # mm, generous upper bound on total cabinet width


def solve(components: list[Component]) -> tuple[dict[str, float], float, str]:
    """Solve for X positions with OR-tools CP-SAT.

    Args:
        components: The synthetic cabinet to place.

    Returns:
        Tuple of (`{component_id: x_position}`, solve wall-clock seconds,
        CP-SAT status name).
    """
    model = cp_model.CpModel()

    circuits = sorted({c.circuit for c in components})
    col_x = {
        circuit: model.new_int_var(0, _BIG_M, f"col_{circuit}")
        for circuit in circuits
    }
    x = {c.id: model.new_int_var(0, _BIG_M, f"x_{c.id}") for c in components}

    by_circuit: dict[int, list[Component]] = {}
    by_kind: dict[str, list[Component]] = {}
    for c in components:
        by_circuit.setdefault(c.circuit, []).append(c)
        by_kind.setdefault(c.kind, []).append(c)

    # Column ordering by circuit index.
    model.add(col_x[circuits[0]] == 0)
    for a, b in zip(circuits, circuits[1:]):
        max_width = int(max(c.width for c in by_circuit[a]))
        model.add(col_x[b] >= col_x[a] + max_width + int(GAP))

    for c in components:
        model.add(x[c.id] == col_x[c.circuit])

    # No-overlap within each zone via native interval variables.
    for kind, comps in by_kind.items():
        intervals = [
            model.new_interval_var(
                x[c.id], int(c.width + GAP), x[c.id] + int(c.width + GAP), f"iv_{c.id}"
            )
            for c in comps
        ]
        model.add_no_overlap(intervals)

    model.minimize(col_x[circuits[-1]])

    solver = cp_model.CpSolver()
    start = time.perf_counter()
    status = solver.solve(model)
    elapsed = time.perf_counter() - start

    positions: dict[str, float] = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        positions = {c.id: float(solver.value(x[c.id])) for c in components}

    return positions, elapsed, solver.status_name(status)
