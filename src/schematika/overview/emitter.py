"""Render ``(units, wires)`` to SVG via ``dot -Tsvg``.

Builds DOT with plain string templating (no graphviz Python dep — keeps
the core dependency footprint at zero) and shells out to the system
``dot`` binary. Always uses plain ``-Tsvg``: the Cairo SVG exporter
rearranges the class hierarchy and breaks downstream parsing
(``docs/overview-module/04-graphviz-reference.md`` pitfall #14).

Three artifacts are written next to ``output_path``:

- ``<output_path>``               — the SVG diagram.
- ``<output_path>.dot``           — raw DOT source, useful for debugging.
- ``<output_path>.expected.json`` — sidecar consumed by the validator.

Sidecar counts are derived from the in-memory ``(units, wires)`` model,
not re-parsed from the SVG, so the validator's check cannot be
tautological.
"""

from __future__ import annotations

import json
import re
import subprocess
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from schematika.overview.errors import OverviewRenderError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from schematika.overview.model import Unit, Wire


_DEFAULT_PALETTE: Mapping[str, str] = {
    "power": "#c0392b",
    "signal": "#2980b9",
}

# DOT identifiers must be either an [A-Za-z_][A-Za-z_0-9]* word, a number,
# or a quoted string. We also explicitly quote DOT keywords.
_DOT_KEYWORDS = frozenset({"node", "edge", "graph", "digraph", "subgraph", "strict"})
_DOT_BARE_ID = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")
_STDERR_TRUNCATE = 4096


# ---------------------------------------------------------------------------
# Quoting / escaping helpers
# ---------------------------------------------------------------------------


