"""Prototype: a Schematika-style Board API with SKiDL as a hidden backend (explicit Circuit, no globals in user code).

Illustrative only. Answers: can SKiDL sit behind our own syntax, and does state leak between boards?
"""
from __future__ import annotations

import builtins
import importlib
from dataclasses import dataclass, field
from typing import Any

# Loaded dynamically: SKiDL injects names (e.g. `default_circuit` into builtins) that static checkers cannot see.
def _load() -> Any:
    return importlib.import_module("skidl")


_sk = _load()
SKIDL, TEMPLATE, Circuit, Net, Part, Pin = _sk.SKIDL, _sk.TEMPLATE, _sk.Circuit, _sk.Net, _sk.Part, _sk.Pin

PASSIVE = Pin.types.PASSIVE


@dataclass(frozen=True)
class PartSpec:
    """What the Schematika catalog would supply: no KiCad symbol library needed."""

    name: str
    prefix: str
    pins: tuple[tuple[str, str], ...]  # (number, name)
    footprint: str = ""
    description: str = ""


@dataclass
class Board:
    name: str
    _c: Any = field(default_factory=Circuit)
    _nets: dict[str, Any] = field(default_factory=dict)

    def part(self, spec: PartSpec, *, tag: str, value: str = "", **fields: str):
        tpl = Part(
            name=spec.name, tool=SKIDL, dest=TEMPLATE, ref_prefix=spec.prefix,
            description=spec.description, circuit=self._c,
            pins=[Pin(num=n, name=nm, func=PASSIVE) for n, nm in spec.pins],
        )
        if spec.footprint:
            tpl.footprint = spec.footprint
        p = tpl(value=value or spec.name, tag=tag, circuit=self._c)
        for k, v in fields.items():
            setattr(p, k, v)
        return p

    def net(self, name: str) -> Any:
        if name not in self._nets:
            self._nets[name] = Net(name, circuit=self._c)
        return self._nets[name]

    def connect(self, net_name: str, *pins) -> None:
        n = self.net(net_name)
        for pin in pins:
            n += pin

    def nc(self, *pins) -> None:
        for pin in pins:
            self._c.NC += pin

    @property
    def circuit(self) -> Any:
        return self._c


CONN4 = PartSpec("Conn_01x04", "J", (("1", "Pin_1"), ("2", "Pin_2"), ("3", "Pin_3"), ("4", "Pin_4")),
                 "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", "Field connector")
RES = PartSpec("R", "R", (("1", "~"), ("2", "~")), "Resistor_SMD:R_0603_1608Metric", "Resistor")


def make(name: str, r_value: str) -> Board:
    b = Board(name)
    j1 = b.part(CONN4, tag=f"{name}_j1", mpn="430451600")
    r1 = b.part(RES, tag=f"{name}_r1", value=r_value)
    b.connect("VIN", j1[1], r1[1])
    b.connect("GND", j1[2], r1[2])
    b.nc(j1[3], j1[4])
    return b


if __name__ == "__main__":
    a, b = make("A", "10k"), make("B", "4k7")
    for board in (a, b):
        c = board.circuit
        print(board.name, "parts:", [(p.ref, p.value) for p in c.parts])
        print(board.name, "nets:", {n.name: [f"{pin.part.ref}.{pin.num}" for pin in n.pins] for n in c.nets if n.pins})
    print("global default_circuit parts (should be 0):", len(vars(builtins)["default_circuit"].parts))
