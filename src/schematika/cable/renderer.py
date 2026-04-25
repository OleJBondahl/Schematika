"""WireViz adapter: convert CableDrawing to SVG string.

This is the only file in the cable module that imports wireviz.
If the rendering backend ever needs to be swapped, only this file changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.cable.model import CableConnector, CableDef, CableDrawing


def _connector_kwargs(connector: CableConnector) -> dict:
    """Build keyword arguments for Harness.add_connector()."""
    kwargs: dict = {
        "pins": list(connector.pins),
        "show_pincount": connector.show_pincount,
    }
    if connector.type:
        kwargs["type"] = connector.type
    if connector.subtype:
        kwargs["subtype"] = connector.subtype
    if connector.style:
        kwargs["style"] = connector.style
    if connector.notes:
        kwargs["notes"] = connector.notes
    if connector.loops:
        kwargs["loops"] = [list(pair) for pair in connector.loops]
    return kwargs


def _cable_kwargs(cable: CableDef) -> dict:
    """Build keyword arguments for Harness.add_cable()."""
    kwargs: dict = {"wirecount": cable.wirecount}
    if cable.wire_gauge:
        kwargs["gauge"] = cable.wire_gauge
        kwargs["gauge_unit"] = cable.gauge_unit
    if cable.length:
        kwargs["length"] = cable.length
    if cable.wire_colors:
        kwargs["colors"] = list(cable.wire_colors)
    if cable.category and cable.category != "cable":
        kwargs["category"] = cable.category
    if cable.shield:
        kwargs["shield"] = cable.shield
    if cable.notes:
        kwargs["notes"] = cable.notes
    return kwargs


def render_cable_svg(drawing: CableDrawing) -> str:
    """Convert a CableDrawing to an SVG string via WireViz Harness API.

    Forces a fixed 8-inch width on every output SVG so that drawings render
    at a consistent scale regardless of connector count.

    Args:
        drawing: A fully constructed ``CableDrawing`` (e.g. from
            ``build_cable_drawings`` or ``build_inter_device_drawings``).

    Returns:
        str: SVG markup ready to write to a file or embed in HTML.

    Raises:
        ImportError: If ``wireviz`` is not installed (optional dependency;
            install via ``uv sync --all-extras``).

    Examples:
        >>> from schematika.cable.renderer import render_cable_svg
        >>> from schematika.cable.model import (
        ...     CableConnection, CableConnector, CableDef, CableDrawing)
        >>> cable = CableDef(designator="W001", wirecount=1,
        ...                  wire_colors=("WH",))
        >>> src = CableConnector(designator="SRC", pins=("1",))
        >>> dst = CableConnector(designator="DST", pins=("1",))
        >>> conn = CableConnection(from_connector="SRC", from_pin="1",
        ...                        cable="W001", wire=1,
        ...                        to_connector="DST", to_pin="1")
        >>> drawing = CableDrawing(cable=cable, connectors=(src, dst),
        ...                        connections=(conn,))
        >>> svg = render_cable_svg(drawing)
        >>> svg.startswith("<?xml") or "<svg" in svg
        True
    """
    from wireviz.DataClasses import (
        Metadata,
        Options,
        Tweak,
    )
    from wireviz.Harness import Harness

    # Force all graphs to a fixed width (8 inches) so SVGs render
    # at consistent scale regardless of connector count.
    # The "!" suffix forces exact size; large height allows vertical growth.
    tweak = Tweak(append='size="8,100!" ratio="compress"')
    harness = Harness(metadata=Metadata(), options=Options(), tweak=tweak)

    for connector in drawing.connectors:
        harness.add_connector(connector.designator, **_connector_kwargs(connector))

    harness.add_cable(drawing.cable.designator, **_cable_kwargs(drawing.cable))

    for conn in drawing.connections:
        harness.connect(
            conn.from_connector,
            conn.from_pin,
            conn.cable,
            conn.wire,
            conn.to_connector,
            conn.to_pin,
        )

    return harness.svg
