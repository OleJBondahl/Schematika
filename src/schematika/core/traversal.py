"""Element tree traversal utilities."""

from collections.abc import Callable

from schematika._purity import pure
from schematika.core.geometry import Element
from schematika.core.primitives import Group
from schematika.core.symbol import Symbol


@pure
def walk_elements(
    root: Element | list[Element], visitor: Callable[[Element], None]
) -> None:
    """Recursively visit all elements in a Group/Symbol tree."""
    if isinstance(root, list):
        for elem in root:
            walk_elements(elem, visitor)
        return
    visitor(root)
    if isinstance(root, (Group, Symbol)):
        for child in root.elements:
            walk_elements(child, visitor)


@pure
def collect_by_type(root: Element | list[Element], target_type: type) -> list:
    """Collect all elements matching a type from an element tree."""
    result = []

    def _collect(elem):
        if isinstance(elem, target_type):
            result.append(elem)

    walk_elements(root, _collect)
    return result
