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

    Spacing knobs map to Graphviz attributes:

    - ``node_spacing`` → ``nodesep`` (inches) — gap between siblings.
    - ``rank_spacing`` → ``ranksep`` (inches) — gap between ranks; with
      ``splines="ortho"`` this also widens the lanes the cables route in.
    - ``edge_separation`` → ``esep`` (points, additive) — minimum margin
      around each box for spline routing; bigger value pushes parallel
      cables apart from each other and away from box edges.
    - ``cluster_margin`` → per-cluster ``margin`` (points) — internal
      whitespace inside each cluster, also pushes siblings apart.

    ``field_location`` lets a consumer nest field devices under
    user-declared "location" containers (e.g. cooling skid, battery
    pack). It is called with each device tag and returns the parent
    container id from ``containment`` — or ``None`` to leave the device
    in the top-level kind cluster.
    """

    containment: Mapping[str, ContainerSpec]
    output_path: str | Path
    palette: Mapping[str, str] | None = None
    signal_kind: Callable[[ConnectionKey], str] | None = None
    field_location: Callable[[str], str | None] | None = None
    node_spacing: float = 1.5
    rank_spacing: float = 10.0
    edge_separation: float = 20.0
    cluster_margin: float = 30.0
