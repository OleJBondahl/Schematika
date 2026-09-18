"""Comparison example (a): fuse -> E-stop -> coil rung, TODAY's real API.

This is the honest baseline for the llm-dsl-pipeline research spike
(docs/research/layout-improvement/llm-dsl-pipeline.md). It is a normal,
runnable Schematika program using nothing but the public CircuitBuilder API
that already exists in this repo -- no research code, no wrapper.

Rung: X1 -> F1 (breaker, standing in for a fuse) -> S1 (NC contact, E-stop)
      -> K1 (coil) -> X2

Run with: uv run python research/layout/llm-dsl-pipeline/a_today_direct.py
"""

from pathlib import Path

from schematika import (
    CircuitBuilder,
    WireLabels,
    breaker,
    coil,
    create_initial_state,
    nc_contact,
    render_system,
)
from schematika.core.options import BuildOptions, SymbolConfig, TerminalConfig

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# One label per vertical wire segment: X1->F1, F1->S1, S1->K1, K1->X2.
WIRE_LABELS = [
    WireLabels.BK_1_5,
    WireLabels.BK_1_5,
    WireLabels.BK_1_5,
    WireLabels.BK_1_5,
]


def main() -> None:
    state = create_initial_state()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    # NOTE: no Point(...) appears anywhere below. Every add_* call places
    # its component "below the previous chain head" by default -- this is
    # already a relative-placement API, not raw coordinates.
    builder.add_terminal("X1", config=TerminalConfig(poles=1))
    builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F"))
    builder.add_symbol(nc_contact, config=SymbolConfig(tag_prefix="S"))
    builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
    builder.add_terminal("X2", config=TerminalConfig(poles=1))

    result = builder.build(options=BuildOptions(count=1, wire_labels=WIRE_LABELS))

    svg_path = str(OUTPUT_DIR / "a_today_direct.svg")
    render_system(result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
