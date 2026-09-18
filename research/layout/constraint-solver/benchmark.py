"""Benchmark: deterministic allocator vs. z3 vs. OR-tools CP-SAT.

Run directly: `uv run python benchmark.py` from this directory (relative
imports are deliberately avoided -- see module docstrings -- so this only
works as a script, not as a package import from outside this folder).
"""

from __future__ import annotations

import time

from circuit import generate_cabinet
from deterministic_allocator import allocate
from solve_ortools import solve as solve_ortools
from solve_z3 import solve as solve_z3
from verify import verify

CABINET_SIZES = [15, 30, 50, 100]  # n_circuits; ~50/100/165/330 components


def run_one(n_circuits: int) -> None:
    components = generate_cabinet(n_circuits)
    print(f"\n=== {n_circuits} circuits -> {len(components)} components ===")

    t0 = time.perf_counter()
    positions = allocate(components)
    t1 = time.perf_counter()
    violations = verify(components, positions)
    span = max(positions.values()) if positions else 0.0
    print(
        f"  deterministic allocator: {(t1 - t0) * 1000:.3f} ms, "
        f"span={span:.0f} mm, violations={len(violations)}"
    )
    if violations:
        print(f"    {violations[:3]}")

    positions_z3, elapsed_z3, status_z3 = solve_z3(components)
    violations_z3 = verify(components, positions_z3) if positions_z3 else ["no model"]
    print(
        f"  z3:                       {elapsed_z3 * 1000:.3f} ms, "
        f"status={status_z3}, violations={len(violations_z3)}"
    )

    positions_or, elapsed_or, status_or = solve_ortools(components)
    violations_or = verify(components, positions_or) if positions_or else ["no model"]
    print(
        f"  OR-tools CP-SAT:          {elapsed_or * 1000:.3f} ms, "
        f"status={status_or}, violations={len(violations_or)}"
    )


if __name__ == "__main__":
    for n in CABINET_SIZES:
        run_one(n)
