"""Mechanised check: does the recycle line cross equipment it isn't connected to?

`manhattan_route` (schematika.pid.connections) has no obstacle avoidance —
it only knows two endpoints and a preferred bend axis. A generic layered
graph places nodes but says nothing about routing around symbols that end
up sitting between a return line's two endpoints. This script recomputes
the recycle pipe's waypoints the same way `PIDBuilder._route_pipes` does,
then tests each segment against every *other* equipment's bounding box.

Run: uv run python routing_check.py
"""

from __future__ import annotations

from schematika.core.geometry import Point
from schematika.core.renderer import calculate_bounds
from schematika.pid.connections import manhattan_route
from schematika.pid.diagram import PIDDiagram


def _segment_crosses_rect(
    p1: Point, p2: Point, rect: tuple[float, float, float, float]
) -> bool:
    """Axis-aligned-segment vs. axis-aligned-rect overlap test.

    Manhattan routes are always axis-aligned, so this only needs the
    horizontal/vertical cases (a diagonal segment never occurs here).
    """
    min_x, min_y, max_x, max_y = rect
    if abs(p1.x - p2.x) < 1e-9:  # vertical segment
        if not (min_x <= p1.x <= max_x):
            return False
        y_lo, y_hi = sorted((p1.y, p2.y))
        return y_lo <= max_y and y_hi >= min_y
    if abs(p1.y - p2.y) < 1e-9:  # horizontal segment
        if not (min_y <= p1.y <= max_y):
            return False
        x_lo, x_hi = sorted((p1.x, p2.x))
        return x_lo <= max_x and x_hi >= min_x
    return False


def recycle_crossings(
    diagram: PIDDiagram,
    equipment_map: dict[str, str],
    *,
    src: str,
    dst: str,
    from_port: str,
    to_port: str,
) -> list[str]:
    """Recompute the src->dst recycle route; return labels of equipment it crosses."""
    src_sym = diagram.get_equipment_by_tag(equipment_map[src])
    dst_sym = diagram.get_equipment_by_tag(equipment_map[dst])
    assert src_sym is not None
    assert dst_sym is not None

    from_p = src_sym.ports[from_port]
    to_p = dst_sym.ports[to_port]
    from_dir = from_p.direction
    prefer = "vertical" if abs(from_dir.dy) > abs(from_dir.dx) else "horizontal"
    waypoints = manhattan_route(from_p.position, to_p.position, prefer=prefer)

    excluded = {equipment_map[src], equipment_map[dst]}
    hits: list[str] = []
    for sym in diagram.equipment:
        label = sym.label
        if not label or label in excluded or label in hits:
            continue
        rect = calculate_bounds(sym.elements)
        for i in range(len(waypoints) - 1):
            if _segment_crosses_rect(waypoints[i], waypoints[i + 1], rect):
                hits.append(label)
                break
    return hits


def report(label: str, diagram: PIDDiagram, equipment_map: dict[str, str]) -> None:
    hits = recycle_crossings(
        diagram,
        equipment_map,
        src="tank2",
        dst="tank1",
        from_port="drain",
        to_port="vent",
    )
    print(f"[{label}] recycle line (tank2.drain -> tank1.vent) crosses: {hits or 'none'}")


if __name__ == "__main__":
    import auto_layout
    import manual_layout

    m_result = manual_layout.build()
    report("manual", m_result.diagram, m_result.equipment_map)

    a_result = auto_layout.build()
    report("auto", a_result.diagram, a_result.equipment_map)
