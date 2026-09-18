"""Shared correctness checker for all three placement approaches.

Every approach (deterministic allocator, z3, OR-tools CP-SAT) produces the
same output shape: `{component_id: x_position}`. This module checks that
output against the three rules from the spike question, independent of how
the positions were produced.
"""

from __future__ import annotations

from circuit import GAP, ZONE_Y, Component


def verify(components: list[Component], x: dict[str, float]) -> list[str]:
    """Check zone pinning, no-overlap, and column ordering.

    Args:
        components: The synthetic cabinet.
        x: X position (mm) assigned to each component id.

    Returns:
        List of human-readable violation strings; empty means all three
        hard-constraint families hold.
    """
    violations: list[str] = []
    by_kind: dict[str, list[Component]] = {}
    for c in components:
        by_kind.setdefault(c.kind, []).append(c)

    # 1. No-overlap within each zone (same Y band -> compare X intervals).
    for kind, comps in by_kind.items():
        ordered = sorted(comps, key=lambda c: x[c.id])
        for a, b in zip(ordered, ordered[1:]):
            if x[a.id] + a.width + GAP > x[b.id] + 1e-6:
                violations.append(
                    f"overlap in zone {kind}: {a.id}[{x[a.id]:.1f}"
                    f"+{a.width:.1f}] vs {b.id}[{x[b.id]:.1f}]"
                )

    # 2. Column ordering: every component in circuit c shares one column X,
    #    and column X is strictly increasing in circuit index.
    by_circuit: dict[int, list[Component]] = {}
    for c in components:
        by_circuit.setdefault(c.circuit, []).append(c)

    col_x: dict[int, float] = {}
    for circuit, comps in by_circuit.items():
        xs = {round(x[c.id], 6) for c in comps}
        if len(xs) > 1:
            violations.append(
                f"circuit {circuit} components not column-aligned: {xs}"
            )
        col_x[circuit] = x[comps[0].id]

    for a, b in zip(sorted(col_x), sorted(col_x)[1:]):
        if col_x[a] >= col_x[b]:
            violations.append(
                f"column order violated: circuit {a} (x={col_x[a]:.1f}) "
                f"not left of circuit {b} (x={col_x[b]:.1f})"
            )

    # 3. Zone pinning is an invariant of construction (Y = ZONE_Y[kind]), so
    #    there's nothing to check on distinct data here beyond kind coverage.
    for c in components:
        if c.kind not in ZONE_Y:
            violations.append(f"unknown zone kind for {c.id}: {c.kind}")

    return violations
