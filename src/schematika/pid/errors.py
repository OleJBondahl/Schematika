"""Errors for the schematika.pid (P&ID) module."""


class PIDError(ValueError):
    """Base exception for P&ID building and layout errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``PIDError`` (or a subclass)
    explicitly.
    """


class PIDValidationError(PIDError):
    """Raised when P&ID validation fails (invalid ISA letters, duplicate names, etc)."""


class PIDPlacementError(PIDError):
    """Raised when equipment placement cannot be resolved (missing anchor, cycle, etc)."""


class PIDRoutingError(PIDError):
    """Raised when pipe/signal-line routing fails (unknown port, unknown equipment, etc)."""
