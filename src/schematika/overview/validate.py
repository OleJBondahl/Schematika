"""Tier-1 SVG-level structural checks for the overview emitter.

The emitter writes a sidecar ``<svg>.expected.json`` derived from the
in-memory ``(units, wires)`` model. This module compares the rendered
SVG against that sidecar — checking palette, counts, cluster
containment, and page size.

Graphviz wraps every node/edge/cluster's geometry in an ``<a
xlink:title="...">`` element (because the emitter sets ``tooltip=`` on
each); the validator parses that attribute (XML namespace
``http://www.w3.org/1999/xlink``) rather than the seldom-emitted
``<title>`` text node.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from schematika.core.validation import ValidationResult

if TYPE_CHECKING:
    from collections.abc import Iterator

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"
_XLINK_TITLE = f"{{{_XLINK_NS}}}title"

# Real-world cabinets in cable view (TB layout, generous spacing) easily reach
# ~8500px wide by ~1200px tall. The check is only meant to catch runaway
# page-size regressions like "all clusters collapsed onto one node," so
# 16000px in either dimension gives ample headroom for hand-tuned spacing.
_MAX_PAGE_DIM = 16000
_CLUSTER_TOLERANCE_PX = 5.0
_PALETTE_FAIL_PREVIEW = 3

_DIM_NUMBER = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]*)\s*$")
# Approximate px-per-unit for the units Graphviz commonly emits.
_UNIT_TO_PX: dict[str, float] = {
    "": 1.0,
    "px": 1.0,
    "pt": 96.0 / 72.0,
    "in": 96.0,
    "mm": 96.0 / 25.4,
    "cm": 96.0 / 2.54,
}


@dataclass(frozen=True, slots=True)
class _Bbox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains(self, other: _Bbox, tol: float) -> bool:
        return (
            self.min_x - tol <= other.min_x
            and other.max_x <= self.max_x + tol
            and self.min_y - tol <= other.min_y
            and other.max_y <= self.max_y + tol
        )


# ---------------------------------------------------------------------------
# SVG parsing helpers
# ---------------------------------------------------------------------------


def _q(tag: str) -> str:
    return f"{{{_SVG_NS}}}{tag}"


def _xlink_title(group: ET.Element) -> str | None:
    """Return the xlink:title of the first descendant ``<a>``, or ``None``.

    Graphviz nests the ``<a>`` inside a ``<g id="a_...">`` wrapper, so a
    direct ``find(<a>)`` misses it; iterate the subtree instead.
    """
    for a in group.iter(_q("a")):
        title = a.get(_XLINK_TITLE)
        if title:
            return title
    return None


def _iter_class(root: ET.Element, class_name: str) -> Iterator[ET.Element]:
    for g in root.iter(_q("g")):
        if g.get("class") == class_name:
            yield g


_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _coord_pairs(text: str) -> list[tuple[float, float]]:
    """Collect every numeric (x, y) pair in *text* — works for ``points`` and ``d``."""
    nums = [float(t) for t in _NUM.findall(text)]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _bbox_from_points(points: list[tuple[float, float]]) -> _Bbox | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return _Bbox(min(xs), min(ys), max(xs), max(ys))


def _group_bbox(group: ET.Element) -> _Bbox | None:
    """Compute axis-aligned bbox from a group's polygon/path/polyline geometry."""
    points: list[tuple[float, float]] = []
    for elem in group.iter():
        local = elem.tag.rpartition("}")[2]
        if local in {"polygon", "polyline"}:
            pts = elem.get("points")
            if pts:
                points.extend(_coord_pairs(pts))
        elif local == "path":
            d = elem.get("d")
            if d:
                points.extend(_coord_pairs(d))
    return _bbox_from_points(points)


def _parse_dim(value: str | None) -> float | None:
    if value is None:
        return None
    match = _DIM_NUMBER.match(value)
    if match is None:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower()
    factor = _UNIT_TO_PX.get(unit)
    if factor is None:
        return None
    return number * factor


# ---------------------------------------------------------------------------
# Edge stroke extraction
# ---------------------------------------------------------------------------


_STROKE_ATTR = re.compile(r"(?:^|;)\s*stroke\s*:\s*([^;]+)", re.IGNORECASE)


def _path_stroke(group: ET.Element) -> str | None:
    """Return the first non-``none`` stroke colour found inside an edge group."""
    for path in group.iter(_q("path")):
        explicit = path.get("stroke")
        if explicit and explicit.lower() != "none":
            return explicit.strip()
        style = path.get("style")
        if style:
            match = _STROKE_ATTR.search(style)
            if match:
                value = match.group(1).strip()
                if value.lower() != "none":
                    return value
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_counts(
    root: ET.Element,
    sidecar: dict,
    findings: list[str],
) -> None:
    expected = sidecar["counts"]
    nodes = list(_iter_class(root, "node"))
    edges = list(_iter_class(root, "edge"))
    clusters = list(_iter_class(root, "cluster"))
    findings.append(_count_line("node_count", len(nodes), expected["nodes"]))
    findings.append(_count_line("edge_count", len(edges), expected["edges"]))
    findings.append(_count_line("cluster_count", len(clusters), expected["clusters"]))


