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
    """A terminal block identifier that carries wiring metadata.

    Subclasses ``str`` for full backward compatibility — a ``Terminal`` can
    be used anywhere a plain string terminal ID is expected.  Extra metadata
    (title, MPN, bridge mode, pin prefixes) is stored as immutable slots.

    Attributes:
        title: Human-readable label unique to this terminal, e.g.
            ``"Main 400V AC"``.
        description: BOM description shared across terminals with the same
            MPN, e.g. ``"Phoenix 2.5mm terminal"``.
        bridge: Internal bridge definition —
            :attr:`~schematika.electrical.BridgeMode.ALL`,
            :attr:`~schematika.electrical.BridgeMode.PER_PREFIX`, a list of
            ``(start, end)`` ranges, or ``None``.
        reference: ``True`` for non-physical terminals like ``"PLC:DO"``
            that are excluded from terminal reports.
        pin_prefixes: Prefix strings for group-based pin IDs, e.g.
            ``("L1", "L2", "L3")`` generates ``"L1:1"``, ``"L2:1"``, etc.
        mpn: Manufacturer part number for BOM.

    Examples:
        >>> from schematika.electrical import Terminal
        >>> t = Terminal("X001", title="Main supply", description="Terminal block")
        >>> str(t)
        'X001'
        >>> t.title
        'Main supply'
        >>> t == "X001"
        True
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
        msg = f"Terminal is immutable, cannot set '{name}'"
        raise AttributeError(msg)

    def __hash__(self) -> int:
        """Compute hash using the underlying string value."""
        return str.__hash__(self)

    def __eq__(self, other: object) -> bool:
        """Compare equality on the string representation of *other*."""
        return str.__eq__(self, str(other))
