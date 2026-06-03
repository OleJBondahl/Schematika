# src/schematika/catalog/identifiers.py
"""Typed string identifiers for the catalog (audit F1, F2, F30).

Seven frozen ``str`` subclasses. Each ``__new__`` validates and raises
``CatalogValidationError`` on a malformed value. They subclass ``str`` so they
cross ``str``-typed boundaries (SKiDL, WireViz, Typst) unchanged while ``ty``
enforces distinctness; native ``str`` equality and hashing are kept on purpose
(``NetId("n") == "n"``). Pattern mirrors ``electrical/terminal.py``.
"""

from __future__ import annotations

import re

from schematika.catalog.errors import CatalogValidationError

_PART_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_TAG_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]*$")


def _require_nonempty(value: str, typename: str) -> None:
    if not value:
        msg = f"{typename} must be non-empty"
        raise CatalogValidationError(msg)


class PartId(str):
    """Catalog primary key, e.g. ``PartId("phoenix_3pos")``.

    The ``PartId`` *is* the catalog's MPN slot; ``PartSpec.mpn`` carries the
    manufacturer string. Validates against ``^[A-Za-z0-9._-]+$``.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> PartId("phoenix_3pos")
        'phoenix_3pos'
        >>> from schematika.catalog.errors import CatalogValidationError
        >>> try:
        ...     PartId("bad id!")
        ... except CatalogValidationError:
        ...     print("rejected")
        rejected
    """

    __slots__ = ()

    def __new__(cls, value: str) -> PartId:
        """Create a validated ``PartId``."""
        if not _PART_ID_RE.match(value):
            msg = f"Invalid PartId {value!r}: must match {_PART_ID_RE.pattern}"
            raise CatalogValidationError(msg)
        return super().__new__(cls, value)


class ConnectorId(str):
    """Per-project connector instance handle, e.g. ``ConnectorId("J1")``.

    Examples:
        >>> from schematika.catalog.identifiers import ConnectorId
        >>> ConnectorId("J1")
        'J1'
    """

    __slots__ = ()

    def __new__(cls, value: str) -> ConnectorId:
        """Create a validated ``ConnectorId``."""
        _require_nonempty(value, "ConnectorId")
        return super().__new__(cls, value)


class DeviceTag(str):
    """Per-circuit device tag, e.g. ``DeviceTag("-Q1")``.

    Validates non-empty only; consumer tags are heterogeneous
    (``"TT-101"``, ``"-Q1"``, ``"M1"``) so no strict IEC 61346 regex is
    applied here.

    Examples:
        >>> from schematika.catalog.identifiers import DeviceTag
        >>> DeviceTag("-Q1")
        '-Q1'
    """

    __slots__ = ()

    def __new__(cls, value: str) -> DeviceTag:
        """Create a validated ``DeviceTag``."""
        _require_nonempty(value, "DeviceTag")
        return super().__new__(cls, value)


class NetId(str):
    """Canonical net name. Rejects any string containing ``'/'``.

    Structural enforcement for audit F30: SKiDL net names must pass through
    ``normalize_net_name`` before becoming a ``NetId``; no caller can bypass
    normalization by constructing ``NetId("/foo")``.

    Examples:
        >>> from schematika.catalog.identifiers import NetId
        >>> NetId("VBUS_24V")
        'VBUS_24V'
        >>> from schematika.catalog.errors import CatalogValidationError
        >>> try:
        ...     NetId("/foo")
        ... except CatalogValidationError:
        ...     print("rejected")
        rejected
    """

    __slots__ = ()

    def __new__(cls, value: str) -> NetId:
        """Create a validated ``NetId``."""
        _require_nonempty(value, "NetId")
        if "/" in value:
            msg = f"Invalid NetId {value!r}: must not contain '/'"
            raise CatalogValidationError(msg)
        return super().__new__(cls, value)


class CableId(str):
    """Cable instance handle, e.g. ``CableId("W12")``.

    Examples:
        >>> from schematika.catalog.identifiers import CableId
        >>> CableId("W12")
        'W12'
    """

    __slots__ = ()

    def __new__(cls, value: str) -> CableId:
        """Create a validated ``CableId``."""
        _require_nonempty(value, "CableId")
        return super().__new__(cls, value)


class CircuitId(str):
    """Project-level circuit key (replaces the ``project._results`` str key).

    Examples:
        >>> from schematika.catalog.identifiers import CircuitId
        >>> CircuitId("main")
        'main'
    """

    __slots__ = ()

    def __new__(cls, value: str) -> CircuitId:
        """Create a validated ``CircuitId``."""
        _require_nonempty(value, "CircuitId")
        return super().__new__(cls, value)


class TagPrefix(str):
    """IEC prefix for ``reuse_tags`` maps, e.g. ``TagPrefix("K")``.

    Validates against ``^[A-Z][A-Z0-9]*$``. Per-circuit prefix-set
    validation lives in the autonumberer (Layer 2), not here.

    Examples:
        >>> from schematika.catalog.identifiers import TagPrefix
        >>> TagPrefix("FT")
        'FT'
    """

    __slots__ = ()

    def __new__(cls, value: str) -> TagPrefix:
        """Create a validated ``TagPrefix``."""
        if not _TAG_PREFIX_RE.match(value):
            msg = f"Invalid TagPrefix {value!r}: must match {_TAG_PREFIX_RE.pattern}"
            raise CatalogValidationError(msg)
        return super().__new__(cls, value)
