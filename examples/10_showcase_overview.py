"""
Example 10: Showcase Overview — interactive connectivity graph demo

Builds a small Project with explicit device-to-device wiring for the
same fictional panel as examples 07-09, then renders it as a
self-contained interactive HTML graph. Part of the project's GitHub
showcase (showcase/overview.html).

Concepts taught:
    - Project.add_wires(): feed explicit inter-device Wires into a Project
    - schematika.overview.build(): Project -> self-contained interactive HTML
"""

from pathlib import Path

from schematika.catalog.identifiers import ConnectorId, DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire
from schematika.overview import build as build_overview
from schematika.project import Project

SHOWCASE_DIR = Path(__file__).parent.parent / "showcase" / "assets" / "overview"
SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)


def _wire(
    net: str, src_device: str, src_conn: str, dst_device: str, dst_conn: str, port: str
) -> Wire:
    return Wire(
        net=NetId(net),
        source=PinRef(
            device=DeviceTag(src_device), connector=ConnectorId(src_conn), port_id=port
        ),
        target=PinRef(
            device=DeviceTag(dst_device), connector=ConnectorId(dst_conn), port_id=port
        ),
    )


def main():
    project = Project(
        title="Showcase Panel Overview",
        project="Examples",
    )
    project.add_wires(
        [
            _wire("M1_U", "Q1", "T1", "M1", "J1", "U"),
            _wire("M1_V", "Q1", "T1", "M1", "J1", "V"),
            _wire("M1_W", "Q1", "T1", "M1", "J1", "W"),
            _wire("M2_U", "Q2", "T1", "M2", "J1", "U"),
            _wire("M2_V", "Q2", "T1", "M2", "J1", "V"),
            _wire("M2_W", "Q2", "T1", "M2", "J1", "W"),
            _wire("START", "S1", "X12", "K3", "A1", "1"),
            _wire("SEAL", "K3", "13", "K3", "A1", "1"),
        ]
    )

    output_path = SHOWCASE_DIR / "overview.html"
    build_overview(project, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
