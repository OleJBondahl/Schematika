"""Comparison example (b): the same fuse -> E-stop -> coil rung, using the
`layout_dsl_sketch.Cursor` prototype instead of direct CircuitBuilder calls.

This is a research prototype for the llm-dsl-pipeline spike -- see
docs/research/layout-improvement/llm-dsl-pipeline.md for the verdict.

Run with: uv run python research/layout/llm-dsl-pipeline/b_relative_dsl_version.py
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
from schematika.core.options import BuildOptions

from layout_dsl_sketch import start_cursor

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

WIRE_LABELS = [
    WireLabels.BK_1_5,
    WireLabels.BK_1_5,
    WireLabels.BK_1_5,
    WireLabels.BK_1_5,
]


def main() -> None:
    state = create_initial_state()
    builder = CircuitBuilder(state)

    cursor = start_cursor(builder)
    (
        cursor.terminal("X1")
        .down(breaker, tag="F")
        .down(nc_contact, tag="S")
        .down(coil, tag="K")
        .terminal("X2")
    )

    result = builder.build(options=BuildOptions(count=1, wire_labels=WIRE_LABELS))

    svg_path = str(OUTPUT_DIR / "b_relative_dsl_version.svg")
    render_system(result.circuit, svg_path, width="auto", height="auto")
    print(f"Rendered: {svg_path}")


if __name__ == "__main__":
    main()
