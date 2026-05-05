"""Render ConnectorBlock and FloatingPart to schematika Circuit objects.

This module is the boundary between pure pcb data and schematika's
rendering pipeline. Lives in schematika.pcb so it can import from
schematika.electrical.* without crossing layer boundaries (importlinter
forbids pcb from importing schematika.project).
"""

from schematika.electrical.system.system import Circuit, add_symbol
from schematika.pcb.model import ConnectorBlock, FloatingPart


def render_connector_block(block: ConnectorBlock) -> Circuit:
    """Render one ConnectorBlock to a schematika Circuit.

    For now: a minimal stub that creates a Circuit and adds each placed
    slice's symbol at the origin. Full positioning and wire drawing is
    downstream of Phase 2.

    Args:
        block: A ConnectorBlock from pcb.build().

    Returns:
        A populated Circuit with one symbol per PlacedSlice.
    """
    circuit = Circuit()
    for pin_col in block.pin_columns:
        for column in pin_col.columns:
            for placed_slice in column.slices:
                add_symbol(circuit, placed_slice.symbol)
    return circuit


def render_floating_part(floating: FloatingPart) -> Circuit:
    """Render a FloatingPart as an empty Circuit (for linter pickup only).

    Args:
        floating: A FloatingPart from pcb.build().

    Returns:
        An empty Circuit.
    """
    del floating  # to satisfy vulture
    return Circuit()
