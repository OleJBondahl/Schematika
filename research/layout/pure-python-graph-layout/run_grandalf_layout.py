"""Lay out the synthetic interlock ladder with grandalf's SugiyamaLayout.

Answers the spike question concretely: feed grandalf real node sizes taken
from Schematika Symbol bounding boxes, read back its (x, y) positions, map
them onto `schematika.core.geometry.Point`s, translate the real Symbols
there, and render with Schematika's own SVG renderer -- then look at the
result.

grandalf only produces node centers. It knows nothing about *ports*: a
component here has one port pointing up and one pointing down, which is a
degenerate case in grandalf's world (it does not model side-specific
attachment points at all -- it just terminates edges at the node's
center/bbox). Edges between adjacent layers are drawn as straight lines
between whatever coordinates we choose to read off each port; grandalf itself
never guarantees those lines stay orthogonal, and does no port-to-port
routing. Both gaps are made visible in the rendered SVG below.
"""

from grandalf.graphs import Edge as GEdge
from grandalf.graphs import Graph as GGraph
from grandalf.graphs import Vertex as GVertex
from grandalf.layouts import SugiyamaLayout

from circuit_graph import build_interlock_ladder, node_size_mm, place_node
from schematika.core.geometry import Point
from schematika.core.geometry import Style as CoreStyle
from schematika.core.primitives import Line
from schematika.rendering.svg import render_to_svg

# mm per grandalf layout unit, chosen so component bodies (~15-20mm) don't
# overlap once grandalf's internal spacing (driven by view.w/view.h) is
# mapped back to millimeters.
_SCALE_X = 1.0
_SCALE_Y = 1.0


class _View:
    """grandalf's required per-vertex `.view` duck type: needs `.w`/`.h`."""

    def __init__(self, w: float, h: float) -> None:
        self.w = w
        self.h = h


def run() -> None:
    """Build the ladder, lay it out with grandalf, render, and print a report."""
    circuit = build_interlock_ladder()

    tags = list(circuit.nodes)
    vertices = {tag: GVertex(tag) for tag in tags}
    for tag, node in circuit.nodes.items():
        w, h = node_size_mm(node)
        # Pad generously -- grandalf packs by view.w/h with no separate margin.
        vertices[tag].view = _View(w + 20, h + 15)  # ty: ignore[unresolved-attribute]

    g_edges = [GEdge(vertices[a], vertices[b]) for a, b in circuit.edges]
    graph = GGraph(list(vertices.values()), g_edges)

    component = graph.C[0]
    sug = SugiyamaLayout(component)
    roots = [v for v in component.sV if v.data == "L1"]
    sug.init_all(roots=roots)
    sug.draw()

    positions: dict[str, Point] = {}
    for v in component.sV:
        x, y = v.view.xy
        positions[v.data] = Point(x * _SCALE_X, y * _SCALE_Y)

    print("grandalf layer/x-order positions (mm-scaled):")
    for tag in tags:
        p = positions[tag]
        print(f"  {tag:8s} -> ({p.x:7.1f}, {p.y:7.1f})")

    elements = []
    placed_ports: dict[str, dict[str, Point]] = {}
    for tag, node in circuit.nodes.items():
        placed = place_node(node, positions[tag])
        elements.append(placed)
        placed_ports[tag] = {pid: port.position for pid, port in placed.ports.items()}

    wire_style = CoreStyle(stroke="#c0392b", stroke_width=0.6)
    diagonal_count = 0
    for a, b in circuit.edges:
        node_a, node_b = circuit.nodes[a], circuit.nodes[b]
        pa = placed_ports[a][node_a.bottom_port]
        pb = placed_ports[b][node_b.top_port]
        if abs(pa.x - pb.x) > 0.5:
            diagonal_count += 1
        elements.append(Line(pa, pb, wire_style))

    print(
        f"\n{diagonal_count}/{len(circuit.edges)} edges are NOT vertical "
        "(straight diagonal lines -- grandalf gave us a center point, not a "
        "routed orthogonal wire; the crossing between F1->S2 and F2->S1 is "
        "visibly a plain diagonal, not a Manhattan jog)."
    )

    render_to_svg(elements, "output_grandalf.svg", width="auto", height="auto")
    print("\nWrote output_grandalf.svg")


if __name__ == "__main__":
    run()
