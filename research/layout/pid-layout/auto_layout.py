"""Auto-layout: generic layered-graph placement, no hand-picked coordinates.

Every equipment position comes from `layered_layout.compute_positions`
(longest-path layering by process-flow direction + measured symbol bounds).
Pipe routing and instrument-stub placement are 100% reused, unchanged, from
`schematika.pid` — this prototype only replaces equipment *placement*.

Run: uv run python auto_layout.py
"""

from __future__ import annotations

from pathlib import Path

from layered_layout import compute_positions
from scenario import EQUIPMENT, PIPES, apply_instruments, apply_pipes

from schematika.core.options import EquipmentConfig, EquipmentPlacement
from schematika.pid.builder import PIDBuilder, PIDBuildResult
from schematika.pid.diagram import render_pid
from schematika.pid.validation import validate_pid

OUT_DIR = Path(__file__).parent / "out"


def build() -> PIDBuildResult:
    node_names = [e.name for e in EQUIPMENT]

    # Measure each symbol's bounding box at the origin (untagged) purely to
    # drive spacing — this is the generic-graph substitute for a human
    # eyeballing a pipe-run length.
    blank_symbols = {e.name: e.factory(**e.kwargs) for e in EQUIPMENT}
    positions = compute_positions(node_names, PIPES, blank_symbols)

    builder = PIDBuilder()
    for e in EQUIPMENT:
        builder.add_equipment(
            e.name,
            config=EquipmentConfig(
                factory=e.factory, tag_prefix=e.tag_prefix, factory_kwargs=e.kwargs
            ),
            placement=EquipmentPlacement(position=positions[e.name]),
        )

    apply_pipes(builder)
    apply_instruments(builder)

    # Shift the whole page-0,0-rooted layout into the A3-landscape margin.
    return builder.build(x=20.0, y=90.0)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    result = build()
    render_pid(result.diagram, str(OUT_DIR / "auto.svg"))
    validation = validate_pid(result.diagram)
    print("=== auto_layout ===")
    print(f"equipment_map: {result.equipment_map}")
    print(f"instrument_map: {result.instrument_map}")
    print(f"validation.passed: {validation.passed}")
    print(f"errors: {validation.errors}")
    print(f"warnings: {validation.warnings}")


if __name__ == "__main__":
    main()
