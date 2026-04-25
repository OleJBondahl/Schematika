"""Shared validation helpers used by all diagram validators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import deal

from schematika._purity import pure
from schematika.core.primitives import Text
from schematika.core.traversal import collect_by_type

if TYPE_CHECKING:
    from collections.abc import Callable

    from schematika.core.geometry import Element

TEXT_WIDTH_FACTOR = 0.6
TEXT_LINE_HEIGHT_FACTOR = 1.3


@dataclass
class ValidationResult:
    """Result of diagram layout validation."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@pure
def collect_elements(elements: list[Element], element_type: type) -> list:
    """Recursively collect elements of a given type from nested structures."""
    return collect_by_type(elements, element_type)


@deal.pure
def boxes_overlap(
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


@deal.pure
def text_bbox(text: Text) -> tuple[float, float, float, float]:
    """Estimate axis-aligned bounding box for a Text element.

    Handles multi-line text (content with newlines).
    """
    lines = text.content.split("\n")
    longest = max(lines, key=len)
    width = len(longest) * text.font_size * TEXT_WIDTH_FACTOR
    height = len(lines) * text.font_size * TEXT_LINE_HEIGHT_FACTOR
    x = text.position.x
    y = text.position.y - text.font_size

    if text.anchor == "middle":
        x -= width / 2
    elif text.anchor == "end":
        x -= width

    return (x, y, x + width, y + height)


@pure
def check_text_overlap(elements: list[Element]) -> list[str]:
    """Return warnings for pairwise text overlap among all Text elements."""
    warnings: list[str] = []
    texts = collect_elements(elements, Text)
    text_boxes = [text_bbox(t) for t in texts]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if boxes_overlap(text_boxes[i], text_boxes[j]):
                x = (texts[i].position.x + texts[j].position.x) / 2
                y = (texts[i].position.y + texts[j].position.y) / 2
                warnings.append(
                    f"Text overlap: '{texts[i].content}' and '{texts[j].content}' "
                    f"at ({x:.1f}, {y:.1f})"
                )
    return warnings


@deal.pure
def check_page_bounds(
    items: list[Any],
    bounds: list[tuple[float, float, float, float]],
    page_width: float,
    page_height: float,
    margin: float,
    label_fn: Callable[[Any], str] = lambda x: x.label,
) -> list[str]:
    """Return errors for items whose bounds extend outside the page boundary."""
    errors: list[str] = []
    min_x, max_x = margin, page_width - margin
    min_y, max_y = margin, page_height - margin
    for item, bbox in zip(items, bounds, strict=True):
        bx_min, by_min, bx_max, by_max = bbox
        if bx_min < min_x or bx_max > max_x or by_min < min_y or by_max > max_y:
            errors.append(f"'{label_fn(item)}' extends outside page boundary")
    return errors
