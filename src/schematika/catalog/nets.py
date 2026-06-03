# src/schematika/catalog/nets.py
"""Net-name normalization: the sole NetId constructor from raw strings."""

from __future__ import annotations

from schematika.catalog.errors import CatalogValidationError
from schematika.catalog.identifiers import NetId


def normalize_net_name(raw: str) -> NetId:
    """Canonicalize a raw net name to a ``NetId``.

    Strips a single leading ``'/'`` (SKiDL hierarchical prefix), then
    constructs a ``NetId`` -- which rejects any remaining internal ``'/'`` and
    empty results.

    Args:
        raw: Plain net-name string (e.g. a SKiDL ``Net.name``).

    Returns:
        The normalized ``NetId``.

    Raises:
        CatalogValidationError: if normalization yields an empty string or the
            name still contains a ``'/'``.

    Examples:
        >>> from schematika.catalog.nets import normalize_net_name
        >>> normalize_net_name("/VBUS_24V")
        'VBUS_24V'
    """
    stripped = raw.removeprefix("/")
    if not stripped:
        msg = f"Net name {raw!r} normalizes to empty"
        raise CatalogValidationError(msg)
    return NetId(stripped)