def _count_line(tag: str, current: int, expected: int) -> str:
    if current == expected:
        return f"[PASS {tag}] {current}/{expected}"
    delta = expected - current
    direction = "missing" if delta > 0 else "extra"
    return f"[FAIL {tag}] {current}/{expected}   ({abs(delta)} {direction})"


def _check_palette(
    root: ET.Element,
    sidecar: dict,
    findings: list[str],
) -> None:
    allowed = {v.lower() for v in sidecar["palette"].values()}
    bad: list[tuple[str, str]] = []
    total = 0
    for edge in _iter_class(root, "edge"):
        title = _xlink_title(edge)
        if title is None:
            # Defensive — emitter always wraps edges, but skip if missing.
            continue
        total += 1
        stroke = _path_stroke(edge)
        if stroke is None:
            bad.append((title, "<no stroke>"))
            continue
        if stroke.lower() not in allowed:
            bad.append((title, stroke))
    if bad:
        details = ", ".join(f"{t}={s}" for t, s in bad[:_PALETTE_FAIL_PREVIEW])
        more = (
            ""
            if len(bad) <= _PALETTE_FAIL_PREVIEW
            else f" (+{len(bad) - _PALETTE_FAIL_PREVIEW} more)"
        )
        findings.append(
            f"[FAIL palette] {total - len(bad)}/{total} edges in palette; "
            f"violations: {details}{more}"
        )
    else:
        names = "{" + ", ".join(sorted(sidecar["palette"])) + "}"
        findings.append(f"[PASS palette] {total}/{total} edges in {names}")


def _check_cluster_containment(
    root: ET.Element,
    sidecar: dict,
    findings: list[str],
) -> None:
    clusters_by_id = {
        title: g
        for g in _iter_class(root, "cluster")
        if (title := _xlink_title(g)) is not None
    }
    nodes_by_id = {
        title: g
        for g in _iter_class(root, "node")
        if (title := _xlink_title(g)) is not None
    }
    violations: list[str] = []
    checked = 0
    for container in sidecar["containers"]:
        cluster_group = clusters_by_id.get(container["id"])
        if cluster_group is None:
            continue
        cluster_bbox = _group_bbox(cluster_group)
        if cluster_bbox is None:
            continue
        for child_id in container["child_units"]:
            node_group = nodes_by_id.get(child_id)
            if node_group is None:
                continue
            child_bbox = _group_bbox(node_group)
            if child_bbox is None:
                continue
            checked += 1
            if not cluster_bbox.contains(child_bbox, _CLUSTER_TOLERANCE_PX):
                violations.append(
                    f"unit '{child_id}' bbox extends outside cluster "
                    f"'{container['id']}' bbox"
                )
    if violations:
        first = violations[0]
        more = "" if len(violations) == 1 else f" (+{len(violations) - 1} more)"
        findings.append(f"[FAIL cluster_contains] {first}{more}")
    else:
        findings.append(
            f"[PASS cluster_contains] all {checked} "
            "child units inside their cluster bbox"
        )


def _check_page_size(root: ET.Element, findings: list[str]) -> None:
    width = _parse_dim(root.get("width"))
    height = _parse_dim(root.get("height"))
    if width is None or height is None:
        findings.append(
            "[FAIL page_size] could not parse svg width/height "
            f"(width={root.get('width')!r}, height={root.get('height')!r})"
        )
        return
    if width <= _MAX_PAGE_DIM and height <= _MAX_PAGE_DIM:
        findings.append(
            f"[PASS page_size] {int(width)} x {int(height)} "
            f"<= {_MAX_PAGE_DIM} x {_MAX_PAGE_DIM}"
        )
    else:
        findings.append(
            f"[FAIL page_size] {int(width)} x {int(height)} "
            f"exceeds {_MAX_PAGE_DIM} x {_MAX_PAGE_DIM}"
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _sidecar_path_for(svg_path: Path) -> Path:
    return svg_path.with_suffix(svg_path.suffix + ".expected.json")


def validate_svg(svg_path: str | Path) -> ValidationResult:
    """Run Tier-1 SVG-level structural checks against the emitter's sidecar.

    ``warnings`` carries the full ``[PASS ...]`` and ``[FAIL ...]`` findings
    list (used by the CLI for display); ``errors`` is the ``[FAIL ...]``
    subset. ``passed`` is ``not errors``.
    """
    svg = Path(svg_path)
    sidecar = _sidecar_path_for(svg)
    if not sidecar.exists():
        return ValidationResult(
            passed=False,
            warnings=[],
            errors=[f"sidecar not found: {sidecar}"],
        )
    try:
        sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ValidationResult(
            passed=False,
            warnings=[],
            errors=[f"sidecar parse failure: {exc}"],
        )
    try:
        tree = ET.parse(svg)  # noqa: S314 — Graphviz output, trusted local file
    except (OSError, ET.ParseError) as exc:
        return ValidationResult(
            passed=False,
            warnings=[],
            errors=[f"svg parse failure: {exc}"],
        )

    root = tree.getroot()
    findings: list[str] = []
    _check_palette(root, sidecar_payload, findings)
    _check_counts(root, sidecar_payload, findings)
    _check_cluster_containment(root, sidecar_payload, findings)
    _check_page_size(root, findings)

    errors = [f for f in findings if f.startswith("[FAIL")]
    return ValidationResult(passed=not errors, warnings=findings, errors=errors)
