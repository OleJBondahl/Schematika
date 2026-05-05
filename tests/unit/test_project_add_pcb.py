"""Tests for Project.add_pcb consuming ConnectorBlock (Option A)."""

from unittest.mock import MagicMock, patch

from schematika.core.state import create_initial_state
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    Page,
    PCBBuildResult,
    PinColumns,
    Terminator,
)


def _minimal_result(block_ref: str = "J1") -> PCBBuildResult:
    pc = PinColumns(pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),))
    block = ConnectorBlock(
        connector_ref=block_ref, functional_label=None, pin_columns=(pc,)
    )
    page = Page(title="Page 1", connector_block_refs=(block_ref,))
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block,),
        floating_parts=(),
        pages=(page,),
    )


def test_add_pcb_registers_circuit_with_stable_key() -> None:
    """Project.add_pcb must call add_circuit with key 'pcb_block_J1'."""
    from schematika.project import Project

    project = Project.__new__(Project)
    registered: dict = {}
    project.add_circuit = lambda key, fn: registered.__setitem__(key, fn)  # type: ignore[method-assign]
    project.page = lambda title, keys: None  # type: ignore[method-assign]      project._state = None  # type: ignore[attr-defined]

    result = _minimal_result("J1")
    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ):
        project.add_pcb(result)

    assert "pcb_block_J1" in registered


def test_add_pcb_registers_floating_part() -> None:
    """Project.add_pcb must call add_circuit with key 'pcb_floating_K1' for floating parts."""
    from schematika.project import Project

    pc = PinColumns(pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    page = Page(
        title="Floating",
        connector_block_refs=(),
        floating_part_refs=("K1",),
    )
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block,),
        floating_parts=(FloatingPart(part_ref="K1"),),
        pages=(page,),
    )
    project = Project.__new__(Project)
    registered: dict = {}
    project.add_circuit = lambda key, fn: registered.__setitem__(key, fn)  # type: ignore[method-assign]
    project.page = lambda title, keys: None  # type: ignore[method-assign]      project._state = None  # type: ignore[attr-defined]

    with patch("schematika.pcb.render.render_floating_part", return_value=MagicMock()):
        project.add_pcb(result)

    assert "pcb_floating_K1" in registered
