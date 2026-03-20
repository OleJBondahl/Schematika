"""
Block diagram constants -- visual weights, spacing, and text sizes.

All dimensional constants are derived from :data:`GRID_SIZE` (5 mm) so that
proportions remain consistent with the electrical schematic and P&ID modules.
"""

from schematika.core.constants import GRID_SIZE

__all__ = [
    "GRID_SIZE",
    "BLOCK_GAP",
    "CONTAINER_PADDING",
    "BLOCK_DEFAULT_HEIGHT",
    "BLOCK_MIN_WIDTH",
    "BLOCK_STROKE_WIDTH",
    "CABLE_BUNDLE_SPACING",
    "CABLE_LABEL_OFFSET",
    "BLOCK_LABEL_SIZE",
    "TAG_LABEL_SIZE",
    "NOTE_TEXT_SIZE",
    "CABLE_WEIGHT_POWER",
    "CABLE_WEIGHT_CONTROL",
    "CABLE_WEIGHT_SIGNAL",
    "CABLE_WEIGHT_ETHERNET",
    "CABLE_ETHERNET_DASH",
    "CABLE_COLOR_AC_POWER",
    "CABLE_COLOR_DC_CONTROL",
    "CABLE_COLOR_SIGNAL",
    "CABLE_COLOR_ETHERNET",
    "LEGEND_LINE_SAMPLE_LENGTH",
    "LEGEND_ENTRY_HEIGHT",
]

# Layout
BLOCK_GAP = GRID_SIZE * 3  # 15mm between sibling blocks
CONTAINER_PADDING = GRID_SIZE * 2  # 10mm inside containers
BLOCK_DEFAULT_HEIGHT = GRID_SIZE * 5  # 25mm for leaf blocks
BLOCK_MIN_WIDTH = GRID_SIZE * 8  # 40mm minimum block width
BLOCK_STROKE_WIDTH = GRID_SIZE * 0.1  # 0.5mm

# Cable
CABLE_BUNDLE_SPACING = GRID_SIZE * 0.6  # 3mm between parallel cables in a bundle
CABLE_LABEL_OFFSET = GRID_SIZE * 0.4  # 2mm label offset from cable line

# Text
BLOCK_LABEL_SIZE = GRID_SIZE * 0.6  # 3mm block label
TAG_LABEL_SIZE = GRID_SIZE * 0.5  # 2.5mm device tag labels
NOTE_TEXT_SIZE = GRID_SIZE * 0.5  # 2.5mm notes and abbreviations

# Cable line weights (mm)
CABLE_WEIGHT_POWER = GRID_SIZE * 0.2  # 1.0mm -- AC/DC power cables
CABLE_WEIGHT_CONTROL = GRID_SIZE * 0.12  # 0.6mm -- control cables
CABLE_WEIGHT_SIGNAL = GRID_SIZE * 0.07  # 0.35mm -- signal/instrument cables
CABLE_WEIGHT_ETHERNET = GRID_SIZE * 0.1  # 0.5mm -- Ethernet/data cables

# Cable dash patterns (grid-relative)
CABLE_ETHERNET_DASH = f"{GRID_SIZE * 0.4},{GRID_SIZE * 0.2}"

# Cable colors
CABLE_COLOR_AC_POWER = "magenta"
CABLE_COLOR_DC_CONTROL = "#CCCC00"
CABLE_COLOR_SIGNAL = "blue"
CABLE_COLOR_ETHERNET = "green"

# Legend constants (mm)
LEGEND_LINE_SAMPLE_LENGTH = GRID_SIZE * 4  # 20mm -- sample line in legend
LEGEND_ENTRY_HEIGHT = GRID_SIZE * 1.5  # 7.5mm -- vertical spacing per entry
