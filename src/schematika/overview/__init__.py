"""System-overview Graphviz diagrams from a built ``Project``.

The public entry point is :func:`build`. ``OverviewOptions`` lives in
:mod:`schematika.overview.options` rather than ``schematika.core.options``:
including it in ``core`` would force domain → overview transitive imports
through the TYPE_CHECKING block, which the ``overview-leaf`` import-linter
contract forbids.
"""

from schematika.overview.errors import (
    OverviewContainmentError,
    OverviewError,
    OverviewExtractionError,
    OverviewRenderError,
)
from schematika.overview.model import ConnectionKey, ContainerSpec, Unit, Wire
from schematika.overview.options import OverviewOptions

__all__ = [
    "ConnectionKey",
    "ContainerSpec",
    "OverviewContainmentError",
    "OverviewError",
    "OverviewExtractionError",
    "OverviewOptions",
    "OverviewRenderError",
    "Unit",
    "Wire",
]
