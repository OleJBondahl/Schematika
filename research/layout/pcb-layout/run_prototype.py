"""pcb-layout research spike: run a synthetic SKiDL-shaped circuit through
schematika.pcb.build(), render the result with schematika's real renderer,
and — for comparison only — hand-roll a tiny force-directed layout of the
same netlist to show why it is the wrong shape for this diagram.

Outputs (written to ./out/):
    connector_anchored.svg   -- schematika.pcb's actual deterministic layout
    force_directed.svg       -- naive spring-embedding of the same netlist

Run: uv run python research/layout/pcb-layout/run_prototype.py
(from the repo root of this worktree)
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from types import SimpleNamespace

from schematika.core.geometry import Point, Style, Vector
from schematika.core.primitives import Circle as SvgCircle
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Port, Symbol
from schematika.electrical.system.system import (
    Circuit,
    add_symbol,
    merge_circuits,
    render_system,
)
from schematika.pcb import build
from schematika.pcb.model import (
    ConnectorMap,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)
from schematika.pcb.render import render_connector_block, render_floating_part
from schematika.pcb.symbols.power import gnd, power_24v

from synthetic_circuit import build_synthetic_circuit

OUT_DIR = Path(__file__).parent / "out"


# ---------------------------------------------------------------------------
# Mapping: two-port passthrough symbol used for the fuse and relay coil.
# ---------------------------------------------------------------------------


def _two_port_symbol(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, -1)),
            "bottom": Port("2", Point(0, 5), Vector(0, 1)),
        },
        label=label or "component",
    )


def _template(name: str, n_pins: int) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        pins=[SimpleNamespace(num=str(i + 1)) for i in range(n_pins)],
    )


def build_mapping() -> SymbolMapping:
    conn_4p = _template("conn_4p", 4)
    conn_2p = _template("conn_2p", 2)
    fuse = _template("fuse", 2)
    relay_coil = _template("relay_coil", 2)

    return SymbolMapping(
        symbols=(
            SymbolMap(
                template=fuse,
                slices=(
                    SymbolSlice(symbol=_two_port_symbol, pin_map={"1": "top", "2": "bottom"}),
                ),
            ),
            SymbolMap(
                template=relay_coil,
                slices=(
                    SymbolSlice(symbol=_two_port_symbol, pin_map={"1": "top", "2": "bottom"}),
                ),
            ),
        ),
        connectors=(
            ConnectorMap(template=conn_4p),
            ConnectorMap(template=conn_2p),
        ),
        power_nets=(
            PowerNetMap(canonical_name="+24V", symbol=power_24v),
            PowerNetMap(canonical_name="GND", symbol=gnd),
        ),
    )


# ---------------------------------------------------------------------------
# Part 1: run the real schematika.pcb pipeline and render it.
# ---------------------------------------------------------------------------


def run_connector_anchored() -> None:
    circuit = build_synthetic_circuit()
    mapping = build_mapping()
    result = build(circuit, mapping, page_size=(200.0, 220.0))

    print("=== schematika.pcb.build() result ===")
    print(f"connector_blocks: {[b.connector_ref for b in result.connector_blocks]}")
    print(f"floating_parts:   {[fp.part_ref for fp in result.floating_parts]}")
    print(f"pages:            {len(result.pages)}")
    for page in result.pages:
        print(f"  page {page.title!r}: placements={page.placements}")
        print(f"    floating_placements={page.floating_placements}")

    block_by_ref = {b.connector_ref: b for b in result.connector_blocks}
    combined = Circuit()
    for page in result.pages:
        for ref, x, y in page.placements:
            block = block_by_ref[ref]
            block_circuit = render_connector_block(
                block, mapping, origin_x_mm=x, origin_y_mm=y, layout=result.layout
            )
            combined = merge_circuits(combined, block_circuit)
        for fsp in page.floating_placements:
            fp = next(
                f for f in result.floating_parts if f.part_ref == fsp.part_ref
            )
            floating_circuit = render_floating_part(
                fp,
                mapping,
                result.ir,
                origin_x_mm=fsp.x_mm,
                origin_y_mm=fsp.y_mm,
                layout=result.layout,
            )
            combined = merge_circuits(combined, floating_circuit)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "connector_anchored.svg"
    render_system(combined, str(out_path), viewbox="0 0 200 220")
    print(f"\nWrote {out_path}")


# ---------------------------------------------------------------------------
# Part 2: naive force-directed comparison (NOT wired into schematika).
#
# Hand-rolled Fruchterman-Reingold-style spring embedding, pure Python (no
# networkx/scipy — this worktree has neither installed, deliberately, since
# schematika's core has zero required runtime deps and we don't want to
# suggest adding one just for a spike comparison).
# ---------------------------------------------------------------------------


def _build_graph(circuit: SimpleNamespace) -> tuple[list[str], list[tuple[str, str]]]:
    nodes = [p.ref for p in circuit.parts]
    edges: list[tuple[str, str]] = []
    for net in circuit.nets:
        refs = [pin.part.ref for pin in net.pins]
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                edges.append((refs[i], refs[j]))
    return nodes, edges


def _spring_layout(
    nodes: list[str], edges: list[tuple[str, str]], iterations: int = 200
) -> dict[str, tuple[float, float]]:
    random.seed(0)
    area = 100.0
    k = area / math.sqrt(len(nodes))
    pos = {n: (random.uniform(0, area), random.uniform(0, area)) for n in nodes}

    def repulse(d: float) -> float:
        return k * k / max(d, 1e-6)

    def attract(d: float) -> float:
        return d * d / k

    for _ in range(iterations):
        disp = {n: [0.0, 0.0] for n in nodes}
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                ax, ay = pos[a]
                bx, by = pos[b]
                dx, dy = ax - bx, ay - by
                dist = math.hypot(dx, dy) or 1e-6
                force = repulse(dist)
                fx, fy = dx / dist * force, dy / dist * force
                disp[a][0] += fx
                disp[a][1] += fy
                disp[b][0] -= fx
                disp[b][1] -= fy
        for a, b in edges:
            ax, ay = pos[a]
            bx, by = pos[b]
            dx, dy = ax - bx, ay - by
            dist = math.hypot(dx, dy) or 1e-6
            force = attract(dist)
            fx, fy = dx / dist * force, dy / dist * force
            disp[a][0] -= fx
            disp[a][1] -= fy
            disp[b][0] += fx
            disp[b][1] += fy
        for n in nodes:
            dx, dy = disp[n]
            disp_len = math.hypot(dx, dy) or 1e-6
            step = min(disp_len, 5.0)
            x, y = pos[n]
            x += dx / disp_len * step
            y += dy / disp_len * step
            x = min(max(x, 0.0), area)
            y = min(max(y, 0.0), area)
            pos[n] = (x, y)
    return pos


def run_force_directed_comparison() -> None:
    circuit = build_synthetic_circuit()
    nodes, edges = _build_graph(circuit)
    pos = _spring_layout(nodes, edges)

    style = Style(stroke="black", fill="none", stroke_width=0.3)
    text_style = Style(stroke="none", fill="black")
    out_circuit = Circuit()
    for a, b in edges:
        out_circuit.elements.append(Line(Point(*pos[a]), Point(*pos[b]), style))
    for n in nodes:
        x, y = pos[n]
        out_circuit.elements.append(SvgCircle(Point(x, y), 3.0, style))
        out_circuit.elements.append(
            Text(content=n, position=Point(x + 4, y), anchor="start", font_size=4, style=text_style)
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "force_directed.svg"
    render_system(out_circuit, str(out_path), viewbox="0 0 100 100")
    print(f"Wrote {out_path}")
    print(
        "\nNote: this is intentionally NOT run through schematika's Symbol/Port\n"
        "renderer — a spring layout has no notion of which side of a symbol a\n"
        "port faces, so there is no meaningful way to snap connector pins to it.\n"
        "It is here only to visualize what 'generic netlist layout' would give\n"
        "you instead of the connector-anchored column layout above."
    )


if __name__ == "__main__":
    run_connector_anchored()
    print()
    run_force_directed_comparison()
