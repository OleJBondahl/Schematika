"""schematika.pcb — SKiDL → Schematika bridge."""

from schematika.pcb.builder import (
    A3_LANDSCAPE,
    A4_LANDSCAPE,
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

__all__ = [  # noqa: RUF022
    # builder
    "A3_LANDSCAPE",
    "A4_LANDSCAPE",
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
