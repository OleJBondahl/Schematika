"""Placement resolution for P&ID equipment.

Provides a declarative ``Placement`` descriptor and ``resolve_placements``
which computes absolute positions for all equipment in a diagram by
traversing a placement graph via BFS.
"""

from collections import deque
from dataclasses import dataclass, field

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Symbol
from schematika.core.transform import translate
from schematika.pid.errors import PIDPlacementError


@dataclass(frozen=True)
class Placement:
    """Declares where to place equipment relative to another piece.

    Attributes:
        anchor: Name (key) of the reference equipment.
        anchor_port: Port ID on the reference equipment to align from.
        my_port: Port ID on this equipment to align to the anchor port.
        offset: Additional offset applied after port alignment.
    """

    anchor: str
    anchor_port: str
    my_port: str
    offset: Vector = field(default_factory=lambda: Vector(0, 0))


def resolve_placements(
    symbols: dict[str, Symbol],
    placements: dict[str, Placement],
    root: str,
    root_position: Point,
) -> dict[str, Symbol]:
    """Resolve all equipment positions from the placement graph.

    Starting from *root* (placed at *root_position*), traverses the
    placement graph via BFS.  Each equipment's position is determined by
    aligning its ``my_port`` to the anchor's ``anchor_port``, then applying
    the ``Placement.offset``.

    Args:
        symbols: Mapping of equipment name to un-placed ``Symbol`` template.
        placements: Mapping of equipment name to ``Placement`` descriptor.
            The root equipment must NOT appear as a key (it has no anchor).
        root: Name of the root equipment (no placement descriptor required).
        root_position: Where to place the root symbol (its origin).

    Returns:
        Mapping of equipment name to translated ``Symbol``.

    Raises:
        ValueError: If a cycle is detected, an anchor references non-existent
            equipment, or a referenced port does not exist on a symbol.
    """
    if root not in symbols:
        raise PIDPlacementError(f"Root equipment {root!r} not found in symbols dict.")

    placed: dict[str, Symbol] = {}

    # Place root.
    placed[root] = translate(symbols[root], root_position.x, root_position.y)

    # Build adjacency list: anchor -> list of children.
    children: dict[str, list[str]] = {name: [] for name in symbols}
    for name, pl in placements.items():
        if pl.anchor not in symbols:
            raise PIDPlacementError(
                f"Equipment {name!r} references unknown anchor {pl.anchor!r}."
            )
        children.setdefault(pl.anchor, []).append(name)

    # Detect cycles via DFS before BFS placement to give a clear error.
    _detect_cycle(root, children)

    # BFS placement.
    queue: deque[str] = deque([root])
    visited: set[str] = {root}

    while queue:
        current = queue.popleft()
        current_placed = placed[current]

        for child_name in children.get(current, []):
            if child_name in visited:
                # Should never be reached after cycle detection, but guard anyway.
                raise PIDPlacementError(
                    f"Cycle detected: {child_name!r} was already visited."
                )

            pl = placements[child_name]
            child_sym = symbols[child_name]

            # Validate ports.
            if pl.anchor_port not in current_placed.ports:
                available = list(current_placed.ports.keys())
                raise PIDPlacementError(
                    f"Port {pl.anchor_port!r} not found on {current!r}. "
                    f"Available ports: {available}"
                )
            if pl.my_port not in child_sym.ports:
                available = list(child_sym.ports.keys())
                raise PIDPlacementError(
                    f"Port {pl.my_port!r} not found on {child_name!r}. "
                    f"Available ports: {available}"
                )

            anchor_pt = current_placed.ports[pl.anchor_port].position
            my_pt_local = child_sym.ports[pl.my_port].position

            # dx, dy so that translated my_pt_local == anchor_pt + offset
            dx = anchor_pt.x - my_pt_local.x + pl.offset.dx
            dy = anchor_pt.y - my_pt_local.y + pl.offset.dy

            placed[child_name] = translate(child_sym, dx, dy)
            visited.add(child_name)
            queue.append(child_name)

    return placed


def _detect_cycle(root: str, children: dict[str, list[str]]) -> None:
    """DFS cycle detection over all nodes.  Raises ``ValueError`` if a cycle is found.

    Runs DFS from every unvisited node so that cycles in components of the
    graph that are not reachable from *root* are also caught.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(children, WHITE)

    def dfs(node: str) -> None:
        color[node] = GRAY
        for child in children.get(node, []):
            if color.get(child, WHITE) == GRAY:
                raise PIDPlacementError(
                    f"Cycle detected in placement graph: {child!r} is reachable "
                    f"from itself via {node!r}."
                )
            if color.get(child, WHITE) == WHITE:
                dfs(child)
        color[node] = BLACK

    for node in list(children):
        if color[node] == WHITE:
            dfs(node)
