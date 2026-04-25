"""Re-export shim: actual code lives in schematika.core.exceptions."""

from schematika.core.exceptions import (
    CircuitValidationError,
    ComponentNotFoundError,
    PortNotFoundError,
    TagReuseError,
    TerminalReuseError,
    WireLabelMismatchError,
)
