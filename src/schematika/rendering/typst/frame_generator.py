"""A3 drawing frame generator for IEC 60617 electrical schematics.

Generates an SVG border frame with grid system (columns 1-8, rows A-F)
suitable for A3 landscape technical drawings.
"""

from schematika.electrical.model.core import Point, Style
from schematika.electrical.model.primitives import Line, Text
from schematika.electrical.system.system import Circuit

# A3 Dimensions in mm
A3_WIDTH = 420
A3_HEIGHT = 297

GRID_WIDTH = 5
MARGIN_ALL = GRID_WIDTH

# Inner frame dimensions (content area)
INNER_FRAME_X1 = MARGIN_ALL + GRID_WIDTH  # 10mm
INNER_FRAME_Y1 = MARGIN_ALL + GRID_WIDTH  # 10mm
INNER_FRAME_X2 = A3_WIDTH - MARGIN_ALL - GRID_WIDTH  # 410mm
INNER_FRAME_Y2 = A3_HEIGHT - MARGIN_ALL - GRID_WIDTH  # 287mm

# Content area dimensions (for clipping in Typst)
CONTENT_WIDTH = INNER_FRAME_X2 - INNER_FRAME_X1  # 400mm
CONTENT_HEIGHT = INNER_FRAME_Y2 - INNER_FRAME_Y1  # 277mm


def generate_frame(font_family: str = "Times New Roman") -> Circuit:
    """Generate an A3 landscape drawing frame with grid system.

    The frame consists of:
    - Outer border at 5mm margin from page edge
    - Inner border at 10mm from page edge
    - Column grid 1-8 (horizontal) between outer and inner borders
    - Row grid A-F (vertical) between outer and inner borders

    Args:
        font_family: Font for grid labels. Default "Times New Roman".

    Returns:
        Circuit: A Circuit containing the frame elements.
    """
    outer_x1 = MARGIN_ALL
    outer_y1 = MARGIN_ALL
    outer_x2 = A3_WIDTH - MARGIN_ALL
    outer_y2 = A3_HEIGHT - MARGIN_ALL

    ix1 = outer_x1 + GRID_WIDTH
    iy1 = outer_y1 + GRID_WIDTH
    ix2 = outer_x2 - GRID_WIDTH
    iy2 = outer_y2 - GRID_WIDTH

    circuit = Circuit()
    style = Style(stroke="black", stroke_width=0.18)

    def draw_rect(x1: float, y1: float, x2: float, y2: float) -> None:
        lines = [
            Line(Point(x1, y1), Point(x2, y1), style),
            Line(Point(x2, y1), Point(x2, y2), style),
            Line(Point(x2, y2), Point(x1, y2), style),
            Line(Point(x1, y2), Point(x1, y1), style),
        ]
        circuit.elements.extend(lines)

    draw_rect(outer_x1, outer_y1, outer_x2, outer_y2)
    draw_rect(ix1, iy1, ix2, iy2)

    # Grid system
    cols = 8
    frame_width = outer_x2 - outer_x1
    col_width = frame_width / cols

    rows = 6
    frame_height = outer_y2 - outer_y1
    row_height = frame_height / rows

    text_style = Style(stroke="none", fill="black", font_family=font_family)

    # Horizontal grid (columns 1-8, top and bottom)
    for i in range(cols):
        x_start = outer_x1 + (i * col_width)
        x_mid = x_start + (col_width / 2)
        x_end = x_start + col_width

        label = str(i + 1)

        circuit.elements.append(Line(Point(x_end, outer_y1), Point(x_end, iy1), style))
        circuit.elements.append(Line(Point(x_end, iy2), Point(x_end, outer_y2), style))

        circuit.elements.append(
            Text(
                content=label,
                position=Point(x_mid, outer_y1 + GRID_WIDTH / 2 + 1.2),
                style=text_style,
                font_size=3.5,
                anchor="middle",
            )
        )
        circuit.elements.append(
            Text(
                content=label,
                position=Point(x_mid, outer_y2 - GRID_WIDTH / 2 + 1.2),
                style=text_style,
                font_size=3.5,
                anchor="middle",
            )
        )

    # Vertical grid (rows A-F, left and right)
    for i in range(rows):
        y_start = outer_y1 + (i * row_height)
        y_mid = y_start + (row_height / 2)
        y_end = y_start + row_height

        label = chr(ord("A") + i)

        circuit.elements.append(Line(Point(outer_x1, y_end), Point(ix1, y_end), style))
        circuit.elements.append(Line(Point(ix2, y_end), Point(outer_x2, y_end), style))

        circuit.elements.append(
            Text(
                content=label,
                position=Point(outer_x1 + GRID_WIDTH / 2, y_mid + 1.2),
                style=text_style,
                font_size=3.5,
                anchor="middle",
            )
        )
        circuit.elements.append(
            Text(
                content=label,
                position=Point(outer_x2 - GRID_WIDTH / 2, y_mid + 1.2),
                style=text_style,
                font_size=3.5,
                anchor="middle",
            )
        )

    return circuit
