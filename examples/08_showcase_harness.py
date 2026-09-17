"""
Example 08: Showcase Harness — cable module demo

A 4-conductor motor cable from contactor Q1 (connector T1) to motor M1
(connector J1) — the same fictional panel as example 07's Motor 1
circuit. Part of the project's GitHub showcase (showcase/cable.html).

Requires the [cable] extra: pip install schematika[cable]

Concepts taught:
    - CableRun: declare an inter-device cable as catalog Wires
    - cable_run_to_drawing: CableRun -> CableDrawing
    - render_cable_svg: CableDrawing -> SVG markup
"""

from pathlib import Path

from schematika.cable import CableRun, cable_run_to_drawing, render_cable_svg
from schematika.catalog.cables import CableData
from schematika.catalog.identifiers import ConnectorId, DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire

SHOWCASE_DIR = Path(__file__).parent.parent / "showcase" / "assets" / "cable"
SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)


def _wire(pole: str, color: str) -> Wire:
    return Wire(
        net=NetId(f"M1_{pole}"),
        source=PinRef(
            device=DeviceTag("Q1"), connector=ConnectorId("T1"), port_id=pole
        ),
        target=PinRef(
            device=DeviceTag("M1"), connector=ConnectorId("J1"), port_id=pole
        ),
        color=color,
    )


def main():
    run = CableRun(
        wires=(
            _wire("U", "BN"),
            _wire("V", "BK"),
            _wire("W", "GY"),
            _wire("PE", "GNYE"),
        ),
        cable=CableData(wire_gauge=2.5, cable_note="Motor 1 supply"),
    )
    drawing = cable_run_to_drawing(run, "W001")
    svg = render_cable_svg(drawing)

    svg_path = SHOWCASE_DIR / "harness.svg"
    svg_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {svg_path}")


if __name__ == "__main__":
    main()
