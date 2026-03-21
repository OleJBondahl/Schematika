"""Re-export shim: actual code lives in schematika.core.exceptions."""

from schematika.core.exceptions import (  # noqa: F401
    CircuitValidationError,
    ComponentNotFoundError,
    PortNotFoundError,
    TagReuseError,
    TerminalReuseError,
    WireLabelMismatchError,
)
