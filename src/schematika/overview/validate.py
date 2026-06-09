"""Structural completeness checks for OverviewGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.overview.model import _split_pin

if TYPE_CHECKING:
    from schematika.overview.inputs import OverviewInput
    from schematika.overview.model import OverviewGraph


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationReport:
    """Result of a structural graph validation run."""

    ok: bool
    problems: tuple[str, ...]


def validate_overview_graph(
    graph: OverviewGraph, inp: OverviewInput
) -> ValidationReport:
    """Check structural completeness of graph against its input.

    Returns a ValidationReport; never raises. Problems are sorted for
    deterministic output.
    """
    problems: list[str] = []

    # 1. Edge/wire count
    harness_edges = [e for e in graph.edges if e.kind == "harness"]
    seen: set[frozenset[str]] = set()
    deduped_wires: list = []
    for w in inp.wires:
        key: frozenset[str] = frozenset((w.a, w.b))
        if key not in seen:
            seen.add(key)
            deduped_wires.append(w)
    if len(harness_edges) != len(deduped_wires):
        problems.append(
            f"edge_count {len(harness_edges)} != wire_count {len(deduped_wires)}"
        )

    # 2. Device-node coverage
    device_ids = {d.id for d in graph.devices}
    for w in inp.wires:
        for pin_str in (w.a, w.b):
            tag = _split_pin(pin_str)[0]
            if tag not in device_ids:
                problems.append(f"missing device node: {tag}")
                device_ids.add(tag)  # report once per missing tag

    # 3. No orphan pins
    signal_ids = {s.id for s in graph.signals}
    problems.extend(
        f"orphan pin {pin.id} -> signal {pin.signal_id}"
        for pin in graph.pins
        if pin.signal_id not in signal_ids
    )

    # 4. No duplicate device nodes
    seen_device_ids: set[str] = set()
    for d in graph.devices:
        if d.id in seen_device_ids:
            problems.append(f"duplicate device node: {d.id}")
        seen_device_ids.add(d.id)

    problems.sort()
    return ValidationReport(ok=not problems, problems=tuple(problems))
