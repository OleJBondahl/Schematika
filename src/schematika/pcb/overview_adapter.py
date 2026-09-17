"""Convert a CircuitIR (SKiDL circuit, adapted) into overview's pcb_nets shape.

Lives in schematika.pcb, not schematika.overview: the `overview-layer`
import-linter contract forbids overview from importing pcb. This module
imports nothing from `schematika.overview` — pin ids are a plain f-string,
not routed through `overview.model.pin_id`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.pcb.adapter import CircuitIR


def pcb_nets_for_board(
    ir: CircuitIR, board: str
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Return this board's nets as (board, net_name, [pin_ids]) triples.

    Each pin id is board-qualified as ``f"{board}.{part_ref}.{pin_name}"`` —
    the same direct format Juicebox's own pre-migration extract.py already
    used — so the same net topology can be reused for multiple physical
    instances of one PCB design by calling this once per board name. No
    dependency on `schematika.overview` is needed for this formatting, so this
    module imports nothing from it.

    Args:
        ir: A CircuitIR from :func:`schematika.pcb.adapter.adapt`.
        board: The physical board instance name to qualify pin ids with (e.g. "JB1").

    Returns:
        A tuple of (board, net_name, pin_ids) triples, one per net in `ir`,
        in `ir.nets` order — directly usable as overview's `pcb_nets` input.

    Examples:
        >>> from schematika.pcb.adapter import PartRef, PinRef, NetRef, CircuitIR
        >>> part = PartRef(ref="F1", template_name="Fuse", pin_numbers=("1", "2"))
        >>> pin = PinRef(part_ref="F1", pin_name="1")
        >>> ir = CircuitIR(parts=(part,), nets=(NetRef(name="GND", pins=(pin,)),))
        >>> pcb_nets_for_board(ir, "JB1")
        (('JB1', 'GND', ('JB1.F1.1',)),)
    """
    return tuple(
        (board, net.name, tuple(f"{board}.{p.part_ref}.{p.pin_name}" for p in net.pins))
        for net in ir.nets
    )
