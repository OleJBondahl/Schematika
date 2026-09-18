"""Shared synthetic P&ID topology for the manual vs. auto-layout comparison.

Both `manual_layout.py` and `auto_layout.py` build the *same* process so the
comparison isolates the one variable under test: how equipment gets
positioned. Pipe and instrument declarations are applied identically by
both scripts via `apply_pipes` / `apply_instruments` below.

Topology::

    tank1 --> pump --> control_valve --> tank2
                 \\--> bypass_valve -------/      (parallel bypass, lane 1)
    tank2 --(recycle, back-edge)--> tank1

    Instruments: PT on pump outlet, FT on control_valve outlet,
    LT on tank2 vent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from schematika.pid.builder import PIDBuilder
from schematika.pid.symbols import centrifugal_pump, control_valve, gate_valve, tank

if TYPE_CHECKING:
    from schematika.core.symbol import SymbolFactory


@dataclass(frozen=True)
class EquipmentDef:
    """One process unit: name, symbol factory, tag prefix, factory kwargs."""

    name: str
    factory: SymbolFactory
    tag_prefix: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipeDef:
    """One process-flow edge. `lane` groups parallel paths; `back_edge` marks
    a recycle/return line that would otherwise create a cycle in the flow
    graph (excluded from layering, routed like any other pipe)."""

    src: str
    dst: str
    from_port: str = "outlet"
    to_port: str = "inlet"
    lane: int = 0
    back_edge: bool = False
    line_spec: str = ""


@dataclass(frozen=True)
class InstrumentDef:
    """One ISA 5.1 instrument bubble attached to an equipment port."""

    name: str
    letters: str
    on_equipment: str
    on_port: str
    location: str = "field"


EQUIPMENT: list[EquipmentDef] = [
    EquipmentDef("tank1", tank, "T", {"kind": "closed"}),
    EquipmentDef("pump", centrifugal_pump, "P"),
    EquipmentDef("control_valve", control_valve, "CV"),
    EquipmentDef("bypass_valve", gate_valve, "GV"),
    EquipmentDef("tank2", tank, "T", {"kind": "closed"}),
]

PIPES: list[PipeDef] = [
    PipeDef("tank1", "pump", from_port="outlet", to_port="inlet"),
    PipeDef("pump", "control_valve", from_port="outlet", to_port="in"),
    PipeDef("control_valve", "tank2", from_port="out", to_port="inlet"),
    PipeDef("pump", "bypass_valve", from_port="outlet", to_port="in", lane=1),
    PipeDef("bypass_valve", "tank2", from_port="out", to_port="inlet", lane=1),
    PipeDef(
        "tank2",
        "tank1",
        from_port="drain",
        to_port="vent",
        back_edge=True,
        line_spec="RECYCLE",
    ),
]

INSTRUMENTS: list[InstrumentDef] = [
    InstrumentDef("pt", "PT", on_equipment="pump", on_port="outlet"),
    InstrumentDef("ft", "FT", on_equipment="control_valve", on_port="out"),
    InstrumentDef("lt", "LT", on_equipment="tank2", on_port="vent", location="panel"),
]


def apply_pipes(builder: PIDBuilder, pipes: list[PipeDef] = PIPES) -> None:
    """Declare every pipe in *pipes* on *builder* (identical for both layouts)."""
    for p in pipes:
        builder.pipe(
            p.src,
            p.dst,
            from_port=p.from_port,
            to_port=p.to_port,
            line_spec=p.line_spec,
        )


def apply_instruments(
    builder: PIDBuilder, instruments: list[InstrumentDef] = INSTRUMENTS
) -> None:
    """Declare every instrument in *instruments* on *builder* (identical for both)."""
    for inst in instruments:
        builder.add_instrument(
            inst.name,
            inst.letters,
            on_equipment=inst.on_equipment,
            on_port=inst.on_port,
            location=inst.location,
        )
