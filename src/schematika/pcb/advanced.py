"""schematika.pcb.advanced — tier-2 PCB names.

Public but lighter docstring bar; free to break on minor versions.
"""

from schematika.pcb.builder import A3_LANDSCAPE, A4_LANDSCAPE
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
    ConnectorMap,
    PCBBuildResult,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)

__all__ = [
    "A3_LANDSCAPE",
    "A4_LANDSCAPE",
    "ConnectorMap",
    "DuplicateMappingError",
    "HeightOverflowError",
    "IncompleteSliceError",
    "MultiPinSliceError",
    "OrphanSliceError",
    "PCBBuildResult",
    "PinNotOnTemplateError",
    "PortNotOnSymbolError",
    "PowerNetMap",
    "SymbolMap",
    "SymbolMapping",
    "SymbolSlice",
    "UnmappedPartError",
]
