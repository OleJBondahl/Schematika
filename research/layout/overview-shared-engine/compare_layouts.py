"""Spike prototype: compare the overview module's domain zone-engine against
a generic graph-layered (Sugiyama-style) layout, both implemented against the
*real* `schematika.overview` model and the `Layout` seam it already exposes
(`Layout = Callable[[OverviewGraph], OverviewGraph]`).

Not production code. Throwaway spike for
docs/research/layout-improvement/overview-shared-engine.md.

Run: uv run python research/layout/overview-shared-engine/compare_layouts.py
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict

from schematika.overview.layout import _natural_key, compute_device_positions
from schematika.overview.model import DeviceNode, OverviewGraph, build_graph

# ---------------------------------------------------------------------------
# 1. A synthetic but representative cabinet, expressed as the same plain
#    tuples `build_graph` takes from a real consumer (see extract.py).
# ---------------------------------------------------------------------------

WIRES = [
    ("PSU1.OUT.+", "PLC1.PWR.24V", "V24"),
    ("PSU1.OUT.-", "PLC1.PWR.GND", "GND"),
    ("PLC1.DO.1", "K1.COIL.A1", "K1_COIL"),
    ("PLC1.DO.2", "K2.COIL.A1", "K2_COIL"),
    ("K1.CONTACT.13", "Q1.IN.1", "Q1_ENABLE"),
    ("Q1.OUT.1", "X1..1", "MOTOR1_L1"),
    ("K2.CONTACT.13", "X1..2", "MOTOR2_ENABLE"),
    ("X1..1", "FIELD1-CX.J1.1", "MOTOR1_L1"),
    ("X1..2", "FIELD2-CX.J1.1", "MOTOR2_ENABLE"),
    ("PLC1.DI.1", "FIELD3-CY.J1.1", "SENSOR1"),
    ("PLC1.DI.2", "FIELD4-CY.J1.1", "SENSOR2"),
    ("X1..3", "FIELD3-CY.J1.2", "SENSOR1_RET"),
    ("X1..4", "FIELD4-CY.J1.2", "SENSOR2_RET"),
]

FUSE_LINKS: list = []
RELAY_CONTACTS = [
    ("RC1", "K1", "K1.COIL.A1", "K1.CONTACT.13"),
    ("RC2", "K2", "K2.COIL.A1", "K2.CONTACT.13"),
]
RELAY_PINS = {
    "K1": {"coil": ["K1.COIL.A1"], "contact": ["K1.CONTACT.13"], "contactPairs": []},
    "K2": {"coil": ["K2.COIL.A1"], "contact": ["K2.CONTACT.13"], "contactPairs": []},
}


def build_test_graph() -> OverviewGraph:
    graph = build_graph(WIRES, [], FUSE_LINKS, RELAY_CONTACTS, RELAY_PINS)
    field_tags = frozenset(
        d.id for d in graph.devices if d.id.startswith("FIELD")
    )
    terminal_tags = frozenset(d.id for d in graph.devices if d.id == "X1")
    new_devices = tuple(
        dataclasses.replace(d, device_class="FIELD")
        if d.id in field_tags
        else dataclasses.replace(d, device_class="X")
        if d.id in terminal_tags
        else d
        for d in graph.devices
    )
    return dataclasses.replace(graph, devices=new_devices)


# ---------------------------------------------------------------------------
# 2. A generic, domain-agnostic layered ("Sugiyama-style") layout: longest-
#    path ranking from meta-edge adjacency, then barycenter ordering within
#    each rank. This is the shape of layout a `pure-python-graph-layout` or
#    ELK-bridge engine would hand back for `electrical`/`pcb` -- no knowledge
#    of "PLC comes before PSU comes before terminals comes before field".
# ---------------------------------------------------------------------------

_COL_GAP = 760.0
_ROW_GAP = 640.0


def generic_layered_layout(graph: OverviewGraph) -> OverviewGraph:
    """Rank devices by longest path from a root, order each rank by barycenter."""
    if not graph.devices:
        return graph

    adjacency: dict[str, set[str]] = defaultdict(set)
    for me in graph.meta_edges:
        adjacency[me.a].add(me.b)
        adjacency[me.b].add(me.a)

    all_ids = [d.id for d in graph.devices]
    degree = {d.id: d.degree for d in graph.devices}
    root = max(all_ids, key=lambda i: (degree[i], i))

    # BFS layering (longest-path-from-root proxy, since this graph is a tree-
    # like harness fan-out, not a DAG with a topological direction).
    rank: dict[str, int] = {root: 0}
    frontier = [root]
    while frontier:
        nxt = []
        for node in frontier:
            for nb in adjacency[node]:
                if nb not in rank:
                    rank[nb] = rank[node] + 1
                    nxt.append(nb)
        frontier = nxt
    # Unreached nodes (disconnected) go in their own trailing rank.
    max_rank = max(rank.values(), default=0)
    for i in all_ids:
        rank.setdefault(i, max_rank + 1)

    by_rank: dict[int, list[str]] = defaultdict(list)
    for i in all_ids:
        by_rank[rank[i]].append(i)

    # One barycenter sweep using the previous rank's order as reference.
    order: dict[str, float] = {i: 0.0 for i in all_ids}
    for r in sorted(by_rank):
        prev_pos = {i: order[i] for i in by_rank.get(r - 1, [])}
        for i in by_rank[r]:
            neighbours = [n for n in adjacency[i] if n in prev_pos]
            order[i] = (
                sum(prev_pos[n] for n in neighbours) / len(neighbours)
                if neighbours
                else _natural_key(i)[1] or 0.0
            )
        by_rank[r].sort(key=lambda i: (order[i], i))
        for row, i in enumerate(by_rank[r]):
            order[i] = float(row)

    id_to_device = {d.id: d for d in graph.devices}
    placed: list[DeviceNode] = []
    for r, ids in by_rank.items():
        n = len(ids)
        for row, i in enumerate(ids):
            placed.append(
                dataclasses.replace(
                    id_to_device[i],
                    x=round(r * _COL_GAP, 2),
                    y=round((row - (n - 1) / 2) * _ROW_GAP, 2),
                )
            )
    return dataclasses.replace(graph, devices=tuple(placed))


# ---------------------------------------------------------------------------
# 3. Comparison harness.
# ---------------------------------------------------------------------------


def columns_of(graph: OverviewGraph) -> dict[float, list[str]]:
    cols: dict[float, list[str]] = defaultdict(list)
    for d in graph.devices:
        cols[d.x].append(d.id)
    return dict(sorted(cols.items()))


def describe(label: str, graph: OverviewGraph) -> str:
    lines = [f"--- {label} ---"]
    for x, ids in columns_of(graph).items():
        lines.append(f"  col x={x:>7.0f}: {sorted(ids)}")
    return "\n".join(lines)


def main() -> None:
    base_graph = build_test_graph()

    zone_graph = compute_device_positions(base_graph)
    generic_graph = generic_layered_layout(base_graph)

    report = [
        describe("Domain zone engine (schematika.overview.layout, current)", zone_graph),
        describe("Generic layered engine (rank-by-BFS, barycenter order)", generic_graph),
    ]

    zone_cols = columns_of(zone_graph)
    generic_cols = columns_of(generic_graph)
    report.append("")
    report.append(f"Zone engine column count:    {len(zone_cols)}")
    report.append(f"Generic engine column count: {len(generic_cols)}")
    report.append("")
    report.append(
        "Generic layering picks its root by degree (X1 has the highest "
        "degree here, being the terminal-block hub every field wire and "
        "downstream device passes through), so it puts the terminal block "
        "in column 0 and pushes PSU1 -- the actual power source -- to the "
        "far right, opposite of the power-flow-left-to-right convention "
        "the zone engine encodes deliberately via _INTERNAL_ORDER = (PLC, "
        "G, PSU, U, K, FT, F, Q, CT). It also collapses K2/Q1/all four "
        "FIELD devices into one rank, because 'hop count from the highest-"
        "degree node' is blind to the fact that FIELD1-CX/FIELD2-CX and "
        "FIELD3-CY/FIELD4-CY are physically different panel locations "
        "('-CX' vs '-CY' suffixes) that should visually group by location, "
        "not by hop distance. Both the zone assignment (_column_rank) and "
        "the field grouping (_location) are cabinet conventions encoded as "
        "string-id rules -- domain knowledge no generic graph-layering "
        "algorithm (BFS/longest-path ranking, ELK layered, Sugiyama) can "
        "recover from connectivity alone."
    )
    print("\n".join(report))

    out_path = __file__.replace("compare_layouts.py", "comparison_output.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
