"""Tests for pcb/render.py — ConnectorBlock and FloatingPart to Circuit."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.electrical.system.system import Circuit
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    Terminator,
)
from schematika.pcb.render import render_connector_block, render_floating_part


def _two_port_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="part",
    )


def _make_block_one_slice() -> ConnectorBlock:
    sym = _two_port_symbol()
    placed = PlacedSlice(
        part_ref="F1",
        slice_index=0,
        symbol=sym,
        pins=(
            PinPlacement(pin_id="1", port_name="top"),
            PinPlacement(pin_id="2", port_name="bottom"),
        ),
    )
    col = Column(slices=(placed,), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(connector_ref="J1", functional_label="PSU", pin_columns=(pc,))


def test_render_connector_block_returns_circuit() -> None:
    block = _make_block_one_slice()
    circuit = render_connector_block(block)
    assert isinstance(circuit, Circuit)


def test_render_connector_block_adds_symbols() -> None:
    block = _make_block_one_slice()
    circuit = render_connector_block(block)
    # 1 connector anchor block + 1 placed slice = 2 symbols
    assert len(circuit.symbols) == 2


def test_render_floating_part_returns_circuit() -> None:
    fp = FloatingPart(part_ref="K1")
    circuit = render_floating_part(fp)
    assert isinstance(circuit, Circuit)


def test_render_floating_part_is_empty() -> None:
    fp = FloatingPart(part_ref="K1")
    circuit = render_floating_part(fp)
    assert circuit.symbols == []
    assert circuit.elements == []
