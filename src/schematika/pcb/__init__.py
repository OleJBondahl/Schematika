"""schematika.pcb — SKiDL → Schematika bridge."""

from schematika.pcb.builder import (
    A3_LANDSCAPE,
    A4_LANDSCAPE,
    add_to_project,
    build,
)
from schematika.pcb.errors import (
    DuplicateMappingError,
    HeightOverflowError,
    IncompleteSliceError,
    MultiPinSliceError,
    OrphanSliceError,
    PCBBuildError,
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
    # builder
    "A3_LANDSCAPE",
    "A4_LANDSCAPE",
    "add_to_project",
    "build",
    # errors
    "DuplicateMappingError",
    "HeightOverflowError",
    "IncompleteSliceError",
    "MultiPinSliceError",
    "OrphanSliceError",
    "PCBBuildError",
    "PinNotOnTemplateError",
    "PortNotOnSymbolError",
    "UnmappedPartError",
    # model
    "ConnectorMap",
    "PCBBuildResult",
    "PowerNetMap",
    "SymbolMap",
    "SymbolMapping",
    "SymbolSlice",
]
