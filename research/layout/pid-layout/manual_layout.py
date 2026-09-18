"""Baseline: today's actual manual-placement workflow.

Equipment positions are hand-picked `EquipmentPlacement` offsets/absolute
points — exactly what a Schematika P&ID author writes today, per the
"P&ID visual review loop" in CLAUDE.md (edit -> render -> inspect ->
adjust). The bypass branch off the main line is placed by an eyeballed
absolute (x, y), the same way a human would guess an off-line position.

Run: uv run python manual_layout.py
"""

from __future__ import annotations

from pathlib import Path

from scenario import EQUIPMENT, apply_instruments, apply_pipes

from schematika.core.geometry import Point
from schematika.core.options import EquipmentConfig, EquipmentPlacement
from schematika.pid.builder import PIDBuilder, PIDBuildResult
from schematika.pid.diagram import render_pid
from schematika.pid.validation import validate_pid

OUT_DIR = Path(__file__).parent / "out"

_BY_NAME = {e.name: e for e in EQUIPMENT}


def build() -> PIDBuildResult:
    builder = PIDBuilder()

    def cfg(name: str) -> EquipmentConfig:
        e = _BY_NAME[name]
        return EquipmentConfig(factory=e.factory, tag_prefix=e.tag_prefix, factory_kwargs=e.kwargs)

    builder.add_equipment(
        "tank1",
        config=cfg("tank1"),
        placement=EquipmentPlacement(position=Point(0.0, 0.0)),
    )
    # Hand-picked run length (50mm) — "looks about right", not computed.
    builder.add_equipment(
        "pump",
        config=cfg("pump"),
        placement=EquipmentPlacement(
            relative_to="tank1", from_port="outlet", to_port="inlet", offset=(50.0, 0.0)
        ),
    )
    builder.add_equipment(
        "control_valve",
        config=cfg("control_valve"),
        placement=EquipmentPlacement(
            relative_to="pump", from_port="outlet", to_port="in", offset=(50.0, 0.0)
        ),
    )
    # First guess (50mm, like the others) ran the tank 3mm past the page
    # margin on render -- knocked down to 40mm on the next iteration of the
    # edit -> render -> inspect loop.
    builder.add_equipment(
        "tank2",
        config=cfg("tank2"),
        placement=EquipmentPlacement(
            relative_to="control_valve", from_port="out", to_port="inlet", offset=(40.0, 0.0)
        ),
    )
    # Bypass valve: off the main line, so its position was eyeballed as an
    # absolute point rather than derived from any port chain — this is the
    # step that takes the most trial and error by hand in practice.
    builder.add_equipment(
        "bypass_valve",
        config=cfg("bypass_valve"),
        placement=EquipmentPlacement(position=Point(150.0, -40.0)),
    )

    apply_pipes(builder)
    apply_instruments(builder)

    # Shift the whole page-0,0-rooted layout into the A3-landscape margin.
    return builder.build(x=30.0, y=90.0)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    result = build()
    render_pid(result.diagram, str(OUT_DIR / "manual.svg"))
    validation = validate_pid(result.diagram)
    print("=== manual_layout ===")
    print(f"equipment_map: {result.equipment_map}")
    print(f"instrument_map: {result.instrument_map}")
    print(f"validation.passed: {validation.passed}")
    print(f"errors: {validation.errors}")
    print(f"warnings: {validation.warnings}")


if __name__ == "__main__":
    main()
