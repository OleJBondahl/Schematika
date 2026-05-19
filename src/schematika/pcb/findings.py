"""Finding dataclass for review() output."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Severity level for a Finding.

    Attributes:
        ERROR: Critical rule violation.
        WARNING: Non-critical rule violation.
        INFO: Informational finding.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class FindingLocation:
    """Where a Finding was raised. Any combination of fields may be present.

    Attributes:
        page_title: Page on which the issue appeared.
        connector_block_ref: Connector block ref.
        part_ref: Part ref.
        net_name: Net name (verbatim, with leading slash).
    """

    page_title: str | None = None
    connector_block_ref: str | None = None
    part_ref: str | None = None
    net_name: str | None = None


@dataclass(frozen=True)
class Finding:
    """A single rule-linter finding from `review()`.

    Attributes:
        code: Unique check code (e.g. PCB001).
        severity: One of Severity.{ERROR,WARNING,INFO}.
        message: Human-readable description.
        location: Where the issue occurred.
    """

    code: str
    severity: Severity
    message: str
    location: FindingLocation = field(default_factory=FindingLocation)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping with severity rendered as string.

        Returns:
            A dict with all fields, where severity is converted to its string value.

        Examples:
            >>> f = Finding(code="PCB001", severity=Severity.ERROR, message="test")
            >>> d = f.to_dict()
            >>> d["severity"]
            'error'
        """
        d = asdict(self)
        d["severity"] = self.severity.value
        return d
