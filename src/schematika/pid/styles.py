"""Shared styles for PID symbol factories."""

from schematika.core.constants import TEXT_FONT_FAMILY
from schematika.core.geometry import Style
from schematika.pid.constants import PID_EQUIPMENT_STROKE, PID_LINE_WEIGHT

PIPE_STYLE = Style(stroke="black", stroke_width=PID_LINE_WEIGHT, fill="none")
BODY_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="none")
FILL_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="black")
TEXT_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)
