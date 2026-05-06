"""Tests for PCB015 — page-width underused / premature page break."""

from schematika.core.state import create_initial_state
from schematika.pcb import LayoutSpec
from schematika.pcb.checks.pcb015_page_width_underused import check
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    Page,
    PCBBuildResult,
    PinColumns,
    SymbolMapping,
    Terminator,
)


def _block(ref: str, n_pins: int) -> ConnectorBlock:
    pcs = tuple(
        PinColumns(
            pin_id=str(i + 1), columns=(Column(slices=(), terminator=Terminator.NC),)
        )
        for i in range(n_pins)
    )
    return ConnectorBlock(connector_ref=ref, functional_label=None, pin_columns=pcs)


def _result(blocks, pages, page_size=(250.0, 297.0)):
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=tuple(blocks),
        floating_parts=(),
        pages=tuple(pages),
        mapping=SymbolMapping(symbols=(), connectors=(), power_nets=()),
        layout=LayoutSpec(),
        page_size=page_size,
    )


def test_pcb015_passes_when_only_one_page() -> None:
    blocks = [_block("J1", 4)]
    pages = [Page(title="t", placements=(("J1", 0.0, 30.0),))]
    issues = check(_result(blocks, pages))
    assert issues == ()


def test_pcb015_passes_on_full_page() -> None:
    # Page 1: J1(20 pins, 210mm wide) — at width 220mm available, no room for J2(20 pins).
    blocks = [_block("J1", 20), _block("J2", 20)]
    pages = [
        Page(title="p1", placements=(("J1", 0.0, 30.0),)),
        Page(title="p2", placements=(("J2", 0.0, 30.0),)),
    ]
    issues = check(_result(blocks, pages))
    # 2*5 + 20*10 = 210mm. Available = 250 - 2*30 = 190mm.
    # Could J2 fit on page 1? need: 210 + 20 + 210 = 440mm > 190 -> no -> no warning.
    assert issues == ()


def test_pcb015_warns_on_premature_break() -> None:
    # Page 1: J1(2 pins, 30mm wide). Page 2: J2(2 pins, 30mm wide).
    # 30 + 20 + 30 = 80 mm <= 220 mm available — would have fit. WARN.
    blocks = [_block("J1", 2), _block("J2", 2)]
    pages = [
        Page(title="p1", placements=(("J1", 0.0, 30.0),)),
        Page(title="p2", placements=(("J2", 0.0, 30.0),)),
    ]
    issues = check(_result(blocks, pages))
    assert len(issues) == 1
    assert issues[0].code == "PCB015"


def test_pcb015_passes_on_empty_pages() -> None:
    blocks = []
    pages = []
    issues = check(_result(blocks, pages))
    assert issues == ()
