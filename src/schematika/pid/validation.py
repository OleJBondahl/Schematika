"""
P&ID layout validation.

Checks a PIDDiagram for common layout issues: equipment overlap, text overlap,
page boundary violations, duplicate lines, and non-standard stroke weights.
"""

from schematika.core.geometry import Element
from schematika.core.primitives import Group, Line, Text
from schematika.core.renderer import calculate_bounds
from schematika.core.symbol import Symbol
from schematika.core.validation import ValidationResult
from schematika.pid.constants import (
    PID_EQUIPMENT_STROKE,
    PID_LINE_WEIGHT,
    PID_SIGNAL_LINE_WEIGHT,
)
from schematika.pid.diagram import PIDDiagram

_ALLOWED_STROKE_WIDTHS = {PID_LINE_WEIGHT, PID_EQUIPMENT_STROKE, PID_SIGNAL_LINE_WEIGHT}
_STROKE_TOLERANCE = 1e-6
_LINE_OVERLAP_TOLERANCE = 0.5


def _collect_elements(elements: list[Element], element_type: type) -> list:
    """Recursively collect elements of a given type from nested structures."""
    result = []
    for el in elements:
        if isinstance(el, element_type):
            result.append(el)
        if isinstance(el, Group):
            result.extend(_collect_elements(el.elements, element_type))
        elif isinstance(el, Symbol):
            result.extend(_collect_elements(el.elements, element_type))
    return result


def _boxes_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """Return True if two axis-aligned bounding boxes intersect."""
    a_min_x, a_min_y, a_max_x, a_max_y = a
    b_min_x, b_min_y, b_max_x, b_max_y = b
    return (
        a_min_x < b_max_x
        and a_max_x > b_min_x
        and a_min_y < b_max_y
        and a_max_y > b_min_y
    )


def _text_bbox(text: Text) -> tuple[float, float, float, float]:
    """Estimate axis-aligned bounding box for a Text element."""
    width = len(text.content) * text.font_size * 0.6
    height = text.font_size
    x = text.position.x
    y = text.position.y - height  # baseline at bottom

    if text.anchor == "middle":
        x -= width / 2
    elif text.anchor == "end":
        x -= width

    return (x, y, x + width, y + height)


def _check_equipment_overlap(
    equipment: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
) -> list[str]:
    errors: list[str] = []
    for i in range(len(equipment)):
        for j in range(i + 1, len(equipment)):
            if _boxes_overlap(bounds_cache[i], bounds_cache[j]):
                errors.append(
                    f"Equipment overlap: '{equipment[i].label}' and "
                    f"'{equipment[j].label}' bounding boxes intersect"
                )
    return errors


def _check_text_overlap(elements: list[Element]) -> list[str]:
    warnings: list[str] = []
    texts = _collect_elements(elements, Text)
    text_boxes = [_text_bbox(t) for t in texts]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if _boxes_overlap(text_boxes[i], text_boxes[j]):
                x = (texts[i].position.x + texts[j].position.x) / 2
                y = (texts[i].position.y + texts[j].position.y) / 2
                warnings.append(
                    f"Text overlap: '{texts[i].content}' and '{texts[j].content}' "
                    f"at ({x:.1f}, {y:.1f})"
                )
    return warnings


def _check_page_bounds(
    equipment: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
    page_width: float,
    page_height: float,
    margin: float,
) -> list[str]:
    errors: list[str] = []
    min_x, max_x = margin, page_width - margin
    min_y, max_y = margin, page_height - margin
    for sym, bounds in zip(equipment, bounds_cache, strict=True):
        bx_min, by_min, bx_max, by_max = bounds
        if bx_min < min_x or bx_max > max_x or by_min < min_y or by_max > max_y:
            errors.append(f"Equipment '{sym.label}' extends outside page boundary")
    return errors


def _check_duplicate_lines(elements: list[Element]) -> list[str]:
    warnings: list[str] = []
    lines = _collect_elements(elements, Line)
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            la, lb = lines[i], lines[j]
            forward = (
                abs(la.start.x - lb.start.x) <= _LINE_OVERLAP_TOLERANCE
                and abs(la.start.y - lb.start.y) <= _LINE_OVERLAP_TOLERANCE
                and abs(la.end.x - lb.end.x) <= _LINE_OVERLAP_TOLERANCE
                and abs(la.end.y - lb.end.y) <= _LINE_OVERLAP_TOLERANCE
            )
            reversed_ = (
                abs(la.start.x - lb.end.x) <= _LINE_OVERLAP_TOLERANCE
                and abs(la.start.y - lb.end.y) <= _LINE_OVERLAP_TOLERANCE
                and abs(la.end.x - lb.start.x) <= _LINE_OVERLAP_TOLERANCE
                and abs(la.end.y - lb.start.y) <= _LINE_OVERLAP_TOLERANCE
            )
            if forward or reversed_:
                warnings.append(
                    f"Duplicate line at ({la.start.x:.1f}, {la.start.y:.1f}) "
                    f"to ({la.end.x:.1f}, {la.end.y:.1f})"
                )
    return warnings


def _check_stroke_weights(elements: list[Element]) -> list[str]:
    warnings: list[str] = []
    for line in _collect_elements(elements, Line):
        width = line.style.stroke_width
        if not any(
            abs(width - allowed) < _STROKE_TOLERANCE
            for allowed in _ALLOWED_STROKE_WIDTHS
        ):
            warnings.append(
                f"Unexpected stroke width {width} on line at "
                f"({line.start.x:.1f}, {line.start.y:.1f})"
            )
    return warnings


def validate_pid(
    diagram: PIDDiagram,
    page_width: float = 297.0,
    page_height: float = 210.0,
    margin: float = 10.0,
) -> ValidationResult:
    """Validate a P&ID diagram layout.

    Args:
        diagram: The P&ID diagram to validate.
        page_width: Page width in mm (default A3 landscape: 297).
        page_height: Page height in mm (default A3 landscape: 210).
        margin: Minimum margin from page edge in mm (default: 10).

    Returns:
        A ValidationResult with any errors and warnings found.
    """
    equipment = diagram.equipment
    bounds_cache = [calculate_bounds(sym.elements) for sym in equipment]

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_check_equipment_overlap(equipment, bounds_cache))
    warnings.extend(_check_text_overlap(diagram.elements))
    errors.extend(
        _check_page_bounds(equipment, bounds_cache, page_width, page_height, margin)
    )
    warnings.extend(_check_duplicate_lines(diagram.elements))
    warnings.extend(_check_stroke_weights(diagram.elements))

    return ValidationResult(passed=len(errors) == 0, warnings=warnings, errors=errors)
