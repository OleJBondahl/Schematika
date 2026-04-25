"""Symbol and Port data classes for the core domain model.

Provides ``Port`` and ``Symbol`` (an ``Element`` subclass carrying ports and
a render callback), imported from ``core/geometry.py``.
"""

from collections.abc import Callable
from dataclasses import dataclass

from schematika.core.geometry import Element, Point, Vector


@dataclass(frozen=True)
class Port:
    """A connection point on a symbol.

    Attributes:
        id (str): Unique identifier within the symbol (e.g., "1", "A1", "13").
        position (Point): The absolute position of the port.
        direction (Vector): The direction a wire should leave
            this port (unit vector ideally).
    """

    id: str
    position: Point
    direction: Vector


@dataclass(frozen=True)
class Symbol(Element):
    """A reusable component composed of primitives and ports.

    Attributes:
        elements (list[Element]): Geometric primitives making up the symbol.
        ports (dict[str, Port]): Connection points, keyed by port ID.
        label (str | None): Component label/tag (e.g., "-K1").
    """

    elements: list[Element]
    ports: dict[str, Port]
    label: str | None = None


# Type alias for symbol factory functions.
# A SymbolFactory is any callable that accepts a tag string as its first
# positional argument and returns a Symbol.  The ``...`` ellipsis allows
# additional keyword arguments, matching the actual factory signatures.
SymbolFactory = Callable[..., Symbol]
