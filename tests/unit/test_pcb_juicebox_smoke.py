"""Integration smoke test: juicebox-shaped SKiDL circuit through the full PCB pipeline."""

import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.electrical.symbols import coil, connector_pin, fuse, no_contact
from schematika.pcb.builder import A3_LANDSCAPE, build
from schematika.pcb.model import (
    ConnectorMap,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)
from schematika.project import Project


def _make_connector_template(n_pins: int, name: str | None = None) -> Part:
    label = name or f"Connector{n_pins}"
    return Part(
        name=label,
        ref_prefix="J",
        pins=[Pin(num=str(i), name="") for i in range(1, n_pins + 1)],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


def _make_fuse_template() -> Part:
    return Part(
        name="Fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


def _make_relay_template() -> Part:
    """4-pin relay: coil (A1, A2) + one NO contact (13, 14)."""
    return Part(
        name="Relay",
        ref_prefix="K",
        pins=[
            Pin(num="A1", name=""),
            Pin(num="A2", name=""),
            Pin(num="13", name=""),
            Pin(num="14", name=""),
        ],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


def _build_juicebox_circuit_and_mapping():
    """Minimal juicebox topology:
      J1.1 -> F1.1 -- F1.2 -> J2.1          (fuse chain)
      J1.2 -> K1.A1 -- K1.A2 -> gnd         (coil chain to power net)
      J1.3 -> K1.13 -- K1.14 -> J2.2        (NO contact chain)

    gnd is declared POWER via power_nets.  To qualify as POWER it needs
    >=3 pins.  Two extra 1-pin connector stubs (J_gnd_a, J_gnd_b) are wired
    directly to gnd.  Connector stubs are terminators whose outward pin sees
    the POWER net — no column is generated from them, and they carry no
    SymbolMap so the orphan check ignores them.
    """
    c = Circuit()
    conn3_tmpl = _make_connector_template(3, "Connector3")
    conn2_tmpl = _make_connector_template(2, "Connector2")
    fuse_tmpl = _make_fuse_template()
    relay_tmpl = _make_relay_template()
    # Two separate 1-pin connector templates for the gnd stubs
    gnd_stub_tmpl_a = _make_connector_template(1, "GndStubA")
    gnd_stub_tmpl_b = _make_connector_template(1, "GndStubB")

    j1 = conn3_tmpl(ref="J1", circuit=c)
    j2 = conn2_tmpl(ref="J2", circuit=c)
    f1 = fuse_tmpl(ref="F1", circuit=c)
    k1 = relay_tmpl(ref="K1", circuit=c)
    j_gnd_a = gnd_stub_tmpl_a(ref="JGA", circuit=c)
    j_gnd_b = gnd_stub_tmpl_b(ref="JGB", circuit=c)

    # Chain 1: J1.1 -> fuse -> J2.1
    n1 = Net("n_j1_f1_in", circuit=c)
    n1 += j1["1"], f1["1"]
    n2 = Net("n_f1_j2_out", circuit=c)
    n2 += f1["2"], j2["1"]

    # Chain 2: J1.2 -> coil -> gnd
    n3 = Net("n_j1_k1_coil_in", circuit=c)
    n3 += j1["2"], k1["A1"]
    gnd = Net("gnd", circuit=c)
    # gnd gets 3 pins: K1.A2 + JGA.1 + JGB.1 → classified POWER
    gnd += k1["A2"], j_gnd_a["1"], j_gnd_b["1"]

    # Chain 3: J1.3 -> contact -> J2.2
    n5 = Net("n_j1_k1_cont_in", circuit=c)
    n5 += j1["3"], k1["13"]
    n6 = Net("n_k1_cont_out_j2", circuit=c)
    n6 += k1["14"], j2["2"]

    # Mapping
    fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
    fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))

    coil_slice = SymbolSlice(symbol=coil, pin_map={"A1": "A1", "A2": "A2"})
    contact_slice = SymbolSlice(symbol=no_contact, pin_map={"13": "13", "14": "14"})
    relay_map = SymbolMap(template=relay_tmpl, slices=(coil_slice, contact_slice))

    conn3_map = ConnectorMap(
        template=conn3_tmpl, pin_symbol=connector_pin, position="top"
    )
    conn2_map = ConnectorMap(
        template=conn2_tmpl, pin_symbol=connector_pin, position="bottom"
    )
    conn_gnd_a_map = ConnectorMap(
        template=gnd_stub_tmpl_a, pin_symbol=connector_pin, position="top"
    )
    conn_gnd_b_map = ConnectorMap(
        template=gnd_stub_tmpl_b, pin_symbol=connector_pin, position="top"
    )

    gnd_power_map = PowerNetMap(net_name="gnd", symbol=connector_pin)

    mapping = SymbolMapping(
        symbols=(fuse_map, relay_map),
        connectors=(conn3_map, conn2_map, conn_gnd_a_map, conn_gnd_b_map),
        power_nets=(gnd_power_map,),
    )
    return c, mapping


def test_juicebox_smoke():
    """End-to-end pipeline: fabricate, build, project.add_pcb, optional PDF."""
    c, mapping = _build_juicebox_circuit_and_mapping()

    result = build(c, mapping, page_size=A3_LANDSCAPE)

    # 3 main chains → 3 columns
    assert len(result.columns) == 3

    for idx, (key, _circ) in enumerate(result.columns):
        assert key == f"pcb_col_{idx:03d}", f"unexpected key {key!r}"

    assert len(result.pages) >= 1

    # Every column key appears in exactly one page
    all_page_keys = [k for _title, keys in result.pages for k in keys]
    for key, _circ in result.columns:
        assert all_page_keys.count(key) == 1, f"{key!r} not in exactly one page"

    # Project integration: every column registers, every page registers.
    # (Matching repo convention, real typst compilation is not exercised in unit
    # tests — see tests/unit/test_project.py for the mocking pattern.)
    project = Project(title="Juicebox smoke test")
    project.add_pcb(result)
    registered_keys = {cdef.key for cdef in project._circuit_defs}
    for key, _circ in result.columns:
        assert key in registered_keys
    assert len(project._pages) == len(result.pages)
