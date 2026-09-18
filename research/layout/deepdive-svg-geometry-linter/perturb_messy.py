"""Simulate messy auto-placed output by injecting known defects into a real
circuit, and check the linter's recall/precision against exactly what was
injected.

Round 2's task 2 asks for testing against "genuinely messy/auto-placed
output, not hand-curated examples," preferably from the `grid-astar-router`
round-2 deep dive's output if it exists yet. As of this run, the sibling
worktree `deepdive-grid-astar-router` has produced no round-2 files (its
`git status` is clean past round 1) -- so this script takes the fallback the
task specified: perturb a real circuit's positions to simulate what an
imperfect auto-layout would produce.

Rather than blind random jitter (which conflates "did the linter catch a
real defect" with "did I get lucky with the random seed"), this injects
three *known, targeted* defects into `02_dol_starter`'s otherwise-clean
geometry (see `run_real_circuits.py` -- 0 findings before perturbation) and
checks the linter's report against exactly what was injected:

1. A near-miss vertical wire (both endpoints shifted +0.3mm in x -- still
   perfectly straight, but no longer lined up with the rest of its column).
2. A crooked wire (only one endpoint shifted +0.6mm in x -- no longer
   orthogonal).
3. A wire label dragged onto a wire it doesn't belong to (text/wire
   collision).

This is the auto-router failure mode these three checks exist for: a router
that is *almost* right (off by sub-mm rounding, or a label placed without
checking what's underneath it) rather than a router that is wildly wrong.

Run with: `uv run research/layout/deepdive-svg-geometry-linter/perturb_messy.py`
"""

import dataclasses
from pathlib import Path

from linter import LintReport, lint_elements
from run_real_circuits import circuit_02_dol_starter

FINDINGS_DIR = Path(__file__).parent / "findings"
FINDINGS_DIR.mkdir(exist_ok=True)


def _shift_point(point, dx: float = 0.0, dy: float = 0.0):
    return dataclasses.replace(point, x=point.x + dx, y=point.y + dy)


def inject_defects(circuit) -> list[str]:
    """Mutate `circuit.elements` in place (via index replacement) with three
    targeted defects. Returns a description of each injected defect.

    Indices below are `02_dol_starter`'s fixed, deterministic structure (see
    the module docstring in `run_real_circuits.py::circuit_02_dol_starter`):
    elements[6:18] are the 12 top-level wire `Line`s (3 phase columns x 4
    segments), elements[18:30] are the 12 wire-label `Text`s. Verified via
    manual inspection, not guessed -- see the findings doc for the printed
    element dump this was built from.
    """
    elements = circuit.elements
    log = []

    # Defect 1: near-miss. Wire at index 7 is the x=10 column's first
    # segment (X1 -> F1, y 0->45). Shift both endpoints +0.3mm in x: still
    # perfectly vertical (won't trip check_orthogonal), but now 0.3mm off
    # from the rest of the x=10 column (wires at index 10, 13, 16, all still
    # at x=10.0 exactly).
    w = elements[7]
    elements[7] = dataclasses.replace(
        w, start=_shift_point(w.start, dx=0.3), end=_shift_point(w.end, dx=0.3)
    )
    log.append(
        "defect 1 (near-miss): wire[7] (x=10 column, X1->F1 segment) shifted "
        "+0.3mm in x -- expect near_misaligned_pins finding(s) against the "
        "rest of the x=10 column"
    )

    # Defect 2: crooked wire. Wire at index 13 is the x=10 column's third
    # segment (FT1 -> M1, y 105->145). Shift only the END point +0.6mm in x
    # -- tan(0.6/40) = 0.86 deg, over the 0.5 deg tolerance, and 0.6mm is
    # past check_near_alignment's 0.5mm tolerance so this doesn't also
    # register as a near-miss (keeps the two defect categories isolated for
    # a clean recall count).
    w = elements[13]
    elements[13] = dataclasses.replace(w, end=_shift_point(w.end, dx=0.6))
    log.append(
        "defect 2 (crooked wire): wire[13] (x=10 column, FT1->M1 segment) "
        "end shifted +0.6mm in x -- expect one non_orthogonal_wire finding"
    )

    # Defect 3: mislabeled text collision. Text at index 22 is the "BK 2.5"
    # label for the second wire segment's x=10 column (F1->Q1, drawn at
    # x=7.5 next to the wire at x=10). Drag it onto x=10.0, i.e. directly on
    # top of the wire it's labeling -- a real layout mistake (label placed
    # without offsetting it clear of the wire).
    t = elements[22]
    elements[22] = dataclasses.replace(t, position=_shift_point(t.position, dx=2.5))
    log.append(
        "defect 3 (text collision): text[22] ('BK 2.5' label) dragged onto "
        "the wire it labels -- expect one text_wire_collision finding"
    )

    return log


def main() -> None:
    circuit = circuit_02_dol_starter()

    before = lint_elements(circuit.elements)
    print(f"BEFORE perturbation: {len(before.findings)} findings (expected 0 -- see run_real_circuits.py)")

    injected = inject_defects(circuit)
    for line in injected:
        print(f"  {line}")

    after = lint_elements(circuit.elements)
    print(f"\nAFTER perturbation: {len(after.findings)} findings, cost {after.cost:.2f}")
    for kind, count in sorted(after.by_kind().items()):
        print(f"  {kind}: {count}")
    for f in after.findings:
        print(f"    [{f.severity}] {f.kind} @ {f.location}: {f.message}")

    # Recall/precision against exactly what was injected: 3 kinds of defect
    # were injected, so the report must contain at least one finding of each
    # of the 3 corresponding kinds, and must contain NO finding of the 4th
    # kind (redundant_jog_candidate) since none of the 3 injected defects
    # touch chain topology.
    kinds_found = set(after.by_kind())
    expected_kinds = {"near_misaligned_pins", "non_orthogonal_wire", "text_wire_collision"}
    missing = expected_kinds - kinds_found
    unexpected = kinds_found - expected_kinds
    print(f"\nexpected kinds all present: {not missing} (missing: {missing or 'none'})")
    print(f"unexpected kinds present: {bool(unexpected)} ({unexpected or 'none'})")

    report_text = (
        f"BEFORE: {len(before.findings)} findings\n"
        f"AFTER: {len(after.findings)} findings, cost {after.cost:.2f}\n"
        f"by_kind: {after.by_kind()}\n"
        f"injected defect kinds all detected: {not missing}\n"
        f"unexpected finding kinds (should be empty -- redundant_jog_candidate "
        f"would mean the perturbation accidentally created chain topology "
        f"noise): {unexpected or 'none'}\n"
    )
    (FINDINGS_DIR / "perturbed_messy.txt").write_text(report_text, encoding="utf-8")
    print(f"\nWrote {FINDINGS_DIR / 'perturbed_messy.txt'}")


if __name__ == "__main__":
    main()
