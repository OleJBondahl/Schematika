"""P&ID layout validation.

Checks a PIDDiagram for common layout issues: equipment overlap, text overlap,
page boundary violations, duplicate lines, and non-standard stroke weights.
"""

from schematika.core.geometry import Element
from schematika.core.primitives import Line
from schematika.core.renderer import calculate_bounds
from schematika.core.symbol import Symbol
from schematika.core.validation import (
    ValidationResult,
    boxes_overlap,
    check_page_bounds,
    check_text_overlap,
    collect_elements,
)
from schematika.pid.constants import (
    PID_EQUIPMENT_STROKE,
    PID_LINE_WEIGHT,
    PID_SIGNAL_LINE_WEIGHT,
)
from schematika.pid.diagram import PIDDiagram

_ALLOWED_STROKE_WIDTHS = {PID_LINE_WEIGHT, PID_EQUIPMENT_STROKE, PID_SIGNAL_LINE_WEIGHT}
_STROKE_TOLERANCE = 1e-6
_LINE_OVERLAP_TOLERANCE = 0.5


def _check_equipment_overlap(
    equipment: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
) -> list[str]:
    errors: list[str] = []
    for i in range(len(equipment)):
        for j in range(i + 1, len(equipment)):
            if boxes_overlap(bounds_cache[i], bounds_cache[j]):
                errors.append(
                    f"Equipment overlap: '{equipment[i].label}' and "
                    f"'{equipment[j].label}' bounding boxes intersect"
                )
    return errors


def _check_duplicate_lines(elements: list[Element]) -> list[str]:
    warnings: list[str] = []
    lines = collect_elements(elements, Line)
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
    for line in collect_elements(elements, Line):
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
    warnings.extend(check_text_overlap(diagram.elements))
    errors.extend(
        check_page_bounds(
            equipment,
            bounds_cache,
            page_width,
            page_height,
            margin,
            label_fn=lambda sym: f"Equipment {sym.label}",
        )
    )
    warnings.extend(_check_duplicate_lines(diagram.elements))
    warnings.extend(_check_stroke_weights(diagram.elements))

    return ValidationResult(passed=len(errors) == 0, warnings=warnings, errors=errors)
