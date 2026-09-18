"""Lay out the same ladder with NetworkX's `multipartite_layout`, for contrast.

NetworkX has no dedicated Sugiyama/layered-DAG algorithm. The closest built-in
recipe is: bucket nodes into generations with `topological_generations`, tag
each node with its generation as the `subset` key, then call
`multipartite_layout`. That function places nodes in *insertion order* within
each layer -- it does not attempt to minimize edge crossings at all. Compared
against `run_grandalf_layout.py` on the identical graph, this makes the
"crossing minimization is not free -- Sugiyama-style layer-order optimization
is a distinct algorithm NetworkX does not ship" gap concrete rather than
asserted.
"""

import networkx as nx

from circuit_graph import build_interlock_ladder, node_size_mm, place_node
from schematika.core.geometry import Point
from schematika.core.geometry import Style as CoreStyle
from schematika.core.primitives import Line
from schematika.rendering.svg import render_to_svg

_LAYER_HEIGHT_MM = 55.0
_COLUMN_WIDTH_MM = 90.0


def run() -> None:
    """Build the ladder, lay it out with plain NetworkX generations, render."""
    circuit = build_interlock_ladder()

    graph = nx.DiGraph()
    graph.add_nodes_from(circuit.nodes)
    graph.add_edges_from(circuit.edges)

    for generation, layer_nodes in enumerate(nx.topological_generations(graph)):
        for tag in layer_nodes:
            graph.nodes[tag]["subset"] = generation

    # align="horizontal" -> generation controls y, insertion order controls x.
    raw_positions = nx.multipartite_layout(graph, subset_key="subset", align="horizontal")

    positions: dict[str, Point] = {}
    for tag, (nx_x, nx_y) in raw_positions.items():
        # networkx returns floats roughly in [-1, 1]; flip y so generation 0 is
        # at the top (multipartite_layout puts generation 0 at the bottom).
        positions[tag] = Point(nx_x * _COLUMN_WIDTH_MM * 2, -nx_y * _LAYER_HEIGHT_MM * 4)

    print("networkx multipartite_layout positions (mm-scaled):")
    for tag in circuit.nodes:
        p = positions[tag]
        print(f"  {tag:8s} -> ({p.x:7.1f}, {p.y:7.1f})")

    elements = []
    placed_ports: dict[str, dict[str, Point]] = {}
    for tag, node in circuit.nodes.items():
        placed = place_node(node, positions[tag])
        elements.append(placed)
        placed_ports[tag] = {pid: port.position for pid, port in placed.ports.items()}
        node_size_mm(node)  # touch bbox helper for parity with the grandalf script

    wire_style = CoreStyle(stroke="#2980b9", stroke_width=0.6)
    diagonal_count = 0
    for a, b in circuit.edges:
        node_a, node_b = circuit.nodes[a], circuit.nodes[b]
        pa = placed_ports[a][node_a.bottom_port]
        pb = placed_ports[b][node_b.top_port]
        if abs(pa.x - pb.x) > 0.5:
            diagonal_count += 1
        elements.append(Line(pa, pb, wire_style))

    print(
        f"\n{diagonal_count}/{len(circuit.edges)} edges are NOT vertical -- "
        "with no crossing-minimization pass, insertion order alone decided "
        "column position, so the deliberately swapped F1->S2 / F2->S1 feeds "
        "stay crossed instead of being resolved the way grandalf resolved them."
    )

    render_to_svg(elements, "output_networkx.svg", width="auto", height="auto")
    print("\nWrote output_networkx.svg")


if __name__ == "__main__":
    run()
