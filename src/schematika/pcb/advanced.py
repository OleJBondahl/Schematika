"""schematika.pcb.advanced — tier-2 PCB names.

Public but lighter docstring bar; free to break on minor versions.
"""

from schematika.pcb.errors import (
    DuplicateMappingError,
    IncompleteSliceError,
    MultiPinSliceError,
    PinNotOnTemplateError,
    PortNotOnSymbolError,
    UnmappedPartError,
    UnnamedNetError,
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
    "IncompleteSliceError",
    "MultiPinSliceError",
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
    "UnnamedNetError",
]
