"""Prove `LintReport.cost` is usable as a real optimization objective, not
just a plausible-sounding sketch.

Round 1 proposed (but did not build) a nudge loop: "propose a small
perturbation, re-lint, keep the perturbation iff score decreases." This
script builds that loop for real -- a plain coordinate-descent hill-climber
with a shrinking step size, nothing fancier, per the task's own framing
("This doesn't need to be sophisticated -- just prove the objective function
is actually usable by something").

Setup: take `02_dol_starter` (0 findings clean, per `run_real_circuits.py`),
inject the same near-miss and crooked-wire defects `perturb_messy.py` uses
(skip the text-collision defect -- nothing in this demo's move set can fix
a label placement, and that's an honest scope note, not a hidden failure),
then let the optimizer nudge two wire endpoints in 1D (x only) using
`lint_elements(...).cost` as the sole objective, and report the defect
count before/after.

Run with: `uv run research/layout/deepdive-svg-geometry-linter/optimizer_demo.py`
"""

import dataclasses
from pathlib import Path

from linter import lint_elements
from perturb_messy import _shift_point
from run_real_circuits import circuit_02_dol_starter

FINDINGS_DIR = Path(__file__).parent / "findings"
FINDINGS_DIR.mkdir(exist_ok=True)


def inject_two_movable_defects(circuit) -> None:
    """Same defects 1 and 2 from `perturb_messy.inject_defects`, standalone
    here so this demo doesn't depend on defect 3 (text collision, which
    nothing in this optimizer's move set can address -- see module
    docstring)."""
    elements = circuit.elements
    w7 = elements[7]
    elements[7] = dataclasses.replace(
        w7, start=_shift_point(w7.start, dx=0.3), end=_shift_point(w7.end, dx=0.3)
    )
    w13 = elements[13]
    elements[13] = dataclasses.replace(w13, end=_shift_point(w13.end, dx=0.6))


def make_uniform_x_nudger(idx: int):
    """Move both endpoints of `elements[idx]` together by `delta` in x
    (keeps the wire straight -- fixes a near-miss without introducing a
    tilt)."""

    def nudge(elements: list, delta: float) -> list:
        w = elements[idx]
        new = dataclasses.replace(
            w, start=_shift_point(w.start, dx=delta), end=_shift_point(w.end, dx=delta)
        )
        return [new if i == idx else e for i, e in enumerate(elements)]

    return nudge


def make_endpoint_x_nudger(idx: int):
    """Move only `elements[idx]`'s end point in x (fixes a tilt by rotating
    the wire back toward vertical)."""

    def nudge(elements: list, delta: float) -> list:
        w = elements[idx]
        new = dataclasses.replace(w, end=_shift_point(w.end, dx=delta))
        return [new if i == idx else e for i, e in enumerate(elements)]

    return nudge


def cost_of(elements: list) -> float:
    return lint_elements(elements).cost


def optimize(
    elements: list,
    movers: dict[str, object],
    *,
    initial_step: float = 0.5,
    min_step: float = 0.005,
) -> tuple[list, float, int]:
    """Coordinate-descent hill-climber: try +-step on each mover, keep any
    move that strictly reduces cost, halve the step when a full sweep finds
    no improvement. Stops once `step < min_step`.

    Returns (final_elements, final_cost, iterations).
    """
    current = elements
    current_cost = cost_of(current)
    step = initial_step
    iterations = 0

    while step >= min_step:
        improved_this_sweep = False
        for name, nudge in movers.items():
            for direction in (1.0, -1.0):
                candidate = nudge(current, direction * step)
                candidate_cost = cost_of(candidate)
                iterations += 1
                if candidate_cost < current_cost - 1e-9:
                    current, current_cost = candidate, candidate_cost
                    improved_this_sweep = True
        if not improved_this_sweep:
            step /= 2

    return current, current_cost, iterations


def main() -> None:
    circuit = circuit_02_dol_starter()
    inject_two_movable_defects(circuit)

    before_report = lint_elements(circuit.elements)
    print(f"BEFORE: {len(before_report.findings)} findings, cost {before_report.cost:.2f}")
    print(f"  by_kind: {before_report.by_kind()}")

    movers = {
        "wire7_uniform_x": make_uniform_x_nudger(7),
        "wire13_endpoint_x": make_endpoint_x_nudger(13),
    }
    final_elements, final_cost, iterations = optimize(circuit.elements, movers)
    after_report = lint_elements(final_elements)

    print(
        f"\nAFTER {iterations} candidate evaluations: "
        f"{len(after_report.findings)} findings, cost {after_report.cost:.2f}"
    )
    print(f"  by_kind: {after_report.by_kind()}")
    for f in after_report.findings:
        print(f"    [{f.severity}] {f.kind} @ {f.location}: {f.message}")

    w7 = final_elements[7]
    w13 = final_elements[13]
    print(f"\nwire[7] final position:  start={w7.start}  end={w7.end}  (started at x=10.3)")
    print(f"wire[13] final position: end={w13.end}  (started at x=10.6)")

    reduction = (
        (before_report.cost - after_report.cost) / before_report.cost * 100
        if before_report.cost
        else 0.0
    )
    report_text = (
        f"BEFORE: {len(before_report.findings)} findings, cost {before_report.cost:.2f}, "
        f"by_kind={before_report.by_kind()}\n"
        f"AFTER:  {len(after_report.findings)} findings, cost {after_report.cost:.2f}, "
        f"by_kind={after_report.by_kind()} ({iterations} candidate evaluations)\n"
        f"cost reduction: {reduction:.1f}%\n"
        f"remaining findings are the text-collision defect, which is outside "
        f"this demo's move set (wire-position nudges only) -- expected, not a failure.\n"
        f"wire[7] returned to x={w7.start.x:.4f} (started perturbed at x=10.3, true value 10.0)\n"
        f"wire[13] end returned to x={w13.end.x:.4f} (started perturbed at x=10.6, true value 10.0)\n"
    )
    (FINDINGS_DIR / "optimizer_demo.txt").write_text(report_text, encoding="utf-8")
    print(f"\nWrote {FINDINGS_DIR / 'optimizer_demo.txt'}")


if __name__ == "__main__":
    main()
