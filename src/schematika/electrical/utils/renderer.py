"""Re-export shim for SVG rendering helpers.

Pure helpers live in ``schematika.core.renderer``; impure XML/IO
builders live in ``schematika.rendering.svg``.
"""

from schematika.core.renderer import (
    _style_to_str,
    calculate_bounds,
)
from schematika.rendering.svg import (
    _render_element,
    render_to_svg,
    save_svg,
    to_xml_element,
)

__all__ = [
    "_render_element",
    "_style_to_str",
    "calculate_bounds",
    "render_to_svg",
    "save_svg",
    "to_xml_element",
]
