"""Render-time presentation flags for cable drawings, keyed by connector.

Keeps the cable data model pure: presentation choices (e.g. whether to show a
connector's pincount) live here, not on the connector dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.identifiers import ConnectorId


@dataclass(frozen=True, slots=True, kw_only=True)
class CableRenderConfig:
    """Presentation flags for rendering a cable, keyed by connector name.

    Attributes:
        show_pincount: Connector names whose pincount should be rendered.

    Examples:
        >>> from schematika.cable.render_config import CableRenderConfig
        >>> from schematika.catalog.identifiers import ConnectorId
        >>> ConnectorId("J1") in CableRenderConfig(
        ...     show_pincount=frozenset({ConnectorId("J1")})
        ... ).show_pincount
        True
    """

    show_pincount: frozenset[ConnectorId] = field(default_factory=frozenset)