def _quote_dot_id(value: str) -> str:
    r"""Quote ``value`` for use as a DOT node id, port id, or attribute string.

    Bare identifiers matching ``[A-Za-z_][A-Za-z_0-9]*`` and not colliding
    with DOT keywords pass through unquoted; anything else is wrapped in
    double quotes with ``\`` and ``"`` escaped.
    """
    if value and value not in _DOT_KEYWORDS and _DOT_BARE_ID.match(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _html_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# DOT rendering
# ---------------------------------------------------------------------------


def _render_unit_table(unit: Unit) -> str:
    """Return the DOT ``label=<<TABLE>...>`` HTML string for a non-container unit."""
    rows = [
        '    <TR><TD COLSPAN="1" BGCOLOR="lightgrey"><B>'
        f"{_html_escape(unit.label)}</B></TD></TR>"
    ]
    rows.extend(
        f'    <TR><TD PORT="{_html_escape(port)}" ALIGN="LEFT">'
        f"{_html_escape(port)}</TD></TR>"
        for port in unit.ports
    )
    body = "\n".join(rows)
    return (
        "<\n"
        '  <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">\n'
        f"{body}\n"
        "  </TABLE>>"
    )


def _render_node(unit: Unit, indent: str) -> str:
    """Render as a labeled box. With ports → HTML table; portless → plain rectangle."""
    if unit.ports:
        label = _render_unit_table(unit)
        shape = "plaintext"
    else:
        label = _quote_dot_id(unit.label)
        shape = "box"
    return (
        f"{indent}{_quote_dot_id(unit.id)} ["
        f"shape={shape}, style=filled, fillcolor=white, "
        f"tooltip={_quote_dot_id(unit.id)}, label={label}];"
    )


def _render_cluster(
    container: Unit,
    children: list[Unit],
    nested_clusters: list[str],
) -> str:
    indent = "    "
    inner = [
        f"{indent}label={_quote_dot_id(container.label)};",
        f"{indent}tooltip={_quote_dot_id(container.id)};",
        f'{indent}style="rounded,filled";',
        f'{indent}fillcolor="#f5f5f5";',
        f"{indent}cluster=true;",
    ]
    inner.extend(_render_node(child, indent) for child in children)
    inner.extend(nested_clusters)
    body = "\n".join(inner)
    return f"  subgraph {_quote_dot_id(f'cluster_{container.id}')} {{\n{body}\n  }}"


def _children_by_parent(units: list[Unit]) -> dict[str | None, list[Unit]]:
    grouped: dict[str | None, list[Unit]] = {}
    for unit in units:
        grouped.setdefault(unit.parent, []).append(unit)
    return grouped


def _render_subgraph(
    container_id: str,
    children_by_parent: Mapping[str | None, list[Unit]],
    units_by_id: Mapping[str, Unit],
) -> str:
    container = units_by_id[container_id]
    children = children_by_parent.get(container_id, [])
    leaf_children = [u for u in children if not u.is_container]
    nested_ids = [u.id for u in children if u.is_container]
    nested_blocks = [
        _render_subgraph(nid, children_by_parent, units_by_id) for nid in nested_ids
    ]
    return _render_cluster(container, leaf_children, nested_blocks)


def _render_edges(wires: list[Wire], palette: Mapping[str, str]) -> list[str]:
    lines: list[str] = []
    for wire in wires:
        color = palette.get(wire.kind, "#444444")
        endpoint_from = _wire_endpoint(wire.from_unit, wire.from_port, "e")
        endpoint_to = _wire_endpoint(wire.to_unit, wire.to_port, "w")
        title = (
            f"{wire.from_unit}:{wire.from_port}->{wire.to_unit}:{wire.to_port}"
            if wire.from_port or wire.to_port
            else f"{wire.from_unit} -> {wire.to_unit} ({wire.kind})"
        )
        lines.append(
            f"  {endpoint_from} -> {endpoint_to} ["
            f'color="{color}", penwidth=2.0, '
            f"tooltip={_quote_dot_id(title)}];"
        )
    return lines


def _wire_endpoint(unit_id: str, port: str, compass: str) -> str:
    """``unit:port:compass`` when port is set, else just ``unit`` (cable view)."""
    if port:
        return f"{_quote_dot_id(unit_id)}:{_quote_dot_id(port)}:{compass}"
    return _quote_dot_id(unit_id)


def _build_dot(
    units: list[Unit],
    wires: list[Wire],
    palette: Mapping[str, str],
) -> str:
    """Return the full DOT source for ``(units, wires)``."""
    units_by_id = {u.id: u for u in units}
    children_by_parent = _children_by_parent(units)

    header = [
        "digraph system {",
        '  graph [compound=true, splines="ortho", rankdir="TB", '
        'newrank=true, nodesep=0.4, ranksep=10.0, fontname="Helvetica"];',
        '  node  [shape=plaintext, fontname="Helvetica"];',
        '  edge  [fontname="Helvetica", arrowhead="none"];',
    ]

    body: list[str] = []
    for unit in children_by_parent.get(None, []):
        if unit.is_container:
            body.append(_render_subgraph(unit.id, children_by_parent, units_by_id))
        else:
            body.append(_render_node(unit, "  "))

    body.extend(_render_edges(wires, palette))

    return "\n".join([*header, *body, "}", ""])


# ---------------------------------------------------------------------------
# Sidecar
# ---------------------------------------------------------------------------


def _get_graphviz_version() -> str:
    """Return ``dot -V`` output (stripped). Empty string if dot is missing."""
    try:
        completed = subprocess.run(
            ["dot", "-V"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    return (completed.stderr or completed.stdout).strip()


def _schematika_version() -> str:
    try:
        return metadata.version("schematika")
    except metadata.PackageNotFoundError:
        return "0.0.0+unknown"


def _has_descendants(
    container_id: str,
    children_by_parent: Mapping[str | None, list[Unit]],
) -> bool:
    """True if any leaf unit transitively descends from ``container_id``.

    Empty containers are dropped from the rendered cluster count because
    Graphviz silently elides ``subgraph cluster_X { }`` blocks with no
    nodes — the sidecar must agree or the validator FAILs cluster_count.
    """
    for child in children_by_parent.get(container_id, []):
        if not child.is_container:
            return True
        if _has_descendants(child.id, children_by_parent):
            return True
    return False


def _sidecar_payload(
    units: list[Unit],
    wires: list[Wire],
    palette: Mapping[str, str],
) -> dict:
    children_by_parent = _children_by_parent(units)

    containers = [
        {
            "id": u.id,
            "label": u.label,
            "parent": u.parent,
            "child_units": [c.id for c in children_by_parent.get(u.id, [])],
        }
        for u in units
        if u.is_container
    ]
    rendered_clusters = sum(
        1
        for u in units
        if u.is_container and _has_descendants(u.id, children_by_parent)
    )
    leaf_units = [
        {
            "id": u.id,
            "container": u.parent,
            "ports": list(u.ports),
        }
        for u in units
        if not u.is_container
    ]
    edge_records = [
        {
            "src": w.from_unit,
            "src_port": w.from_port,
            "dst": w.to_unit,
            "dst_port": w.to_port,
            "kind": w.kind,
            "color": palette.get(w.kind, "#444444"),
        }
        for w in wires
    ]
    return {
        "version": 1,
        "graphviz_version": _get_graphviz_version(),
        "schematika_version": _schematika_version(),
        "palette": dict(palette),
        "counts": {
            "nodes": len(leaf_units),
            "edges": len(wires),
            "clusters": rendered_clusters,
        },
        "containers": containers,
        "units": leaf_units,
        "edges": edge_records,
    }


def _write_sidecar(payload: dict, output_path: Path) -> None:
    sidecar_path = output_path.with_suffix(output_path.suffix + ".expected.json")
    sidecar_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Render via `dot`
# ---------------------------------------------------------------------------


def _run_dot(dot_text: str, output_path: Path) -> None:
    try:
        completed = subprocess.run(  # noqa: S603
            ["dot", "-Tsvg", "-o", str(output_path)],  # noqa: S607
            input=dot_text.encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = "Graphviz `dot` CLI not found on PATH"
        raise OverviewRenderError(msg) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        msg = (
            f"`dot -Tsvg` exited {completed.returncode}. "
            f"stderr: {stderr[:_STDERR_TRUNCATE]}"
        )
        raise OverviewRenderError(msg)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def emit(
    units: list[Unit],
    wires: list[Wire],
    *,
    output_path: str | Path,
    palette: Mapping[str, str] | None = None,
) -> None:
    """Render to SVG, plus ``.dot`` source and ``.expected.json`` sidecar."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    effective_palette = palette if palette is not None else _DEFAULT_PALETTE
    dot_text = _build_dot(units, wires, effective_palette)

    out.with_suffix(out.suffix + ".dot").write_text(dot_text, encoding="utf-8")
    _run_dot(dot_text, out)
    _write_sidecar(_sidecar_payload(units, wires, effective_palette), out)
