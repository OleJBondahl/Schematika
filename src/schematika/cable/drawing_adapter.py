"""Adapter: CableBuildResult (Wire-based) -> CableDrawing (legacy render model).

Bridges the catalog-driven cable result to the existing WireViz renderer,
propagating per-wire color (F17) and length into the drawing.

Provisional: the catalog-driven cable path; no consumer uses it yet — the
adopted inter-device path is ``cable_run_to_drawing``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from schematika.cable.model import (
    CableConnection,
    CableConnector,
    CableDef,
    CableDrawing,
)

if TYPE_CHECKING:
    from schematika.cable.render_config import CableRenderConfig
    from schematika.cable.result import CableBuildResult
    from schematika.catalog.refs import PinRef
    from schematika.catalog.result import ResolvedCatalog


def _designator(endpoint: PinRef) -> str:
    """Connector name if present, else the device tag (terminal/PLC fallback)."""
    return (
        str(endpoint.connector)
        if endpoint.connector is not None
        else str(endpoint.device)
    )


def result_to_drawing(
    result: CableBuildResult,
    /,
    *,
    catalog: ResolvedCatalog,
    config: CableRenderConfig | None = None,
) -> CableDrawing:
    """Convert a ``CableBuildResult`` into a renderable ``CableDrawing``.

    Per-wire ``Wire.color`` becomes ``CableDef.wire_colors`` (F17); the first
    wire's ``length_mm`` (else the product default) becomes ``CableDef.length``.

    Args:
        result: The resolved cable.
        catalog: Resolves the cable product and connector pin rosters.
        config: Presentation flags; defaults to nothing shown.

    Returns:
        A ``CableDrawing`` ready for ``render_cable_svg``.

    Examples:
        >>> from schematika.cable.drawing_adapter import result_to_drawing
        >>> from schematika.cable.result import CableBuildResult
        >>> from schematika.catalog.identifiers import CableId, PartId
        >>> from schematika.catalog.cables import CableProductSpec
        >>> from schematika.catalog.result import ResolvedCatalog
        >>> cat = ResolvedCatalog(parts={}, connectors={},
        ...     cable_products={PartId("cab"): CableProductSpec(
        ...         part=PartId("cab"), conductor_count=0)},
        ...     devices={}, cable_instances={})
        >>> r = CableBuildResult(name=CableId("W1"), wires=(),
        ...     connectors=(), cable_product=PartId("cab"))
        >>> result_to_drawing(r, catalog=cat).cable.designator
        'W1'
    """
    product = catalog.lookup_cable_product(result.cable_product)
    # A cable is one physical length; CableDef.length is one scalar, so the
    # first wire's length_mm represents the whole cable (else the product default).
    lengths = [w.length_mm for w in result.wires if w.length_mm is not None]
    length = lengths[0] if lengths else (product.default_length_mm or 0.0)

    cable = CableDef(
        designator=str(result.name),
        wirecount=len(result.wires),
        wire_gauge=product.gauge_mm2 or 0.0,
        length=length,
        category=product.category or "cable",
        wire_colors=tuple(w.color or "" for w in result.wires),
    )

    show = config.show_pincount if config is not None else frozenset()
    connectors = tuple(
        CableConnector(
            designator=str(ci.name),
            pins=catalog.lookup_connector(ci.part).pins,
            show_pincount=ci.name in show,
        )
        for ci in result.connectors
    )

    connections = tuple(
        CableConnection(
            from_connector=_designator(w.source),
            from_pin=w.source.port_id,
            cable=str(result.name),
            wire=i,
            to_connector=_designator(w.target),
            to_pin=w.target.port_id,
        )
        for i, w in enumerate(result.wires, start=1)
    )

    return CableDrawing(cable=cable, connectors=connectors, connections=connections)
