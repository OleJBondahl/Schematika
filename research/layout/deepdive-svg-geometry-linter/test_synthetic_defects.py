"""Synthetic true-positive/true-negative + adversarial checks, round 2.

Extends round 1's `test_synthetic_defects.py` (still all four checks fire
on hand-built defects, still stay quiet on hand-built clean geometry) with
the cases round 2 was asked to prove:

- `test_junction_does_not_fabricate_a_chain` / `test_true_l_bend_still_caught`:
  the `_chain_wires` degree-aware rewrite. Reproduces the exact bug in round
  1's chaining heuristic (stale head/tail matched against the *entire*
  remaining list in one pass, silently welding two unrelated branches at a
  T-junction into one fictitious chain) and proves the round-2 version stops
  at the junction instead.
- `test_jog_suppressed_when_obstacle_justifies_it` /
  `test_jog_still_flagged_when_route_is_clear`: obstacle-gated
  `check_redundant_jogs`.
- `test_calibrated_width_catches_missed_collision` /
  `test_calibrated_width_clears_false_collision`: the font-metric
  calibration actually changing a verdict, not just a cosmetic number.

Run with: `uv run research/layout/deepdive-svg-geometry-linter/test_synthetic_defects.py`
"""

from linter import (
    AVG_CHAR_WIDTH_EM_OLD,
    Box,
    Pt,
    Seg,
    check_near_alignment,
    check_orthogonal,
    check_redundant_jogs,
    estimate_text_bbox,
    lint,
    lint_elements,
    lint_pid_diagram,
)


def test_crooked_wire_is_caught() -> None:
    findings = check_orthogonal([Seg(Pt(0, 0), Pt(10, 3), source="wire")])
    assert len(findings) == 1, "a 16.7 deg tilted segment should be flagged"
    assert findings[0].kind == "non_orthogonal_wire"


def test_orthogonal_wire_is_not_flagged() -> None:
    findings = check_orthogonal([Seg(Pt(0, 0), Pt(0, 10), source="wire")])
    assert findings == [], "a purely vertical segment must not be flagged"


def test_text_on_wire_is_caught() -> None:
    segments = [Seg(Pt(0, 0), Pt(0, 20), source="wire")]
    report = lint(
        segments,
        texts=[estimate_text_bbox(content="OOPS", position=Pt(0, 10), font_size=4.0, anchor="middle")],
    )
    collisions = [f for f in report.findings if f.kind == "text_wire_collision"]
    assert len(collisions) == 1, "a label centered on a wire should collide"


def test_near_misaligned_pins_are_caught() -> None:
    findings = check_near_alignment([Pt(0, 0), Pt(50, 0.2)], tolerance=0.5)
    assert len(findings) == 1, "a 0.2mm y-offset within a 0.5mm tolerance should be flagged"


def test_exactly_aligned_pins_are_not_flagged() -> None:
    findings = check_near_alignment([Pt(0, 0), Pt(50, 0.0)], tolerance=0.5)
    assert findings == [], "exactly-equal y coordinates must never be flagged"


def test_redundant_jog_is_caught_with_no_obstacles() -> None:
    # A 4-segment staircase between two points a single L-bend could join,
    # and nothing in the way -- no obstacles passed, matching round 1.
    chain = [
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
        Seg(Pt(10, 10), Pt(10, 20), source="wire"),
        Seg(Pt(10, 20), Pt(20, 20), source="wire"),
    ]
    findings = check_redundant_jogs(chain)
    assert len(findings) == 1, "a 3-turn staircase should be flagged as a jog candidate"


def test_single_l_bend_is_not_flagged() -> None:
    chain = [
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
    ]
    findings = check_redundant_jogs(chain)
    assert findings == [], "a single L-bend is the Manhattan minimum, not a defect"


# ---------------------------------------------------------------------------
# Round 2: obstacle-gated redundant-jog check.
# ---------------------------------------------------------------------------


def test_jog_suppressed_when_obstacle_justifies_it() -> None:
    """The same 3-turn staircase as above, but a symbol sits exactly where
    both Manhattan-minimum candidates (bend-first-horizontal,
    bend-first-vertical) would have to pass -- the extra turns are the
    correct way to route around it, so this must NOT be a finding."""
    chain = [
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
        Seg(Pt(10, 10), Pt(10, 20), source="wire"),
        Seg(Pt(10, 20), Pt(20, 20), source="wire"),
    ]
    # Blocks the bend-first-horizontal candidate ((0,0)->(20,0)->(20,20))
    # AND the bend-first-vertical candidate ((0,0)->(0,20)->(20,20)) --
    # both L-bend candidates between (0,0) and (20,20) pass through
    # x in [0,20], y in [0,20], so one big obstacle spanning the whole
    # candidate region proves neither is available.
    obstacle = (Box(min_x=-1, max_x=21, min_y=-1, max_y=21),)
    findings = check_redundant_jogs(chain, obstacles=obstacle)
    assert findings == [], "an obstacle blocking every simpler route must suppress the finding"


