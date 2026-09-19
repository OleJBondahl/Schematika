"""Prototype: emit a KiCad netlist ourselves from a plain frozen IR, then diff it against SKiDL's own netlist.

The IR here is what a Schematika graph would hand a `pcb` exporter: no SKiDL types.
"""
from __future__ import annotations

import re
import sys
import uuid
from dataclasses import dataclass, replace

from wrapper_skidl import make

NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass(frozen=True)
class Pin:
    number: str
    name: str = ""
    kind: str = "passive"


@dataclass(frozen=True)
class Comp:
    id: str  # stable ID (tag); drives ref stability and tstamp
    ref: str
    value: str
    footprint: str
    lib_part: str
    pins: tuple[Pin, ...]
    fields: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NetIR:
    name: str
    nodes: tuple[tuple[str, str], ...]  # (ref, pin number)


@dataclass(frozen=True)
class BoardIR:
    comps: tuple[Comp, ...]
    nets: tuple[NetIR, ...]
    nc: tuple[tuple[str, str], ...] = ()


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_netlist(b: BoardIR, source: str = "schematika") -> str:
    pin_of = {(c.ref, p.number): p for c in b.comps for p in c.pins}
    out = ['(export (version "E")', f'  (design (source {q(source)}) (tool "Schematika"))', "  (components"]
    for c in sorted(b.comps, key=lambda c: c.ref):
        fields = "".join(f"(field (name {q(k)}) {q(v)})" for k, v in c.fields)
        out.append(
            f"    (comp (ref {q(c.ref)}) (value {q(c.value)}) (footprint {q(c.footprint)}) "
            f"(fields {fields}) (libsource (lib \"NO_LIB\") (part {q(c.lib_part)})) "
            f'(sheetpath (names "/") (tstamps "/")) (tstamps {q(str(uuid.uuid5(NS, c.id)))}))'
        )
    out.append("  )")
    out.append("  (nets")
    for i, n in enumerate(sorted(b.nets, key=lambda n: n.name), 1):
        nodes = "".join(
            f"\n      (node (ref {q(r)}) (pin {q(p)}) (pinfunction {q(pin_of[(r, p)].name)}) (pintype {q(pin_of[(r, p)].kind)}))"
            for r, p in sorted(n.nodes)
        )
        out.append(f"    (net (code {i}) (name {q(n.name)}){nodes})")
    out.append("  )")
    out.append(")")
    return "\n".join(out) + "\n"


def from_skidl(board) -> BoardIR:
    """Duck-typed walk, like pcb/adapter.py but richer (keeps value, footprint, pin names, fields)."""
    c = board.circuit
    comps = tuple(
        Comp(
            id=p.tag, ref=p.ref, value=str(p.value), footprint=str(p.footprint), lib_part=p.name,
            pins=tuple(Pin(str(x.num), str(x.name)) for x in p.pins),
            fields=tuple((k, str(getattr(p, k))) for k in ("mpn",) if hasattr(p, k)),
        )
        for p in c.parts
    )
    nets = tuple(
        NetIR(n.name, tuple((x.part.ref, str(x.num)) for x in n.pins))
        for n in c.nets if n.pins and n is not c.NC
    )
    nc = tuple((x.part.ref, str(x.num)) for x in c.NC.pins)
    return BoardIR(comps, nets, nc)


# ---- minimal s-expression reader, so the diff does not depend on any KiCad/SKiDL parser ----
def parse(text: str):
    toks = re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()"]+', text)
    pos = 0

    def node():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            items = []
            while toks[pos] != ")":
                items.append(node())
            pos += 1
            return items
        return t[1:-1] if t.startswith('"') else t

    return node()


def find(tree, key):
    return [x for x in tree if isinstance(x, list) and x and x[0] == key]


def summarise(text: str):
    t = parse(text)
    comps = {}
    for comp in find(find(t, "components")[0], "comp"):
        d = {k[0]: k[1] for k in comp if isinstance(k, list) and len(k) > 1 and isinstance(k[1], str)}
        comps[d["ref"]] = (d["value"], d["footprint"])
    nets = {}
    for net in find(find(t, "nets")[0], "net"):
        name = [k for k in net if isinstance(k, list) and k[0] == "name"][0][1]
        nets[name] = frozenset((n[1][1], n[2][1]) for n in net if isinstance(n, list) and n[0] == "node")
    return comps, nets


if __name__ == "__main__":
    board = make("A", "10k")
    ir = from_skidl(board)
    ours = write_netlist(ir)
    board.circuit.generate_netlist(file_="skidl_out.net", do_backup=False)
    skidl_txt = open("skidl_out.net", encoding="utf-8").read()
    open("own_out.net", "w", encoding="utf-8").write(ours)

    sc, sn = summarise(skidl_txt)
    oc, on = summarise(ours)
    sn_no_nc = {k: v for k, v in sn.items() if "NOCONNECT" not in k.upper() and not k.startswith("unconnected")}
    print("SKiDL comps:", sc)
    print("own   comps:", oc)
    print("components equal:", sc == oc)
    print("SKiDL nets:", {k: sorted(v) for k, v in sn.items()})
    print("own   nets:", {k: sorted(v) for k, v in on.items()})
    print("nets equal (ignoring NC pseudo-net):", sn_no_nc == on)
    print("pin names in SKiDL netlist:", "pinfunction" in skidl_txt, "| in ours:", "pinfunction" in ours)
    print("MPN field in SKiDL netlist:", '"mpn"' in skidl_txt.lower(), "| in ours:", '"mpn"' in ours.lower())
    print("SKiDL netlist lines:", skidl_txt.count("\n"), "| ours:", ours.count("\n"))

    # synthetic failing case: move one pin to a different net, the diff must notice
    bad = replace(ir, nets=tuple(
        NetIR(n.name, n.nodes[:-1]) if n.name == "VIN" else n for n in ir.nets))
    bc, bn = summarise(write_netlist(bad))
    print("perturbed netlist detected as different:", bn != sn_no_nc)
    print("own writer is", sum(1 for _ in open(__file__, encoding="utf-8")), "lines incl. IR types + reader + diff")
    sys.exit(0)
