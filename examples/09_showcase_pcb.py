"""
Example 09: Showcase PCB Bridge — SKiDL -> Schematika demo

A small original "relay-driver interface board" circuit (2 connectors,
1 fuse, 1 relay, GND/+24V power nets) bridged from SKiDL into a
Schematika schematic. Deliberately modest: the PCB module's symbol
coverage is intentionally thin and tracked separately — this shows the
bridge works, not a finished board.

Requires the [pcb] extra: pip install schematika[pcb]

Concepts taught:
    - Declaring SKiDL part templates and instantiating them on a Circuit
    - SymbolMapping: SKiDL template -> Schematika symbol slices
    - pcb.build(): SKiDL Circuit + SymbolMapping -> PCBBuildResult
    - Project.add_pcb() + Project.build_svgs(): PCBBuildResult -> SVG
"""

from pathlib import Path

import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.electrical.symbols import coil, fuse
from schematika.pcb import build
from schematika.pcb.model import (
    ConnectorMap,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)
from schematika.pcb.symbols.power import gnd as gnd_symbol
from schematika.pcb.symbols.power import power_24v
from schematika.project import Project

SHOWCASE_DIR = Path(__file__).parent.parent / "showcase" / "assets" / "pcb"
SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)


def _fuse_sym(label: str = "", **_kwargs: object):
    return fuse(label=label)


def _relay_sym(label: str = "", **_kwargs: object):
    return coil(label=label, pins=("A1", "A2"))


def build_circuit() -> tuple[Circuit, Part, Part, Part]:
    """A 2-connector, 1-fuse, 1-relay interface board — original demo topology."""
    circuit = Circuit()

    conn_template = Part(
        name="conn_4p",
        ref_prefix="J",
        pins=[Pin(num=str(i), name="") for i in range(1, 5)],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )
    fuse_template = Part(
        name="fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )
    relay_template = Part(
        name="relay_spst",
        ref_prefix="K",
        pins=[Pin(num="A1", name=""), Pin(num="A2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )

    j1 = conn_template(ref="J1", circuit=circuit)
    j2 = conn_template(ref="J2", circuit=circuit)
    f1 = fuse_template(ref="F1", circuit=circuit)
    k1 = relay_template(ref="K1", circuit=circuit)

    vcc = Net("+24V", circuit=circuit)
    gnd = Net("GND", circuit=circuit)
    sig_in = Net("SIG_IN", circuit=circuit)
    sig_out = Net("SIG_OUT", circuit=circuit)

    vcc += j1["1"], f1["1"]
    sig_in += j1["2"], k1["A1"]
    gnd += j1["3"], k1["A2"], j1["4"]
    sig_out += f1["2"], j2["1"]

    return circuit, conn_template, fuse_template, relay_template


def main():
    circuit, conn_template, fuse_template, relay_template = build_circuit()

    mapping = SymbolMapping(
        symbols=(
            SymbolMap(
                template=fuse_template,
                slices=(SymbolSlice(symbol=_fuse_sym, pin_map={"1": "1", "2": "2"}),),
            ),
            SymbolMap(
                template=relay_template,
                slices=(
                    SymbolSlice(symbol=_relay_sym, pin_map={"A1": "A1", "A2": "A2"}),
                ),
            ),
        ),
        connectors=(ConnectorMap(template=conn_template),),
        power_nets=(
            PowerNetMap(canonical_name="GND", symbol=gnd_symbol),
            PowerNetMap(canonical_name="+24V", symbol=power_24v),
        ),
    )

    # Sized to keep this small demo circuit on a single page, so the
    # fixed-name copy step below (via the sorted glob) picks up the
    # right page.
    result = build(circuit, mapping, page_size=(250.0, 200.0))

    project = Project(
        title="Interface Board (Demo)",
        drawing_number="EX-009",
        author="Schematika",
        project="Examples",
        revision="01",
    )
    project.add_pcb(result)
    project.build_svgs(str(SHOWCASE_DIR))

    # add_pcb names pages "pcb_page_<title>"; copy the first to a fixed
    # name so the showcase HTML doesn't need to know the exact title.
    pages = sorted(SHOWCASE_DIR.glob("pcb_page_*.svg"))
    if not pages:
        msg = "no pcb_page_*.svg produced — check the PCB build"
        raise SystemExit(msg)
    (SHOWCASE_DIR / "board.svg").write_bytes(pages[0].read_bytes())
    print(f"Wrote {SHOWCASE_DIR / 'board.svg'}")


if __name__ == "__main__":
    main()
