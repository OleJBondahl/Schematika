"""Errors for the schematika.overview module."""


class OverviewError(ValueError):
    """Base exception for the schematika.overview module."""


class OverviewContainmentError(OverviewError):
    """Containment input is malformed or inconsistent."""


class OverviewExtractionError(OverviewError):
    """Project state could not be turned into a valid Unit/Wire graph."""


class OverviewRenderError(OverviewError):
    """Graphviz invocation failed or produced unexpected output."""
