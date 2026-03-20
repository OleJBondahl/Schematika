"""
Block diagram layout validation.

Checks a BlockDiagram for common layout issues: block overlap, text overlap,
page boundary violations, minimum spacing, and cable label collisions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from schematika.block.constants import BLOCK_GAP, NOTE_TEXT_SIZE
from schematika.core.geometry import Element
from schematika.core.primitives import Group, Text
from schematika.core.symbol import Symbol
from schematika.core.validation import ValidationResult

if TYPE_CHECKING:
    from schematika.block.diagram import BlockDiagram
    from schematika.block.model import Block

_CABLE_LABEL_TOLERANCE = 2.0  # mm
_TEXT_LINE_HEIGHT_FACTOR = 1.3


def _block_bbox(b: "Block") -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) for a Block."""
    return (b.x, b.y, b.x + b.width, b.y + b.height)


def _boxes_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    a_min_x, a_min_y, a_max_x, a_max_y = a
    b_min_x, b_min_y, b_max_x, b_max_y = b
    return (
        a_min_x < b_max_x
        and a_max_x > b_min_x
        and a_min_y < b_max_y
        and a_max_y > b_min_y
    )


def _text_bbox(text: Text) -> tuple[float, float, float, float]:
    lines = text.content.split("\n")
    longest = max(lines, key=len)
    width = len(longest) * text.font_size * 0.6
    height = len(lines) * text.font_size * _TEXT_LINE_HEIGHT_FACTOR
    x = text.position.x
    y = text.position.y - text.font_size

    if text.anchor == "middle":
        x -= width / 2
    elif text.anchor == "end":
        x -= width

    return (x, y, x + width, y + height)


def _collect_elements(elements: list[Element], element_type: type) -> list:
    result = []
    for el in elements:
        if isinstance(el, element_type):
            result.append(el)
        if isinstance(el, Group):
            result.extend(_collect_elements(el.elements, element_type))
        elif isinstance(el, Symbol):
            result.extend(_collect_elements(el.elements, element_type))
    return result


def _is_child_of(a: "Block", b: "Block") -> bool:
    """Return True if a is a descendant of b."""
    p = a.parent
    while p is not None:
        if p is b:
            return True
        p = p.parent
    return False


def _check_block_overlap(blocks: list["Block"]) -> list[str]:
    errors: list[str] = []
    bboxes = [_block_bbox(b) for b in blocks]
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            # Skip parent-child pairs (children are inside parents)
            if _is_child_of(blocks[i], blocks[j]) or _is_child_of(blocks[j], blocks[i]):
                continue
            # Skip siblings with same parent (handled by layout)
            if blocks[i].parent is blocks[j].parent and blocks[i].parent is not None:
                continue
            if _boxes_overlap(bboxes[i], bboxes[j]):
                errors.append(
                    f"Block overlap: '{blocks[i].label}' and "
                    f"'{blocks[j].label}' bounding boxes intersect"
                )
    return errors


def _check_page_bounds(
    blocks: list["Block"],
    page_width: float,
    page_height: float,
    margin: float,
) -> list[str]:
    errors: list[str] = []
    min_x, max_x = margin, page_width - margin
    min_y, max_y = margin, page_height - margin
    for b in blocks:
        bbox = _block_bbox(b)
        if bbox[0] < min_x or bbox[2] > max_x or bbox[1] < min_y or bbox[3] > max_y:
            errors.append(f"Block '{b.label}' extends outside page boundary")
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


def _check_minimum_spacing(blocks: list["Block"]) -> list[str]:
    warnings: list[str] = []
    bboxes = [_block_bbox(b) for b in blocks]
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if _is_child_of(blocks[i], blocks[j]) or _is_child_of(blocks[j], blocks[i]):
                continue
            ai = bboxes[i]
            aj = bboxes[j]
            gap_x = max(0, max(aj[0] - ai[2], ai[0] - aj[2]))
            gap_y = max(0, max(aj[1] - ai[3], ai[1] - aj[3]))
            gap = max(gap_x, gap_y)
            if 0 < gap < BLOCK_GAP:
                warnings.append(
                    f"Minimum spacing: '{blocks[i].label}' and '{blocks[j].label}' "
                    f"are {gap:.1f}mm apart (minimum: {BLOCK_GAP}mm)"
                )
    return warnings


def _check_cable_label_collision(elements: list[Element]) -> list[str]:
    warnings: list[str] = []
    texts = _collect_elements(elements, Text)
    cable_labels = [t for t in texts if t.font_size == NOTE_TEXT_SIZE]
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
    diagram: "BlockDiagram",
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
    # elements triggers layout resolution (mutates block x/y), so call first
    rendered_elements = diagram.elements
    blocks = diagram.blocks

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_check_block_overlap(blocks))
    errors.extend(_check_page_bounds(blocks, page_width, page_height, margin))
    warnings.extend(_check_text_overlap(rendered_elements))
    warnings.extend(_check_minimum_spacing(blocks))
    warnings.extend(_check_cable_label_collision(rendered_elements))

    return ValidationResult(passed=len(errors) == 0, warnings=warnings, errors=errors)
