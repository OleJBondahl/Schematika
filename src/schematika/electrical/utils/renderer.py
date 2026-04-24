"""Re-export shim for SVG rendering helpers.

Pure helpers live in ``schematika.core.renderer``; impure XML/IO
builders live in ``schematika.rendering.svg``.
"""

from schematika.core.renderer import (  # noqa: F401
    _style_to_str,
    calculate_bounds,
)
from schematika.rendering.svg import (  # noqa: F401
    _render_element,
    render_to_svg,
    save_svg,
    to_xml_element,
)
