"""Re-export shim: actual code lives in schematika.core.state."""

from schematika.core.state import (
    GenerationState,
    create_initial_state,
)

__all__ = [
    "GenerationState",
    "create_initial_state",
]
