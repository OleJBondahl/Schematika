"""
Data structures for block diagram cable styles and port definitions.

Provides frozen dataclasses for cable visual styles and block connection
ports, plus predefined style constants for common cable types.
"""

from __future__ import annotations

from dataclasses import dataclass

from schematika.block.constants import (
    CABLE_COLOR_AC_POWER,
    CABLE_COLOR_DC_CONTROL,
    CABLE_COLOR_ETHERNET,
    CABLE_COLOR_SIGNAL,
    CABLE_ETHERNET_DASH,
    CABLE_WEIGHT_CONTROL,
    CABLE_WEIGHT_ETHERNET,
    CABLE_WEIGHT_POWER,
    CABLE_WEIGHT_SIGNAL,
)

__all__ = [
    "CableStyle",
    "BlockPort",
    "AC_POWER",
    "DC_CONTROL",
    "SIGNAL_CABLE",
    "ETHERNET",
    "CABLE_TYPE_STYLES",
]


@dataclass(frozen=True)
class CableStyle:
    """Visual style for a cable connection line.

    Attributes:
        stroke_width: Line width in mm.
        color: CSS stroke color string.
        dash_pattern: SVG ``stroke-dasharray`` value, or ``None`` for solid.
    """

    stroke_width: float
    color: str = "black"
    dash_pattern: str | None = None


# ---------------------------------------------------------------------------
# Predefined cable styles
# ---------------------------------------------------------------------------

AC_POWER = CableStyle(CABLE_WEIGHT_POWER, CABLE_COLOR_AC_POWER)
DC_CONTROL = CableStyle(CABLE_WEIGHT_CONTROL, CABLE_COLOR_DC_CONTROL)
SIGNAL_CABLE = CableStyle(CABLE_WEIGHT_SIGNAL, CABLE_COLOR_SIGNAL)
ETHERNET = CableStyle(CABLE_WEIGHT_ETHERNET, CABLE_COLOR_ETHERNET, CABLE_ETHERNET_DASH)

CABLE_TYPE_STYLES: dict[str, CableStyle] = {
    "power_ac": AC_POWER,
    "power_dc": DC_CONTROL,
    "signal": SIGNAL_CABLE,
    "ethernet": ETHERNET,
    "control": DC_CONTROL,
}


@dataclass(frozen=True)
class BlockPort:
    """A connection point on a block's edge.

    Attributes:
        id: Unique identifier for this port (e.g. ``"left"``, ``"eth1"``).
        side: Which edge of the block: ``"top"``, ``"bottom"``, ``"left"``,
              or ``"right"``.
        position: Fractional position along that side, from ``0.0`` (start)
                  to ``1.0`` (end).  ``0.5`` is the center.
    """

    id: str
    side: str  # "top", "bottom", "left", "right"
    position: float  # 0.0-1.0 along that side
