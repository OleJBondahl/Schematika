"""Connectivity graph and terminal trace analysis for electrical circuits.

Provides ``build_connectivity_graph``, ``trace_connection``, and
``export_terminals_to_csv`` — tools for analysing which symbols and terminals
are electrically connected. Imports from ``electrical/model/``.
"""

import csv
from dataclasses import dataclass
from typing import Final

from schematika.electrical.model.core import Element, Point, Symbol, Vector
from schematika.electrical.model.primitives import Line
from schematika.electrical.symbols.terminals import TerminalBlock, TerminalSymbol

# Tolerance for connection (should match layout.py)
TOLERANCE = 0.1
# Minimum positive dot product to consider a wire going "out" in a direction.
_DIRECTION_DOT_THRESHOLD: Final = 0.001


def _point_key(p: Point) -> tuple[float, float]:
    # Round to 1 decimal place to match tolerance
    return (round(p.x, 1), round(p.y, 1))


@dataclass
class ConnectionNode:
    """A graph node representing a geometric point with its connected lines and ports."""

    point: Point
    connected_lines: list[Line]
    connected_ports: list[tuple[Symbol, str]]  # Symbol, PortID


def build_connectivity_graph(
    elements: list[Element],
) -> dict[tuple[float, float], ConnectionNode]:
    """Build a connectivity graph mapping grid points to ``ConnectionNode`` objects.

    Lines and symbol ports are indexed by their endpoint coordinates.
    """
    nodes: dict[tuple[float, float], ConnectionNode] = {}

    def get_node(p: Point) -> ConnectionNode:
        k = _point_key(p)
        if k not in nodes:
            nodes[k] = ConnectionNode(p, [], [])
        return nodes[k]

    for el in elements:
        if isinstance(el, Line):
            n1 = get_node(el.start)
            n2 = get_node(el.end)
            n1.connected_lines.append(el)
            n2.connected_lines.append(el)
        elif isinstance(el, Symbol):
            for pid, port in el.ports.items():
                node = get_node(port.position)
                node.connected_ports.append((el, pid))

    return nodes


def _find_connected_symbol(
    node: ConnectionNode, start_symbol: Symbol
) -> tuple[Symbol, str] | None:
    """Check if this node has ports from other symbols."""
    for sym, pid in node.connected_ports:
        if sym != start_symbol:
            return sym, pid
    return None


def _is_valid_direction(
    p_node: Point, p_other: Point, direction_filter: Vector | None
) -> bool:
    """Check if the line direction matches the filter."""
    if not direction_filter:
        return True

    dx = p_other.x - p_node.x
    dy = p_other.y - p_node.y
    # Dot product
    dot = dx * direction_filter.dx + dy * direction_filter.dy
    # If dot product is <= 0 (orthogonal or opposite), skip
    # We want lines going "out" in the direction of the port
    return dot > _DIRECTION_DOT_THRESHOLD


def trace_connection(
    node: ConnectionNode,
    graph: dict[tuple[float, float], ConnectionNode],
    visited_lines: set[int],
    start_symbol: Symbol,
    direction_filter: Vector | None = None,
) -> tuple[Symbol | None, str | None]:
    """Trace a wire connection from *node* to the first symbol other than *start_symbol*.

    Traverses the connectivity graph following unvisited lines, optionally
    filtering by *direction_filter*. Returns the connected symbol and port ID, or
    ``(None, None)`` if no connection is found.
    """
    # Check if this node has ports from other symbols
    found_symbol = _find_connected_symbol(node, start_symbol)
    if found_symbol:
        return found_symbol

    # Traverse lines
    for line in node.connected_lines:
        if id(line) in visited_lines:
            continue

        p_node = node.point
        p_other = (
            line.end if _point_key(line.start) == _point_key(p_node) else line.start
        )

        if not _is_valid_direction(p_node, p_other, direction_filter):
            continue

        visited_lines.add(id(line))
        next_node_key = _point_key(p_other)

        if next_node_key in graph:
            # Recursive call - clear direction filter for subsequent steps
            res = trace_connection(
                graph[next_node_key], graph, visited_lines, start_symbol, None
            )
            if res[0]:
                return res

    return None, None


