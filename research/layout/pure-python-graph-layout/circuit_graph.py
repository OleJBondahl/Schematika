"""Synthetic Schematika circuit used to benchmark pure-Python graph layout.

Models a classic forward/reverse contactor interlock ladder using *real*
Schematika symbol factories (fuse, no_contact, nc_contact, coil) so the
prototype exercises the actual Symbol/Port data model, not a toy stand-in.

Two rungs (A: forward, B: reverse) hang between an L1 rail and an N rail.
The fuse->contact feeds are deliberately swapped (F1 feeds S2's rung, F2
feeds S1's rung) to force at least one unavoidable edge crossing -- a
reasonable proxy for the "shared bus feeds many branches" pattern that is
common in real cabinet ladders and is exactly what a crossing-minimizing
layered layout is supposed to handle well.

Each node is a component instance placed at the origin by its factory; the
layout engines under test only ever see `node_id -> node_id` connectivity
plus a `(width, height)` size hint, exactly the interface a Sugiyama-style
layout expects. Downstream code repositions the already-built Symbol with
`schematika.core.transform.translate`, so ports move with the body.
"""

from dataclasses import dataclass

from schematika.core.geometry import Point, Vector
from schematika.core.primitives import Circle
from schematika.core.symbol import Port, Symbol
from schematika.core.transform import translate
from schematika.electrical.model.parts import standard_style
from schematika.electrical.symbols.coils import coil
from schematika.electrical.symbols.contacts import nc_contact, no_contact
from schematika.electrical.symbols.protection import fuse


def _rail_node(tag: str) -> Symbol:
    """A minimal bus-junction stand-in: a small filled dot with one port."""
    dot = Circle(Point(0, 0), 1.5, standard_style(filled=True))
    return Symbol(
        elements=[dot],
        ports={
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
        },
        label=tag,
    )


@dataclass(frozen=True)
class Node:
    """One graph node: a placed-at-origin Symbol plus its two ladder ports."""

    tag: str
    symbol: Symbol
    top_port: str
    bottom_port: str


@dataclass(frozen=True)
class CircuitGraph:
    """Nodes plus directed top-to-bottom wire edges (tag, port) -> (tag, port)."""

    nodes: dict[str, Node]
    edges: list[tuple[str, str]]


def build_interlock_ladder() -> CircuitGraph:
    """Build the forward/reverse interlock ladder described in the module docstring."""
    nodes = {
        "L1": Node("L1", _rail_node("L1"), "1", "2"),
        "N": Node("N", _rail_node("N"), "1", "2"),
        "F1": Node("F1", fuse(label="-F1", pins=("1", "2")), "1", "2"),
        "F2": Node("F2", fuse(label="-F2", pins=("1", "2")), "1", "2"),
        "S1": Node("S1", no_contact(label="-S1"), "13", "14"),
        "S2": Node("S2", no_contact(label="-S2"), "13", "14"),
        # Interlock: K2's NC aux sits in the forward rung, K1's NC aux in reverse.
        "K2_NC": Node("K2_NC", nc_contact(label="-K2"), "11", "12"),
        "K1_NC": Node("K1_NC", nc_contact(label="-K1"), "11", "12"),
        "K1": Node("K1", coil(label="-K1"), "A1", "A2"),
        "K2": Node("K2", coil(label="-K2"), "A1", "A2"),
    }

    # Deliberately crossed feeds: F1 -> S2's branch, F2 -> S1's branch.
    edges = [
        ("L1", "F1"),
        ("L1", "F2"),
        ("F1", "S2"),
        ("F2", "S1"),
        ("S1", "K2_NC"),
        ("S2", "K1_NC"),
        ("K2_NC", "K1"),
        ("K1_NC", "K2"),
        ("K1", "N"),
        ("K2", "N"),
    ]
    return CircuitGraph(nodes=nodes, edges=edges)


def node_size_mm(node: Node) -> tuple[float, float]:
    """Bounding box width/height in mm from the node's own Symbol geometry."""
    from schematika.core.renderer import calculate_bounds

    min_x, min_y, max_x, max_y = calculate_bounds(node.symbol.elements)
    return max(max_x - min_x, 10.0), max(max_y - min_y, 10.0)


def place_node(node: Node, position: Point) -> Symbol:
    """Translate *node*'s Symbol (built at the origin) so its center sits at *position*."""
    return translate(node.symbol, position.x, position.y)