def test_jog_still_flagged_when_route_is_clear() -> None:
    """Same staircase, but the obstacle is off to the side -- it does not
    block either Manhattan-minimum candidate, so the jog is genuinely
    avoidable and must still be flagged."""
    chain = [
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
        Seg(Pt(10, 10), Pt(10, 20), source="wire"),
        Seg(Pt(10, 20), Pt(20, 20), source="wire"),
    ]
    far_away_obstacle = (Box(min_x=100, max_x=110, min_y=100, max_y=110),)
    findings = check_redundant_jogs(chain, obstacles=far_away_obstacle)
    assert len(findings) == 1, "an obstacle nowhere near the candidate routes must not suppress the finding"


# ---------------------------------------------------------------------------
# Round 2: junction-aware chaining (the fabricated-chain bug).
# ---------------------------------------------------------------------------


def test_junction_does_not_fabricate_a_chain() -> None:
    """Three segments meet at (0, 10): a vertical drop, and TWO unrelated
    horizontal branches both starting there (a bus tap -- e.g. a shared
    neutral rail feeding two different downstream devices).

    Round 1's `_chain_wires` computed `tail = chain[-1].end` once per
    `while extended` pass, then let its inner `for seg in remaining` loop
    keep matching against that *same stale tail* without ever refreshing it
    after a match -- so if two segments both touched the tail, BOTH got
    appended back-to-back into one fictitious `A -> branch_1 -> branch_2`
    chain, even though branch_1 and branch_2 both begin independently at
    the tap point and have nothing to do with each other.

    This reproduces that exact geometry. With the round-2 degree-aware
    walk, (0, 10) has degree 3 (the drop's end + both branches' starts) --
    a junction, not a pass-through -- so the chain must stop there. Each
    branch is its own 1-segment, 0-turn chain and `check_redundant_jogs`
    must find nothing to flag for either of them, and specifically must
    never see a 3-segment chain here.
    """
    drop = Seg(Pt(0, 0), Pt(0, 10), source="drop")
    branch_1 = Seg(Pt(0, 10), Pt(10, 10), source="branch_1")
    branch_2 = Seg(Pt(0, 10), Pt(-10, 10), source="branch_2")

    findings = check_redundant_jogs([drop, branch_1, branch_2])
    assert findings == [], (
        "a T-junction must never be silently chained into a fabricated "
        "multi-segment path -- each branch is independently 0-1 turns"
    )


def test_junction_false_positive_reproduced_and_fixed() -> None:
    """The concrete, demonstrable version of the bug above: a vertical
    `drop` ends at (0, 10), where two logically UNRELATED wires independently
    begin -- `tap_a` running right, `tap_b` continuing up. This is a T-tap
    (e.g. a shared rail feeding two separate downstream devices), not one
    bent wire.

    Verified directly against round 1's `research/layout/svg-geometry-linter/
    linter.py::_chain_wires`: it welds all three into one fictitious
    `drop -> tap_a -> tap_b` chain (tap_a and tap_b both matched the same
    stale `tail` in one inner-`for` pass) and reports a false
    "redundant_jog_candidate" (3 segments, 2 turns, weight 1.0) -- a
    confident-looking finding about a defect that does not exist; `drop`,
    `tap_a`, and `tap_b` are each independently 0-1 turns. The round-2
    degree-aware walk gives (0, 10) degree 3 and refuses to continue a chain
    through it, producing zero findings, as it must.
    """
    drop = Seg(Pt(0, 0), Pt(0, 10), source="drop")
    tap_a = Seg(Pt(0, 10), Pt(10, 10), source="tap_a_unrelated_wire")
    tap_b = Seg(Pt(0, 10), Pt(0, 20), source="tap_b_unrelated_wire")

    findings = check_redundant_jogs([drop, tap_a, tap_b])
    assert findings == [], (
        "round 1 reported a false 'redundant jog' (3 segments, 2 turns) for "
        "this exact T-tap by fabricating a single chain across it; the "
        "degree-aware walk must find nothing"
    )


def test_true_l_bend_still_caught_through_a_clean_join() -> None:
    """Sanity check that the degree-aware rewrite didn't break the ordinary
    case: exactly two segments meeting at a degree-2 point (no third branch)
    must still chain and still get flagged when it's a genuine 2-turn+
    staircase, same as `test_redundant_jog_is_caught_with_no_obstacles`
    but constructed via the new `_chain_wires` path explicitly (segments
    passed out of order, to prove the walk isn't order-dependent)."""
    chain_out_of_order = [
        Seg(Pt(10, 20), Pt(20, 20), source="wire"),
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(10, 10), Pt(10, 20), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
    ]
    findings = check_redundant_jogs(chain_out_of_order)
    assert len(findings) == 1, "a real 3-turn chain must still be found regardless of input order"


# ---------------------------------------------------------------------------
# Round 2: calibrated text width actually changes a verdict.
# ---------------------------------------------------------------------------


