"""Terminal type for Schematika.

Provides a first-class `Terminal` type that replaces the string-based
terminal ID hack. Terminals carry metadata (title, description, bridge info,
reference flag) while being fully compatible with string operations
by inheriting from `str`.
"""

from schematika.electrical.builder_models import BridgeMode
from schematika.electrical.utils.terminal_bridges import BridgeRange

BridgeDef = BridgeMode | list[BridgeRange] | None


class Terminal(str):
    """A terminal block definition with metadata.

    Terminals ARE strings (via inheritance) for full backwards compatibility
    with existing code that uses terminal IDs as plain strings.

    Args:
        id: Terminal identifier (e.g., "X001").
        title: Human-readable title unique to this terminal (e.g., "Main 400V AC").
        description: Product description shared across terminals with the same MPN
                     (e.g., "Terminal block"). Used for BOM grouping.
        bridge: Internal bridge definition. ``BridgeMode.ALL`` for all pins
                bridged, ``BridgeMode.PER_PREFIX`` for per-prefix bridging,
                list of (start, end) tuples for specific ranges, or None.
        reference: True for non-physical terminals (e.g., "PLC:DO").
                   Reference terminals are excluded from terminal reports.
        pin_prefixes: Optional tuple of prefix strings for auto-numbered pins.
                      When set, ``next_terminal_pins()`` generates pins like
                      ``"L1:1", "L2:1", "L3:1"`` using group-based counting.
    """

    __slots__ = ("bridge", "description", "mpn", "pin_prefixes", "reference", "title")

    title: str
    description: str
    bridge: BridgeDef
    reference: bool
    pin_prefixes: tuple[str, ...] | None
    mpn: str

    def __new__(
        cls,
        id: str,
        title: str = "",
        description: str = "",
        bridge: BridgeDef = None,
        *,
        reference: bool = False,
        pin_prefixes: tuple[str, ...] | None = None,
        mpn: str = "",
    ) -> "Terminal":
        """Create a new ``Terminal`` str-subclass instance carrying metadata."""
        instance = super().__new__(cls, id)
        object.__setattr__(instance, "title", title)
        object.__setattr__(instance, "description", description)
        object.__setattr__(instance, "bridge", bridge)
        object.__setattr__(instance, "reference", reference)
        object.__setattr__(instance, "pin_prefixes", pin_prefixes)
        object.__setattr__(instance, "mpn", mpn)
        return instance

    def __setattr__(self, name: str, value: object) -> None:
        """Raise ``AttributeError`` — ``Terminal`` instances are immutable."""
        raise AttributeError(f"Terminal is immutable, cannot set '{name}'")

    def __hash__(self) -> int:
        """Compute hash using the underlying string value."""
        return str.__hash__(self)

    def __eq__(self, other: object) -> bool:
        """Compare equality on the string representation of *other*."""
        return str.__eq__(self, str(other))
