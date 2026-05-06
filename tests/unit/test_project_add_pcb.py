"""Tests for Project.add_pcb consuming ConnectorBlock (Option A)."""

from unittest.mock import MagicMock, patch

from schematika.core.state import create_initial_state
from schematika.pcb.layout_spec import LayoutSpec
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
    page = Page(title="Page 1", placements=((block_ref, 0.0, 30.0),))
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block,),
        floating_parts=(),
        pages=(page,),
    )


def test_add_pcb_registers_circuit_with_stable_key() -> None:
    """Project.add_pcb must call add_circuit with key 'pcb_page_Page 1'."""
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

    assert "pcb_page_Page 1" in registered


def test_add_pcb_registers_floating_part() -> None:
    """Project.add_pcb must register a circuit for floating parts on a separate page."""
    from schematika.project import Project

    pc = PinColumns(pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    page = Page(
        title="Floating",
        placements=(),
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
    pages_registered: list = []
    project.add_circuit = lambda key, fn: registered.__setitem__(key, fn)  # type: ignore[method-assign]
    project.page = lambda title, keys: pages_registered.append((title, keys))  # type: ignore[method-assign]

    with patch("schematika.pcb.render.render_floating_part", return_value=MagicMock()):
        project.add_pcb(result)

    # Floating parts are merged into a single circuit on a dedicated "Floating parts" page.
    assert "pcb_floating_page_Floating" in registered
    assert any(title == "Floating parts" for title, _ in pages_registered)


def test_add_pcb_stores_page_viewbox() -> None:
    """add_pcb must store the page-extent viewBox in _pcb_page_viewboxes."""
    from schematika.project import Project

    project = Project.__new__(Project)
    project._pcb_page_viewboxes = {}
    project._state = None  # type: ignore[attr-defined]
    registered: dict = {}
    project.add_circuit = lambda key, fn: registered.__setitem__(key, fn)  # type: ignore[method-assign]
    project.page = lambda title, keys: None  # type: ignore[method-assign]

    result = _minimal_result("J1")
    result = PCBBuildResult(
        state=result.state,
        connector_blocks=result.connector_blocks,
        floating_parts=result.floating_parts,
        pages=result.pages,
        page_size=(420.0, 297.0),
    )
    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ):
        project.add_pcb(result)

    assert "pcb_page_Page 1" in project._pcb_page_viewboxes
    assert project._pcb_page_viewboxes["pcb_page_Page 1"] == (
        "0 0 420.0 297.0",
        420.0,
        297.0,
    )


def test_add_pcb_forwards_layout_to_render_connector_block() -> None:
    """add_pcb must forward result.layout to render_connector_block."""
    from schematika.project import Project

    custom_layout = LayoutSpec(pin_spacing_mm=20.0)
    result = _minimal_result("J1")
    result = PCBBuildResult(
        state=result.state,
        connector_blocks=result.connector_blocks,
        floating_parts=result.floating_parts,
        pages=result.pages,
        layout=custom_layout,
    )

    project = Project.__new__(Project)
    project.add_circuit = lambda key, fn: None  # type: ignore[method-assign]
    project.page = lambda title, keys: None  # type: ignore[method-assign]

    with patch(
        "schematika.pcb.render.render_connector_block", return_value=MagicMock()
    ) as mock_render:
        project.add_pcb(result)

    # layout=custom_layout must appear in the call kwargs
    assert mock_render.called
    _, kwargs = mock_render.call_args
    assert kwargs.get("layout") is custom_layout
