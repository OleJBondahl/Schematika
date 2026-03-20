"""
Block diagram constants — visual weights, spacing, and text sizes.

All dimensional constants are derived from :data:`GRID_SIZE` (5 mm) so that
proportions remain consistent with the electrical schematic and P&ID modules.

Design Rules
------------

1. **Line weight hierarchy** — four cable weight classes distinguish power,
   control, signal, and Ethernet connections visually.
2. **Color coding** — each cable type has a distinct color for quick
   identification on screen and in color prints.
3. **Spacing** — minimum gap and clearance constants prevent overlapping
   blocks and cable crossings.
"""

from schematika.core.constants import (
    GRID_SIZE,
    LINE_WIDTH_THIN,
    TEXT_FONT_FAMILY,
    TEXT_SIZE_MAIN,
)

__all__ = [
    "GRID_SIZE",
    "LINE_WIDTH_THIN",
    "TEXT_FONT_FAMILY",
    "TEXT_SIZE_MAIN",
    "BLOCK_DEFAULT_WIDTH",
    "BLOCK_DEFAULT_HEIGHT",
    "BLOCK_STROKE_WIDTH",
    "CABLE_WEIGHT_POWER",
    "CABLE_WEIGHT_CONTROL",
    "CABLE_WEIGHT_SIGNAL",
    "CABLE_WEIGHT_ETHERNET",
    "CABLE_ETHERNET_DASH",
    "CABLE_COLOR_AC_POWER",
    "CABLE_COLOR_DC_CONTROL",
    "CABLE_COLOR_SIGNAL",
    "CABLE_COLOR_ETHERNET",
    "BLOCK_TEXT_SIZE_LABEL",
    "BLOCK_TEXT_SIZE_CABLE",
    "BLOCK_TEXT_SIZE_NOTE",
    "BLOCK_MIN_GAP",
    "BLOCK_CABLE_CLEARANCE",
    "BLOCK_PORT_OFFSET",
    "LEGEND_LINE_SAMPLE_LENGTH",
    "LEGEND_ENTRY_HEIGHT",
]

# Block dimensions (mm)
BLOCK_DEFAULT_WIDTH = GRID_SIZE * 8  # 40mm
BLOCK_DEFAULT_HEIGHT = GRID_SIZE * 5  # 25mm
BLOCK_STROKE_WIDTH = GRID_SIZE * 0.1  # 0.5mm

# Cable line weights (mm)
CABLE_WEIGHT_POWER = GRID_SIZE * 0.2  # 1.0mm — AC/DC power cables
CABLE_WEIGHT_CONTROL = GRID_SIZE * 0.12  # 0.6mm — control cables
CABLE_WEIGHT_SIGNAL = GRID_SIZE * 0.07  # 0.35mm — signal/instrument cables
CABLE_WEIGHT_ETHERNET = GRID_SIZE * 0.1  # 0.5mm — Ethernet/data cables

# Cable dash patterns (grid-relative)
CABLE_ETHERNET_DASH = f"{GRID_SIZE * 0.4},{GRID_SIZE * 0.2}"

# Cable colors
CABLE_COLOR_AC_POWER = "magenta"
CABLE_COLOR_DC_CONTROL = "#CCCC00"
CABLE_COLOR_SIGNAL = "blue"
CABLE_COLOR_ETHERNET = "green"

# Text sizes (mm)
BLOCK_TEXT_SIZE_LABEL = GRID_SIZE * 0.6  # 3.0mm — block label text
BLOCK_TEXT_SIZE_CABLE = GRID_SIZE * 0.5  # 2.5mm — cable label text
BLOCK_TEXT_SIZE_NOTE = GRID_SIZE * 0.5  # 2.5mm — legend/note text

# Spacing constants (mm)
BLOCK_MIN_GAP = GRID_SIZE * 4  # 20mm — minimum gap between blocks
BLOCK_CABLE_CLEARANCE = GRID_SIZE * 2  # 10mm — minimum cable-to-block clearance
BLOCK_PORT_OFFSET = GRID_SIZE * 0.5  # 2.5mm — port inset from block edge

# Legend constants (mm)
LEGEND_LINE_SAMPLE_LENGTH = GRID_SIZE * 4  # 20mm — sample line in legend
LEGEND_ENTRY_HEIGHT = GRID_SIZE * 1.5  # 7.5mm — vertical spacing per entry
