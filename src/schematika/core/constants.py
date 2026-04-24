"""Geometric and visual constants for the core rendering infrastructure.

These constants are domain-neutral (no electrical semantics) and are used
by core/ modules such as transform, renderer, and parts.
"""

# Grid System
GRID_SIZE = 5.0  # mm, Base grid unit

# Geometry
TERMINAL_RADIUS = 0.25 * GRID_SIZE  # 1.25mm
LINE_WIDTH_THIN = 0.05 * GRID_SIZE  # 0.25mm

# Text & Fonts
TEXT_FONT_FAMILY = "Times New Roman"
TEXT_SIZE_MAIN = GRID_SIZE  # 5.0mm
TEXT_OFFSET_X = -GRID_SIZE  # -5.0mm

TERMINAL_TEXT_SIZE = (
    0.85 * GRID_SIZE
)  # 4.25mm (smaller to avoid collision with pin numbers)
TERMINAL_TEXT_OFFSET_X = -1.7 * GRID_SIZE  # -8.5mm (same side as pin number)
TERMINAL_TEXT_OFFSET_X_CLOSE = -0.6 * GRID_SIZE  # -3.0mm (when pin is on opposite side)

TEXT_FONT_FAMILY_AUX = "Times New Roman"
TEXT_SIZE_PIN = 0.7 * GRID_SIZE  # 3.5mm
PIN_LABEL_OFFSET_X = 0.3 * GRID_SIZE  # 1.5mm
PIN_LABEL_OFFSET_Y_ADJUST = 0.0  # mm, adjustment for up/down ports

# Layout
DEFAULT_POLE_SPACING = 2 * GRID_SIZE  # 10.0mm

# Colors
COLOR_BLACK = "black"
COLOR_WHITE = "white"

# Document Defaults
DEFAULT_DOC_WIDTH = "210mm"
DEFAULT_DOC_HEIGHT = "297mm"
