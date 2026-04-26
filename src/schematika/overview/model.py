"""Frozen data types for the system-overview graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContainerSpec:
    """Consumer-supplied containment row.

    ``circuits`` lists the circuit keys (as registered with
    ``project.add_circuit(key, ...)``) that belong to this container.
    """

    label: str
    kind: str
    parent: str | None = None
    circuits: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectionKey:
    """Pre-classification wire identity, fed to ``signal_kind`` callbacks."""

    from_unit: str
    from_port: str
    to_unit: str
    to_port: str


@dataclass(frozen=True, slots=True)
class Unit:
    """A node or cluster in the overview graph.

    ``ports`` is empty when ``is_container`` is ``True``: clusters cannot
    carry ports in Graphviz.
    """

    id: str
    label: str
    parent: str | None
    is_container: bool
    ports: tuple[str, ...]
    kind: str


@dataclass(frozen=True, slots=True)
class Wire:
    """An edge in the overview graph, classified by ``kind`` (e.g. power / signal)."""

    from_unit: str
    from_port: str
    to_unit: str
    to_port: str
    kind: str
