"""End-to-end ELK-bridge spike: build a real Schematika circuit, lay it out
with elkjs (org.eclipse.elk.layered, ORTHOGONAL routing) via a Node
subprocess, and re-render it with ELK's coordinates instead of
Schematika's own ladder-layout coordinates.

Run from this directory (needs `npm install` already done here, see
package.json / node_modules):

    uv run --project ../../../.. python run_layout.py

(adjust --project path if invoked from elsewhere; it just needs the
schematika package importable.)

Throwaway spike script -- not held to repo docstring/typing conventions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from schematika import (
    CircuitBuilder,
    breaker,
    contactor,
    create_initial_state,
    motor,
    render_system,
    thermal_overload,
)
from schematika.core.bbox import compute_bounding_box
from schematika.core.geometry import Point
from schematika.core.options import BuildOptions, SymbolConfig, TerminalConfig
from schematika.core.primitives import Line
from schematika.core.transform import translate
from schematika.electrical.system.system import Circuit

from to_elk import build_result_to_elk_graph

HERE = Path(__file__).parent
NODE_BRIDGE = HERE / "elk_bridge.cjs"
OUTPUT_DIR = HERE / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def build_dol_starter():
    """Same circuit as examples/02_dol_starter.py, without wire labels.

    Reused verbatim as the "one real Schematika electrical circuit" input
    for this spike -- a 3-phase Direct-On-Line motor starter.
    """
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)
    builder.add_terminal("X1", config=TerminalConfig(poles=3))
    builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F", poles=3))
    builder.add_symbol(contactor, config=SymbolConfig(tag_prefix="Q", poles=3))
    builder.add_symbol(thermal_overload, config=SymbolConfig(tag_prefix="FT", poles=3))
    builder.add_symbol(motor, config=SymbolConfig(tag_prefix="M", poles=3))
    builder.add_terminal("X2", config=TerminalConfig(poles=3, pins=("U1", "V1", "W1")))
    return builder.build(options=BuildOptions(count=1))


def run_elk(graph: dict) -> dict:
    """Invoke the Node/elkjs subprocess bridge and return the parsed result."""
    proc = subprocess.run(
        ["node", str(NODE_BRIDGE)],
        input=json.dumps(graph),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"elk_bridge.cjs failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


def main():
    result = build_dol_starter()
    num_symbols = sum(
        1
        for e in result.circuit.elements
        if hasattr(e, "label") and hasattr(e, "ports")
    )
    print(f"Built circuit: {num_symbols} symbols, "
          f"{len(result.wire_connections)} wire connections")

    graph = build_result_to_elk_graph(result)
    (OUTPUT_DIR / "input_graph.json").write_text(json.dumps(graph, indent=2))

    laid_out = run_elk(graph)
    (OUTPUT_DIR / "elk_result.json").write_text(json.dumps(laid_out, indent=2))

    # --- Map ELK coordinates back onto Schematika Symbol positions ---
    new_circuit = Circuit()
    for node in laid_out["children"]:
        # circuit.symbols is empty for CircuitBuilder-built circuits (see
        # to_elk.py note) -- BuildResult.get_symbol() has the elements
        # fallback that actually works here.
        sym = result.get_symbol(node["id"])
        if sym is None:
            continue
        bbox = compute_bounding_box(sym)
        dx = node["x"] - bbox.min_x
        dy = node["y"] - bbox.min_y
        placed = translate(sym, dx, dy)
        new_circuit.symbols.append(placed)
        new_circuit.elements.append(placed)

    # --- Draw ELK's own orthogonal edge routing as wires ---
    wire_count = 0
    for edge in laid_out.get("edges", []):
        for section in edge.get("sections", []):
            points = [section["startPoint"]] + section.get("bendPoints", []) + [
                section["endPoint"]
            ]
            for a, b in zip(points, points[1:]):
                new_circuit.elements.append(
                    Line(start=Point(a["x"], a["y"]), end=Point(b["x"], b["y"]))
                )
                wire_count += 1
    print(f"Drew {wire_count} ELK-routed wire segments")

    svg_path = str(OUTPUT_DIR / "dol_starter_elk_layout.svg")
    render_system(new_circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")

    # Also render the original ladder layout for visual comparison.
    orig_svg = str(OUTPUT_DIR / "dol_starter_original_layout.svg")
    render_system(result.circuit, orig_svg, width="auto", height="auto")
    print(f"Rendered (original, for comparison): {orig_svg}")


if __name__ == "__main__":
    sys.exit(main())
