"""schematika.pcb.advanced — tier-2 PCB names.

Public but lighter docstring bar; free to break on minor versions.
"""

from schematika.pcb.errors import (
    DuplicateMappingError,
    HeightOverflowError,
    IncompleteSliceError,
    MultiPinSliceError,
    OrphanSliceError,
    PinNotOnTemplateError,
    PortNotOnSymbolError,
    UnmappedPartError,
)
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    ConnectorMap,
    FloatingPart,
    Page,
    PCBBuildResult,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)

__all__ = [
    "Column",
    "ConnectorBlock",
    "ConnectorMap",
    "DuplicateMappingError",
    "FloatingPart",
    "HeightOverflowError",
    "IncompleteSliceError",
    "MultiPinSliceError",
    "OrphanSliceError",
    "PCBBuildResult",
    "Page",
    "PinColumns",
    "PinNotOnTemplateError",
    "PinPlacement",
    "PlacedSlice",
    "PortNotOnSymbolError",
    "PowerNetMap",
    "SymbolMap",
    "SymbolMapping",
    "SymbolSlice",
    "Terminator",
    "UnmappedPartError",
]
