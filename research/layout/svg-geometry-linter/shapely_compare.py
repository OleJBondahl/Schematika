"""Shapely-vs-stdlib comparison for the geometry linter's checks.

PEP 723 inline script -- run standalone with `uv run --script`, which
resolves `shapely` into an ephemeral env WITHOUT touching this repo's
`pyproject.toml`. Confirms shapely can do the same checks (it can -- this is
a solved problem for that library) and measures how much code it actually
saves over the stdlib versions in `linter.py`.

Run with:
    uv run --script research/layout/svg-geometry-linter/shapely_compare.py
"""

# /// script
# requires-python = ">=3.14"
# dependencies = ["shapely==2.1.2"]
# ///

from shapely.affinity import rotate
from shapely.geometry import LineString, box

# ---------------------------------------------------------------------------
# check_orthogonal, shapely version.
#
# Same line count as the stdlib version (`linter.py::check_orthogonal`,
# ~15 lines): shapely has no "angle of a LineString" primitive, so this is
# still hand-rolled atan2 either way. Shapely buys nothing here.
# ---------------------------------------------------------------------------


def is_orthogonal(line: LineString, tol_deg: float = 0.5) -> bool:
    (x0, y0), (x1, y1) = line.coords
    import math

    angle = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 90
    return min(angle, 90 - angle) <= tol_deg


# ---------------------------------------------------------------------------
# check_text_wire_collisions, shapely version.
#
# This is the one check shapely genuinely simplifies: `_segment_intersects_rect`
# in `linter.py` is a ~35-line hand-rolled Cohen-Sutherland clipper. Shapely
# replaces it with one call, and it generalizes for free to non-rectangular
# text boxes (rotated boxes as polygons, not just rotated axis-aligned
# corners) and to non-Line geometry (Polygon-vs-Polygon overlap for
# eventual symbol-body collisions, arcs via `.buffer()`, etc).
# ---------------------------------------------------------------------------


def rotated_text_box(cx: float, cy: float, w: float, h: float, rotation_deg: float):
    """Build a text bbox as a Shapely polygon, pre-rotated -- no manual
    corner-rotation math, unlike `linter.py::estimate_text_bbox`.

    Box is centered on (cx, cy) on both axes, matching the real wire labels'
    `dominant-baseline="middle"` -- see the findings doc for why the
    asymmetric ("auto" baseline) case matters less here."""
    unrotated = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return rotate(unrotated, rotation_deg, origin=(cx, cy))


def collides(line: LineString, text_box) -> bool:
    return line.intersects(text_box)  # one call vs. the ~35-line clipper


def main() -> None:
    # 1. Orthogonality: no simpler with shapely.
    crooked = LineString([(0, 0), (10, 3)])
    straight = LineString([(0, 0), (0, 10)])
    print(f"crooked orthogonal? {is_orthogonal(crooked)} (expect False)")
    print(f"straight orthogonal? {is_orthogonal(straight)} (expect True)")

    # 2. Text/wire collision: rotated-box intersection in one line.
    wire = LineString([(0, 0), (0, 20)])
    label_far = rotated_text_box(cx=-2.5, cy=10, w=10.9, h=2.5, rotation_deg=90)
    label_on_wire = rotated_text_box(cx=0, cy=10, w=10.9, h=2.5, rotation_deg=0)
    print(f"offset rotated label collides with wire? {collides(wire, label_far)} (expect False)")
    print(f"on-wire label collides with wire? {collides(wire, label_on_wire)} (expect True)")


if __name__ == "__main__":
    main()
