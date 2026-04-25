"""Errors for the schematika.pid (P&ID) module."""


class PIDError(ValueError):
    """Base exception for P&ID building and layout errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``PIDError`` (or a subclass)
    explicitly.

    Examples:
        >>> from schematika.pid import PIDError
        >>> issubclass(PIDError, ValueError)
        True
        >>> try:
        ...     raise PIDError("bad placement")
        ... except PIDError as exc:
        ...     str(exc)
        'bad placement'
    """


class PIDValidationError(PIDError):
    """Raised when P&ID validation fails (invalid ISA letters, duplicate names, etc)."""


class PIDPlacementError(PIDError):
    """Raised when placement cannot resolve (missing anchor, cycle, etc)."""


class PIDRoutingError(PIDError):
    """Raised when pipe/signal routing fails (unknown port or equipment, etc)."""
