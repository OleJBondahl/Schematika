"""Custom exceptions for Schematika."""


class CircuitValidationError(ValueError):
    """Raised when circuit validation fails.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``CircuitValidationError``
    (or a more specific subclass) explicitly.

    This exception provides detailed information about validation failures
    to help developers quickly identify and fix issues.
    """


class PortNotFoundError(CircuitValidationError):
    """Raised when a referenced port does not exist on a component."""

    def __init__(self, component_tag: str, port_id: str, available_ports: list):
        self.component_tag = component_tag
        self.port_id = port_id
        self.available_ports = available_ports
        super().__init__(
            f"Port '{port_id}' not found on component '{component_tag}'. "
            f"Available ports: {available_ports}"
        )


class ComponentNotFoundError(CircuitValidationError):
    """Raised when a referenced component index is out of bounds."""

    def __init__(self, index: int, max_index: int):
        super().__init__(
            f"Component index {index} is out of bounds. Valid indices: 0-{max_index}"
        )


class TagReuseError(CircuitValidationError):
    """Raised when reuse_tags runs out of tags from the source result."""

    def __init__(self, prefix: str, available_tags: list):
        self.prefix = prefix
        self.available_tags = available_tags
        super().__init__(
            f"reuse_tags exhausted for prefix '{prefix}'. "
            f"Source only had {len(available_tags)} tags: {available_tags}. "
            f"Ensure the source circuit was built with enough instances."
        )


class TerminalReuseError(CircuitValidationError):
    """Raised when reuse_terminals runs out of pins from the source result."""

    def __init__(self, terminal_key: str, available_pins: list):
        self.terminal_key = terminal_key
        self.available_pins = available_pins
        super().__init__(
            f"reuse_terminals exhausted for terminal '{terminal_key}'. "
            f"Source only had {len(available_pins)} pins: {available_pins}. "
            f"Ensure the source circuit was built with enough instances."
        )


class WireLabelMismatchError(CircuitValidationError):
    """Raised when wire label count doesn't match vertical wire count."""

    def __init__(self, expected: int, actual: int, circuit_key: str = ""):
        self.expected = expected
        self.actual = actual
        ctx = f" in circuit '{circuit_key}'" if circuit_key else ""
        super().__init__(
            f"Wire label count mismatch{ctx}: "
            f"{actual} vertical wires found but {expected} labels provided."
        )
