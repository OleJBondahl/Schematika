"""Options bundle for :func:`schematika.overview.build`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from schematika.overview.model import ConnectionKey, ContainerSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewOptions:
    """Options for :func:`schematika.overview.build`.

    ``palette`` and ``signal_kind`` default to ``None``; the emitter falls
    back to the built-in two-colour palette and the name-pattern classifier.
    """

    containment: Mapping[str, ContainerSpec]
    output_path: str | Path
    palette: Mapping[str, str] | None = None
    signal_kind: Callable[[ConnectionKey], str] | None = None
