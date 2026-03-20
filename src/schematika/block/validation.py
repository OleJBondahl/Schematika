"""
Block diagram layout validation.

Checks a BlockDiagram for common layout issues: block overlap, text overlap,
page boundary violations, minimum spacing, and cable label collisions.
"""

from schematika.block.constants import BLOCK_MIN_GAP, BLOCK_TEXT_SIZE_CABLE
from schematika.block.diagram import BlockDiagram
from schematika.core.geometry import Element
from schematika.core.primitives import Group, Text
from schematika.core.renderer import calculate_bounds
from schematika.core.symbol import Symbol
from schematika.core.validation import ValidationResult

_CABLE_LABEL_TOLERANCE = 2.0  # mm — positions within this are "near-identical"
_TEXT_LINE_HEIGHT_FACTOR = 1.3


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
    """Estimate axis-aligned bounding box for a Text element.

    Supports multi-line text (content split on ``\\n``).  Height is
    ``lines * font_size * 1.3`` to account for line spacing.
    """
    lines = text.content.split("\n")
    longest = max(lines, key=len)
    width = len(longest) * text.font_size * 0.6
    height = len(lines) * text.font_size * _TEXT_LINE_HEIGHT_FACTOR
    x = text.position.x
    y = text.position.y - text.font_size  # baseline at bottom of first line

    if text.anchor == "middle":
        x -= width / 2
    elif text.anchor == "end":
        x -= width

    return (x, y, x + width, y + height)


def _check_block_overlap(
    blocks: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
) -> list[str]:
    errors: list[str] = []
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if _boxes_overlap(bounds_cache[i], bounds_cache[j]):
                errors.append(
                    f"Block overlap: '{blocks[i].label}' and "
                    f"'{blocks[j].label}' bounding boxes intersect"
                )
    return errors


def _check_page_bounds(
    blocks: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
    page_width: float,
    page_height: float,
    margin: float,
) -> list[str]:
    errors: list[str] = []
    min_x, max_x = margin, page_width - margin
    min_y, max_y = margin, page_height - margin
    for sym, bounds in zip(blocks, bounds_cache, strict=True):
        bx_min, by_min, bx_max, by_max = bounds
        if bx_min < min_x or bx_max > max_x or by_min < min_y or by_max > max_y:
            errors.append(f"Block '{sym.label}' extends outside page boundary")
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


def _check_minimum_spacing(
    blocks: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
) -> list[str]:
    warnings: list[str] = []
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            ai_min_x, ai_min_y, ai_max_x, ai_max_y = bounds_cache[i]
            aj_min_x, aj_min_y, aj_max_x, aj_max_y = bounds_cache[j]

            # Compute gap between bounding boxes on each axis
            gap_x = max(0, max(aj_min_x - ai_max_x, ai_min_x - aj_max_x))
            gap_y = max(0, max(aj_min_y - ai_max_y, ai_min_y - aj_max_y))

            # If they overlap on one axis, the gap is along the other axis only.
            # If they overlap on both axes, gap is 0 (handled by overlap check).
            gap = max(gap_x, gap_y)
            if 0 < gap < BLOCK_MIN_GAP:
                warnings.append(
                    f"Minimum spacing: '{blocks[i].label}' and '{blocks[j].label}' "
                    f"are {gap:.1f}mm apart (minimum: {BLOCK_MIN_GAP}mm)"
                )
    return warnings


def _check_cable_label_collision(elements: list[Element]) -> list[str]:
    warnings: list[str] = []
    texts = _collect_elements(elements, Text)
    cable_labels = [t for t in texts if t.font_size == BLOCK_TEXT_SIZE_CABLE]
    for i in range(len(cable_labels)):
        for j in range(i + 1, len(cable_labels)):
            dx = abs(cable_labels[i].position.x - cable_labels[j].position.x)
            dy = abs(cable_labels[i].position.y - cable_labels[j].position.y)
            if dx <= _CABLE_LABEL_TOLERANCE and dy <= _CABLE_LABEL_TOLERANCE:
                warnings.append(
                    f"Cable label collision: '{cable_labels[i].content}' and "
                    f"'{cable_labels[j].content}' at near-identical positions"
                )
    return warnings


def validate_block_diagram(
    diagram: BlockDiagram,
    page_width: float = 420.0,
    page_height: float = 297.0,
    margin: float = 10.0,
) -> ValidationResult:
    """Validate a block diagram layout.

    Args:
        diagram: The block diagram to validate.
        page_width: Page width in mm (default A3 landscape: 420).
        page_height: Page height in mm (default A3 landscape: 297).
        margin: Minimum margin from page edge in mm (default: 10).

    Returns:
        A ValidationResult with any errors and warnings found.
    """
    blocks = diagram.blocks
    bounds_cache = [calculate_bounds(sym.elements) for sym in blocks]

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_check_block_overlap(blocks, bounds_cache))
    errors.extend(
        _check_page_bounds(blocks, bounds_cache, page_width, page_height, margin)
    )
    warnings.extend(_check_text_overlap(diagram.elements))
    warnings.extend(_check_minimum_spacing(blocks, bounds_cache))
    warnings.extend(_check_cable_label_collision(diagram.elements))

    return ValidationResult(passed=len(errors) == 0, warnings=warnings, errors=errors)
