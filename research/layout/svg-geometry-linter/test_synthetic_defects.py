"""Synthetic true-positive/true-negative check for the linter prototype.

The real-circuit run (`run_model_linter.py`) came back clean (0 findings) on
both example circuits once the symbol-glyph and text-rotation false
positives were fixed. A linter that never fires could be silently broken
rather than genuinely passing, so this script feeds it hand-built defects of
all four kinds and confirms each one is actually caught -- and confirms a
clean hand-built circuit stays clean.

Run with: `uv run research/layout/svg-geometry-linter/test_synthetic_defects.py`
"""

from linter import (
    Pt,
    Seg,
    check_near_alignment,
    check_orthogonal,
    check_redundant_jogs,
    estimate_text_bbox,
    lint,
)


def test_crooked_wire_is_caught() -> None:
    findings = check_orthogonal([Seg(Pt(0, 0), Pt(10, 3), source="wire")])
    assert len(findings) == 1, "a 16.7 deg tilted segment should be flagged"
    assert findings[0].kind == "non_orthogonal_wire"


def test_orthogonal_wire_is_not_flagged() -> None:
    findings = check_orthogonal([Seg(Pt(0, 0), Pt(0, 10), source="wire")])
    assert findings == [], "a purely vertical segment must not be flagged"


def test_text_on_wire_is_caught() -> None:
    # A horizontal (unrotated) label planted directly on top of a vertical
    # wire -- the collision this check exists to catch, as opposed to the
    # rotated wire-label case that turned out to be a false positive.
    segments = [Seg(Pt(0, 0), Pt(0, 20), source="wire")]
    report = lint(
        segments,
        texts=[estimate_text_bbox(content="OOPS", position=Pt(0, 10), font_size=4.0, anchor="middle")],
    )
    collisions = [f for f in report.findings if f.kind == "text_wire_collision"]
    assert len(collisions) == 1, "a label centered on a wire should collide"


def test_near_misaligned_pins_are_caught() -> None:
    # Two pins 0.2mm off exact horizontal alignment -- "looks aligned," isn't.
    findings = check_near_alignment([Pt(0, 0), Pt(50, 0.2)], tolerance=0.5)
    assert len(findings) == 1, "a 0.2mm y-offset within a 0.5mm tolerance should be flagged"


def test_exactly_aligned_pins_are_not_flagged() -> None:
    findings = check_near_alignment([Pt(0, 0), Pt(50, 0.0)], tolerance=0.5)
    assert findings == [], "exactly-equal y coordinates must never be flagged"


def test_redundant_jog_is_caught() -> None:
    # A 4-segment staircase between two points a single L-bend could join.
    chain = [
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
        Seg(Pt(10, 10), Pt(10, 20), source="wire"),
        Seg(Pt(10, 20), Pt(20, 20), source="wire"),
    ]
    findings = check_redundant_jogs(chain)
    assert len(findings) == 1, "a 3-turn staircase should be flagged as a jog candidate"


def test_single_l_bend_is_not_flagged() -> None:
    # The Manhattan-minimum case: one turn joining two points -- not a jog.
    chain = [
        Seg(Pt(0, 0), Pt(0, 10), source="wire"),
        Seg(Pt(0, 10), Pt(10, 10), source="wire"),
    ]
    findings = check_redundant_jogs(chain)
    assert findings == [], "a single L-bend is the Manhattan minimum, not a defect"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} synthetic checks passed")