def test_calibrated_width_catches_missed_collision() -> None:
    """"WWWW" is 81.5% wider under calibrated per-glyph metrics than under
    round 1's uniform 0.52em/char guess (see calibrate_text_metrics.py's
    sample output). Place a wire just past where the OLD estimate would
    have put the label's right edge, but still inside where the REAL glyph
    metrics put it -- the old constant produces a false negative (misses a
    real collision), the calibrated version catches it."""
    font_size = 4.0
    old_half_width = len("WWWW") * AVG_CHAR_WIDTH_EM_OLD * font_size / 2  # = 4.16
    wire_x = old_half_width + 0.5  # just past the OLD estimate's right edge
    wire = [Seg(Pt(wire_x, 0), Pt(wire_x, 20), source="wire")]

    box = estimate_text_bbox(content="WWWW", position=Pt(0, 10), font_size=font_size, anchor="middle")
    assert wire_x < box.max_x, "calibrated bbox must extend past where the old constant would have"

    report = lint(wire, texts=[box])
    collisions = [f for f in report.findings if f.kind == "text_wire_collision"]
    assert len(collisions) == 1, "calibrated per-glyph width must catch this real collision"


def test_calibrated_width_clears_false_collision() -> None:
    """"IIII" is 36% narrower under calibrated metrics. Place a wire where
    the OLD uniform estimate would have (wrongly) called it a collision,
    but the real glyph metrics clear it."""
    font_size = 4.0
    old_half_width = len("IIII") * AVG_CHAR_WIDTH_EM_OLD * font_size / 2  # = 4.16
    wire_x = old_half_width - 0.5  # inside the OLD estimate, i.e. old = collision
    wire = [Seg(Pt(wire_x, 0), Pt(wire_x, 20), source="wire")]

    box = estimate_text_bbox(content="IIII", position=Pt(0, 10), font_size=font_size, anchor="middle")
    assert wire_x > box.max_x, "calibrated bbox must be narrower than where the old constant put it"

    report = lint(wire, texts=[box])
    collisions = [f for f in report.findings if f.kind == "text_wire_collision"]
    assert collisions == [], "calibrated per-glyph width must clear this false collision"


# ---------------------------------------------------------------------------
# Round 2: `lint_pid_diagram` excludes equipment-glyph lines.
#
# Minimal duck-typed stand-ins for `schematika.core.primitives.Line`/
# `core.symbol.Symbol` and a `PIDDiagram`-shaped object -- `linter.py`
# dispatches on `type(x).__name__`, not `isinstance`, specifically so this
# file never has to import `schematika` (see its module docstring), which
# means a plain same-named local class is exactly as valid an input as the
# real thing for testing that dispatch.
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _dc


@_dc
class Point:  # noqa: D101 -- test double, matches schematika.core.geometry.Point's shape
    x: float
    y: float


@_dc
class Line:  # noqa: D101 -- test double, matches schematika.core.primitives.Line's shape
    start: Point
    end: Point


@_dc
class Symbol:  # noqa: D101 -- test double, matches schematika.core.symbol.Symbol's shape
    elements: list


def test_lint_pid_diagram_excludes_equipment_glyph_lines() -> None:
    """Reproduces the real bug found against `pid_process_train`
    (`run_real_circuits.py`): a lone piece of equipment with a closed
    rectangular outline (any tank/vessel-shaped symbol) chains into a
    fictitious closed loop and trips `redundant_jog_candidate` under naive
    `lint_elements(diagram.elements)`, because `PIDBuilder.build()` flattens
    equipment `Symbol`s into `diagram.elements` (`pid/builder.py:459-465`)
    instead of preserving the `Symbol` wrapper the way `electrical` does.
    `lint_pid_diagram` must exclude every `Line` reachable from
    `diagram.equipment` and find nothing -- while a genuinely separate real
    wire elsewhere in the same diagram must still be checked normally (it
    is, trivially, since it introduces no defect on its own here)."""
    p = Point
    tank_lines = [
        Line(p(0, 0), p(10, 0)),
        Line(p(10, 0), p(10, 10)),
        Line(p(10, 10), p(0, 10)),
        Line(p(0, 10), p(0, 0)),
    ]
    tank_symbol = Symbol(elements=list(tank_lines))
    real_wire = Line(p(50, 0), p(50, 20))

    class FakeDiagram:
        equipment = [tank_symbol]
        elements = [*tank_lines, real_wire]

    naive = lint_elements(FakeDiagram.elements)
    assert any(f.kind == "redundant_jog_candidate" for f in naive.findings), (
        "sanity check: the naive path must reproduce the closed-loop false "
        "positive this test exists to fix"
    )

    fixed = lint_pid_diagram(FakeDiagram)
    assert fixed.findings == [], (
        "lint_pid_diagram must exclude the tank's own outline from the wire "
        "population; the one real wire introduces no defect on its own"
    )


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} synthetic checks passed")
