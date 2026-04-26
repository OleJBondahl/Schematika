"""System-overview Graphviz diagrams from a built ``Project``.

The public entry point is :func:`build`. ``OverviewOptions`` lives in
:mod:`schematika.overview.options` rather than ``schematika.core.options``:
including it in ``core`` would force domain → overview transitive imports
through the TYPE_CHECKING block, which the ``overview-leaf`` import-linter
contract forbids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from schematika.overview import emitter, extractor
from schematika.overview.errors import (
    OverviewContainmentError,
    OverviewError,
    OverviewExtractionError,
    OverviewRenderError,
)
from schematika.overview.model import ConnectionKey, ContainerSpec, Unit, Wire
from schematika.overview.options import OverviewOptions

if TYPE_CHECKING:
    from schematika.project import Project


def build(project: Project, *, options: OverviewOptions | None = None) -> None:
    """Render a Graphviz system diagram from a built ``Project``.

    Auto-calls ``project.build_circuits()`` if ``project._results`` is empty.
    Raises ``TypeError`` when called without ``options`` — same hard-break
    stance as ``CircuitBuilder.build`` after wave C2d-2.
    """
    if options is None:
        msg = (
            "OverviewOptions is required: build(project, options=OverviewOptions(...))"
        )
        raise TypeError(msg)

    if not project._results:
        project.build_circuits()

    units, wires = extractor.extract(
        project,
        containment=options.containment,
        signal_kind=options.signal_kind,
        field_location=options.field_location,
    )
    emitter.emit(
        units,
        wires,
        output_path=options.output_path,
        palette=options.palette,
        node_spacing=options.node_spacing,
        rank_spacing=options.rank_spacing,
        edge_separation=options.edge_separation,
        cluster_margin=options.cluster_margin,
    )


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
    "build",
]
