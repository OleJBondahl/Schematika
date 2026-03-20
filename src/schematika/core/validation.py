"""Shared validation result dataclass used by all diagram validators."""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of diagram layout validation."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