def _get_terminal_channels(term: Element) -> list[dict[str, str]]:
    """Extract channels (pin, from_port, to_port) from a terminal element."""
    channels = []
    if isinstance(term, TerminalSymbol):
        channels.append(
            {"pin": term.terminal_number or "", "from_port": "1", "to_port": "2"}
        )
    elif isinstance(term, TerminalBlock):
        # Derive channels from port pairs (odd=in, even=out)
        port_ids = sorted(
            term.ports.keys(), key=lambda k: (k.isdigit(), int(k) if k.isdigit() else 0)
        )
        numeric_ids = [p for p in port_ids if p.isdigit()]
        for i in range(0, len(numeric_ids) - 1, 2):
            in_id = numeric_ids[i]
            out_id = numeric_ids[i + 1]
            channels.append({"pin": "", "from_port": in_id, "to_port": out_id})
    return channels


def _trace_port_connection(
    term: Symbol, port_id: str, graph: dict[tuple[float, float], ConnectionNode]
) -> tuple[str, str]:
    """Trace a connection from a specific port of a terminal."""
    if port_id not in term.ports:
        return "", ""

    port = term.ports[port_id]
    node = graph.get(_point_key(port.position))

    if node:
        comp, pin = trace_connection(node, graph, set(), term, port.direction)
        return (comp.label if comp and comp.label else "", pin if pin else "")

    return "", ""


def _create_terminal_row(
    term: Symbol, channel: dict[str, str], graph: dict
) -> list[str]:
    """Create a CSV row for a single terminal channel."""
    comp_from, pin_from = _trace_port_connection(term, channel["from_port"], graph)
    comp_to, pin_to = _trace_port_connection(term, channel["to_port"], graph)

    return [
        comp_from,
        pin_from,
        term.label if term.label else "",
        channel["pin"],
        comp_to,
        pin_to,
    ]


def export_terminals_to_csv(elements: list[Element], filename: str):
    """Export all terminals in the system to a CSV file.

    Format:
    component from, pin from, terminal tag, terminal pin, component to, pin to

    From side is typically the TOP port (Input).
    To side is typically the BOTTOM port (Output).
    """
    graph = build_connectivity_graph(elements)

    terminals = [e for e in elements if isinstance(e, (TerminalSymbol, TerminalBlock))]
    terminals.sort(key=lambda t: t.label if t.label else "")

    rows = [
        _create_terminal_row(term, ch, graph)
        for term in terminals
        for ch in _get_terminal_channels(term)
    ]

    # Write CSV
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Component From",
                "Pin From",
                "Terminal Tag",
                "Terminal Pin",
                "Component To",
                "Pin To",
            ]
        )
        writer.writerows(rows)


def export_components_to_csv(elements: list[Element], filename: str):
    """Export all components in the system to a CSV file.

    Format:
    Component Tag, Component Description, MPN

    For now, only Component Tag is populated.
    Description and MPN are empty placeholders for future enhancement
    (to be populated by merging with project-specific data).

    Args:
        elements: List of all elements in the system
        filename: Path to the output CSV file
    """
    # Collect all symbols with labels (components)
    components = []
    seen_tags = set()

    for el in elements:
        if isinstance(el, Symbol) and el.label:
            # Only add unique component tags
            if el.label not in seen_tags:
                components.append(
                    {
                        "tag": el.label,
                        "description": "",  # Placeholder for future population
                        "mpn": "",  # Placeholder for future population
                    }
                )
                seen_tags.add(el.label)

    # Sort components by tag for consistent output
    components.sort(key=lambda c: c["tag"])

    # Write CSV
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Component Tag", "Component Description", "MPN"])
        for comp in components:
            writer.writerow([comp["tag"], comp["description"], comp["mpn"]])
