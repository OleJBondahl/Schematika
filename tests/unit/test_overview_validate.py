"""Tests for ``schematika.overview.validate``.

The validator is testable without the ``dot`` CLI: each test writes a
hand-rolled minimal SVG + sidecar fixture and asserts on the
``ValidationResult``.
"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING

import pytest

from schematika.overview.emitter import emit
from schematika.overview.model import Unit, Wire
from schematika.overview.validate import validate_svg

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _svg(
    *,
    width: str = "400pt",
    height: str = "300pt",
    edges_xml: str = "",
    nodes_xml: str = "",
    clusters_xml: str = "",
) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 400 300">\n'
        '  <g id="graph0" class="graph" transform="scale(1) translate(0,300)">\n'
        f"    {clusters_xml}\n"
        f"    {nodes_xml}\n"
        f"    {edges_xml}\n"
        "  </g>\n"
        "</svg>\n"
    )


def _node(*, title: str, points: str) -> str:
    return (
        f'<g id="node-{title}" class="node">'
        f'<a xlink:title="{title}"><polygon points="{points}"/></a>'
        "</g>"
    )


def _cluster(*, title: str, points: str) -> str:
    return (
        f'<g id="cluster-{title}" class="cluster">'
        f'<a xlink:title="{title}"><polygon points="{points}"/></a>'
        "</g>"
    )


def _edge(*, title: str, stroke: str = "#c0392b", d: str = "M0,0 L10,10") -> str:
    return (
        f'<g id="edge-{title}" class="edge">'
        f'<a xlink:title="{title}"><path stroke="{stroke}" d="{d}"/></a>'
        "</g>"
    )


def _sidecar(
    *,
    palette: dict | None = None,
    nodes: int,
    edges: int,
    clusters: int,
    containers: list[dict] | None = None,
) -> dict:
    return {
        "version": 1,
        "graphviz_version": "test",
        "schematika_version": "0.0.0",
        "palette": palette or {"power": "#c0392b", "signal": "#2980b9"},
        "counts": {"nodes": nodes, "edges": edges, "clusters": clusters},
        "containers": containers or [],
        "units": [],
        "edges": [],
    }


def _write_pair(tmp_path: Path, svg_text: str, sidecar_payload: dict) -> Path:
    svg_path = tmp_path / "system.svg"
    svg_path.write_text(svg_text, encoding="utf-8")
    sidecar = svg_path.with_suffix(svg_path.suffix + ".expected.json")
    sidecar.write_text(json.dumps(sidecar_payload), encoding="utf-8")
    return svg_path


# Two leaf nodes wholly inside a cluster polygon (0,0)..(200,200).
_HAPPY_NODES = _node(title="K1", points="20,20 60,20 60,60 20,60") + _node(
    title="X1", points="120,20 160,20 160,60 120,60"
)
_HAPPY_CLUSTER = _cluster(title="cab", points="0,0 200,0 200,200 0,200")
_HAPPY_EDGE = _edge(title="X1:1->K1:A1", stroke="#c0392b")
_HAPPY_CONTAINERS = [
    {
        "id": "cab",
        "label": "Cabinet",
        "parent": None,
        "child_units": ["K1", "X1"],
    }
]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_passes(tmp_path: Path) -> None:
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=_HAPPY_EDGE,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert result.passed
    assert result.errors == []
    tags = {line.split("]")[0] + "]" for line in result.warnings}
    assert tags == {
        "[PASS palette]",
        "[PASS node_count]",
        "[PASS edge_count]",
        "[PASS cluster_count]",
        "[PASS cluster_contains]",
        "[PASS page_size]",
    }


# ---------------------------------------------------------------------------
# Count mismatches
# ---------------------------------------------------------------------------


def test_edge_count_mismatch_fails(tmp_path: Path) -> None:
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=_HAPPY_EDGE,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=5, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert not result.passed
    fails = [e for e in result.errors if "[FAIL edge_count]" in e]
    assert len(fails) == 1
    assert "1/5" in fails[0]
    assert "missing" in fails[0]


def test_node_count_mismatch_fails(tmp_path: Path) -> None:
    only_one_node = _node(title="K1", points="20,20 60,20 60,60 20,60")
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=_HAPPY_EDGE,
            nodes_xml=only_one_node,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(
            nodes=2,
            edges=1,
            clusters=1,
            containers=[
                {
                    "id": "cab",
                    "label": "Cabinet",
                    "parent": None,
                    "child_units": ["K1"],
                }
            ],
        ),
    )
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("[FAIL node_count]" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------


def test_palette_violation_fails(tmp_path: Path) -> None:
    bad_edge = _edge(title="bad", stroke="#00ff00")
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=bad_edge,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("[FAIL palette]" in e for e in result.errors)
    assert any("#00ff00" in e for e in result.errors)


def test_palette_accepts_style_attribute(tmp_path: Path) -> None:
    """Stroke can come from ``style="stroke:..."`` not just ``stroke=`` attr."""
    styled_edge = (
        '<g class="edge"><a xlink:title="x">'
        '<path style="fill:none; stroke:#c0392b" d="M0,0 L10,10"/>'
        "</a></g>"
    )
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=styled_edge,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# Cluster containment
# ---------------------------------------------------------------------------


def test_cluster_contains_violation_fails(tmp_path: Path) -> None:
    # K1 escapes the cluster bbox (cluster goes 0..200, K1 sits at 300+).
    escaping = _node(title="K1", points="300,20 360,20 360,60 300,60") + _node(
        title="X1", points="120,20 160,20 160,60 120,60"
    )
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=_HAPPY_EDGE,
            nodes_xml=escaping,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("[FAIL cluster_contains]" in e for e in result.errors)
    assert any("K1" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Page size
# ---------------------------------------------------------------------------


def test_page_size_exceeded_fails(tmp_path: Path) -> None:
    svg_path = _write_pair(
        tmp_path,
        _svg(
            width="9000",
            height="500",
            edges_xml=_HAPPY_EDGE,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("[FAIL page_size]" in e for e in result.errors)


def test_page_size_in_pt_unit_converts_to_px(tmp_path: Path) -> None:
    # 7000pt ≈ 9333px > 8000px limit -> FAIL page_size.
    svg_path = _write_pair(
        tmp_path,
        _svg(
            width="7000pt",
            height="500pt",
            edges_xml=_HAPPY_EDGE,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("[FAIL page_size]" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Boundary errors (sidecar / parse)
# ---------------------------------------------------------------------------


def test_missing_sidecar_returns_error(tmp_path: Path) -> None:
    svg_path = tmp_path / "system.svg"
    svg_path.write_text(_svg(), encoding="utf-8")
    # No sidecar written.
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("sidecar not found" in e for e in result.errors)
    assert any(str(svg_path.name) in e for e in result.errors)


def test_malformed_svg_returns_error(tmp_path: Path) -> None:
    svg_path = tmp_path / "system.svg"
    svg_path.write_text("<svg><broken", encoding="utf-8")
    sidecar = svg_path.with_suffix(svg_path.suffix + ".expected.json")
    sidecar.write_text(
        json.dumps(_sidecar(nodes=0, edges=0, clusters=0)), encoding="utf-8"
    )
    result = validate_svg(svg_path)
    assert not result.passed
    assert any("svg parse failure" in e for e in result.errors)


def test_str_path_accepted(tmp_path: Path) -> None:
    """The public signature accepts ``str | Path``; smoke-test the str path."""
    svg_path = _write_pair(
        tmp_path,
        _svg(
            edges_xml=_HAPPY_EDGE,
            nodes_xml=_HAPPY_NODES,
            clusters_xml=_HAPPY_CLUSTER,
        ),
        _sidecar(nodes=2, edges=1, clusters=1, containers=_HAPPY_CONTAINERS),
    )
    result = validate_svg(str(svg_path))
    assert result.passed


# ---------------------------------------------------------------------------
# End-to-end integration (skipped without ``dot``)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz `dot` not on PATH")
def test_validate_against_real_dot_output_passes(tmp_path: Path) -> None:
    """Emit an SVG via real ``dot``, then validate against its sidecar."""
    units = [
        Unit(
            id="cab",
            label="Cabinet",
            parent=None,
            is_container=True,
            ports=(),
            kind="cabinet",
        ),
        Unit(
            id="K1",
            label="K1",
            parent="cab",
            is_container=False,
            ports=("A1", "A2"),
            kind="device",
        ),
        Unit(
            id="X1",
            label="X1",
            parent="cab",
            is_container=False,
            ports=("1", "2"),
            kind="terminal",
        ),
    ]
    wires = [
        Wire(from_unit="X1", from_port="1", to_unit="K1", to_port="A1", kind="power"),
    ]
    out = tmp_path / "system.svg"
    emit(units, wires, output_path=out)

    result = validate_svg(out)
    assert result.passed, result.warnings
