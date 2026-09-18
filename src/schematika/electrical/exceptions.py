"""Re-export shim: actual code lives in schematika.core.exceptions."""

from schematika.core.exceptions import (
    CircuitValidationError,
    ComponentNotFoundError,
    PortNotFoundError,
    RoutingError,
    TagReuseError,
    TerminalReuseError,
    WireLabelMismatchError,
)

__all__ = [
    "CircuitValidationError",
    "ComponentNotFoundError",
    "PortNotFoundError",
    "RoutingError",
    "TagReuseError",
    "TerminalReuseError",
    "WireLabelMismatchError",
]
