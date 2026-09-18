"""Convert a Schematika electrical BuildResult into an ELK JSON graph.

Throwaway research spike code (research/layout/elk-bridge/). Not wired into
src/schematika/ and not held to the repo's docstring/type-checking bar.

Maps:
    Symbol (+ its Ports)   -> ELK "child" node with FIXED_SIDE ports
    wire_connections tuple -> ELK edge between two port ids
    (tag, pin) pair        -> ELK port id "<tag>.<pin>"

Port side is inferred from the Port.direction unit vector (dominant axis),
since Schematika ports don't carry an explicit "side" concept -- only a
wire-exit direction, which is the same information ELK's FIXED_SIDE port
constraint needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schematika.core.bbox import compute_bounding_box
from schematika.core.symbol import Symbol

if TYPE_CHECKING:
    from schematika.electrical.builder_models import BuildResult

# Physical units: Schematika works in mm. ELK has no unit opinion, so we
# feed mm straight through and interpret the returned coordinates as mm.
PORT_SIZE = 2.0


def _port_side(dx: float, dy: float) -> str:
    """Map a Schematika port exit-direction vector to an ELK compass side."""
    if abs(dy) >= abs(dx):
        return "SOUTH" if dy >= 0 else "NORTH"
    return "EAST" if dx >= 0 else "WEST"


def symbol_to_elk_node(tag: str, symbol: Symbol) -> dict[str, Any]:
    """Build one ELK child-node dict from a placed Symbol.

    Node width/height come from the symbol's own bounding box; port
    positions are made node-relative (ELK requires this for FIXED_SIDE).
    """
    bbox = compute_bounding_box(symbol)
    ports = []
    for pin_id, port in symbol.ports.items():
        ports.append(
            {
                "id": f"{tag}.{pin_id}",
                "width": PORT_SIZE,
                "height": PORT_SIZE,
                # Port position relative to the node's own top-left corner.
                "x": port.position.x - bbox.min_x - PORT_SIZE / 2,
                "y": port.position.y - bbox.min_y - PORT_SIZE / 2,
                "properties": {
                    "port.side": _port_side(port.direction.dx, port.direction.dy)
                },
            }
        )
    return {
        "id": tag,
        "width": max(bbox.width, 1.0),
        "height": max(bbox.height, 1.0),
        "ports": ports,
        "properties": {"portConstraints": "FIXED_SIDE"},
    }


def build_pin_resolver(
    result: "BuildResult",
) -> tuple[Any, list[tuple[str, str, str]]]:
    """Build a (tag, semantic_pin_label, role) -> real Port.id resolver.

    `BuildResult.wire_connections` logs *semantic* pin identifiers: a
    terminal's user-supplied pin label, or a symbol factory's declared
    `*_pins` default (e.g. contactor's "L1"/"T1"). `Symbol.ports` is keyed
    *positionally* ("1".."N") regardless of those semantic names -- see
    `contactor()`'s own docstring doctest in
    electrical/symbols/assemblies.py:47
    (``sorted(sym.ports.keys()) == ['1','2','3','4','5','6']`` even though
    `contact_pins` defaults to the semantic IEC names). The two id spaces
    are NOT the same string space, so `wire_connections` pin strings
    cannot be used directly as ELK port ids.

    This rebuilds the missing mapping heuristically: for each tag, split
    its real ports into "up-facing" (direction.dy < 0) and "down-facing"
    (direction.dy > 0) pools sorted left-to-right by x (mirroring
    `get_connection_ports()` in electrical/layout/layout.py, the same
    geometry order the builder itself uses when it has to fall back).
    Semantic labels are then assigned to real ports in first-seen order
    per (tag, role). This is a heuristic, not a guarantee -- see the
    "Motor port-count mismatch" note in elk-bridge.md for a case
    (`motor`) where a `wire_connections` entry has no real port to match
    at all, because the auto-generated pin count (poles*2) overshoots the
    symbol's actual pin count.
    """
    up_ports: dict[str, list] = {}
    down_ports: dict[str, list] = {}
    for elem in result.circuit.elements:
        if not (isinstance(elem, Symbol) and elem.label is not None):
            continue
        tag = elem.label
        ports = list(elem.ports.values())
        up_ports[tag] = sorted(
            (p for p in ports if p.direction.dy < 0), key=lambda p: p.position.x
        )
        down_ports[tag] = sorted(
            (p for p in ports if p.direction.dy > 0), key=lambda p: p.position.x
        )

    seen_index: dict[tuple[str, str], int] = {}
    label_to_real: dict[tuple[str, str], str | None] = {}
    unresolved: list[tuple[str, str, str]] = []

    def resolve(tag: str, label: str, role: str) -> str | None:
        """role: "source" (down-facing/output side) or "target" (up-facing/input)."""
        key = (tag, label)
        if key in label_to_real:
            return label_to_real[key]
        pool = down_ports.get(tag, []) if role == "source" else up_ports.get(tag, [])
        idx = seen_index.get((tag, role), 0)
        seen_index[(tag, role)] = idx + 1
        if idx >= len(pool):
            unresolved.append((tag, label, role))
            label_to_real[key] = None
            return None
        port_id = pool[idx].id
        label_to_real[key] = port_id
        return port_id

    return resolve, unresolved


def build_result_to_elk_graph(
    result: BuildResult,
    *,
    direction: str = "DOWN",
) -> dict[str, Any]:
    """Convert a full CircuitBuilder BuildResult into an ELK JSON graph.

    Args:
        result: Output of ``CircuitBuilder.build()``.
        direction: ELK layout direction (schematics are ladder-style, so
            "DOWN" matches Schematika's own top-to-bottom convention).

    Returns:
        A dict ready to ``json.dumps`` and feed to elkjs.
    """
    # NOTE: CircuitBuilder.build() constructs its Circuit as
    # `Circuit(elements=elements)` (schematika/electrical/builder.py) and never
    # populates `circuit.symbols` -- that list is only filled by the
    # free-function `add_symbol()` path used outside CircuitBuilder. So the
    # live path for "all placed symbols" here is filtering `circuit.elements`,
    # same fallback BuildResult.get_symbol() already relies on.
    named_symbols = [
        elem
        for elem in result.circuit.elements
        if isinstance(elem, Symbol) and elem.label is not None
    ]
    children = [symbol_to_elk_node(sym.label, sym) for sym in named_symbols if sym.label]

    resolve, unresolved = build_pin_resolver(result)
    edges = []
    for i, (from_tag, from_pin, to_tag, to_pin) in enumerate(result.wire_connections):
        real_from = resolve(from_tag, from_pin, "source")
        real_to = resolve(to_tag, to_pin, "target")
        if real_from is None or real_to is None:
            continue  # see build_pin_resolver docstring: no matching real port
        edges.append(
            {
                "id": f"e{i}",
                "sources": [f"{from_tag}.{real_from}"],
                "targets": [f"{to_tag}.{real_to}"],
            }
        )
    if unresolved:
        print(
            f"[to_elk] {len(unresolved)} wire_connections entries "
            f"had no matching real Port and were dropped: {unresolved}"
        )

    return {
        "id": "root",
        "layoutOptions": {
            "elk.algorithm": "layered",
            "elk.direction": direction,
            "elk.edgeRouting": "ORTHOGONAL",
            "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
            "elk.spacing.nodeNode": "20",
            "elk.layered.spacing.nodeNodeBetweenLayers": "40",
        },
        "children": children,
        "edges": edges,
    }
