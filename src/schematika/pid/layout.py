"""P&ID placement resolution: BFS over a port-to-port placement graph."""

from collections import deque
from dataclasses import dataclass, field

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Symbol
from schematika.core.transform import translate
from schematika.pid.errors import PIDPlacementError


@dataclass(frozen=True)
class Placement:
    """Anchor + port pair + offset; `my_port` aligns to anchor's `anchor_port`."""

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
    """BFS from *root* at *root_position*; raises PIDPlacementError on cycles."""
    if root not in symbols:
        msg = f"Root equipment {root!r} not found in symbols dict."
        raise PIDPlacementError(msg)

    placed: dict[str, Symbol] = {}

    # Place root.
    placed[root] = translate(symbols[root], root_position.x, root_position.y)

    # Build adjacency list: anchor -> list of children.
    children: dict[str, list[str]] = {name: [] for name in symbols}
    for name, pl in placements.items():
        if pl.anchor not in symbols:
            msg = f"Equipment {name!r} references unknown anchor {pl.anchor!r}."
            raise PIDPlacementError(msg)
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
                msg = f"Cycle detected: {child_name!r} was already visited."
                raise PIDPlacementError(msg)

            pl = placements[child_name]
            child_sym = symbols[child_name]

            # Validate ports.
            if pl.anchor_port not in current_placed.ports:
                available = list(current_placed.ports.keys())
                msg = (
                    f"Port {pl.anchor_port!r} not found on {current!r}. "
                    f"Available ports: {available}"
                )
                raise PIDPlacementError(msg)
            if pl.my_port not in child_sym.ports:
                available = list(child_sym.ports.keys())
                msg = (
                    f"Port {pl.my_port!r} not found on {child_name!r}. "
                    f"Available ports: {available}"
                )
                raise PIDPlacementError(msg)

            anchor_pt = current_placed.ports[pl.anchor_port].position
            my_pt_local = child_sym.ports[pl.my_port].position

            # dx, dy so that translated my_pt_local == anchor_pt + offset
            dx = anchor_pt.x - my_pt_local.x + pl.offset.dx
            dy = anchor_pt.y - my_pt_local.y + pl.offset.dy

            placed[child_name] = translate(child_sym, dx, dy)
            visited.add(child_name)
            queue.append(child_name)

    return placed


def _detect_cycle(_root: str, children: dict[str, list[str]]) -> None:
    """DFS from every node so unreachable-from-root cycles are also caught."""
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(children, white)

    def dfs(node: str) -> None:
        color[node] = gray
        for child in children.get(node, []):
            if color.get(child, white) == gray:
                msg = (
                    f"Cycle detected in placement graph: {child!r} is reachable "
                    f"from itself via {node!r}."
                )
                raise PIDPlacementError(msg)
            if color.get(child, white) == white:
                dfs(child)
        color[node] = black

    for node in list(children):
        if color[node] == white:
            dfs(node)
