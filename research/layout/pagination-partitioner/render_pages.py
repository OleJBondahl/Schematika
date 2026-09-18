"""Bridges a PartitionResult to real Schematika output.

Builds one `CircuitBuilder` chain per rung (with off-page connector arrows
spliced in where the partitioner decided a wire is severed at a page
boundary), registers each rung's `BuildResult` with a `Project`, groups them
into pages exactly as the partitioner decided, and compiles a real
multi-page PDF -- so the automatic split can be inspected visually, not just
reasoned about.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from netlist import RungSpec, SystemNetlist
from partitioner import OffPageMarker, PartitionResult

from schematika.core.options import BuildOptions, SymbolConfig, TerminalConfig
from schematika.core.state import create_initial_state
from schematika.electrical.builder import BuildResult, CircuitBuilder
from schematika.electrical.symbols import ref as offpage_ref
from schematika.project import Project

COLUMN_SPACING_1P = 80.0
COLUMN_SPACING_3P = 220.0


def _rung_width(rung: RungSpec) -> float:
    poles = max((c.poles for c in rung.components), default=1)
    return COLUMN_SPACING_3P if poles >= 3 else COLUMN_SPACING_1P


def _column_positions(partition: PartitionResult, netlist: SystemNetlist) -> dict:
    """Left-to-right cumulative x-offset per rung, reset at each page.

    Deliberately simple: this track owns *which* rungs land on which page,
    not layout quality. Precise Y-zone/grid placement is `grid-astar-router`'s
    job -- see docs/research/layout-improvement/README.md.
    """
    x_of: dict[str, float] = {}
    for page in partition.pages:
        cursor = 0.0
        for key in page.rung_keys:
            x_of[key] = cursor
            cursor += _rung_width(netlist.rung(key))
    return x_of


def _add_marker(builder: CircuitBuilder, marker: OffPageMarker) -> None:
    builder.add_symbol(
        offpage_ref,
        config=SymbolConfig(
            tag_prefix="REF",
            factory_kwargs={"label": marker.label, "direction": marker.direction},
        ),
    )


def _build_rung(
    rung: RungSpec,
    state,
    *,
    x: float,
    start_markers: list[OffPageMarker],
    end_markers: list[OffPageMarker],
    reuse_tags: dict[str, BuildResult],
) -> BuildResult:
    builder = CircuitBuilder(state)
    builder.set_layout(x=x, y=0)

    for marker in start_markers:
        _add_marker(builder, marker)

    for comp in rung.components:
        if comp.kind == "terminal":
            builder.add_terminal(
                comp.id_or_prefix,
                config=TerminalConfig(poles=comp.poles),
            )
        else:
            if comp.symbol_fn is None:
                msg = f"symbol component {comp.id_or_prefix!r} has no symbol_fn"
                raise ValueError(msg)
            builder.add_symbol(
                comp.symbol_fn,
                config=SymbolConfig(tag_prefix=comp.id_or_prefix, poles=comp.poles),
            )

    for marker in end_markers:
        _add_marker(builder, marker)

    builder.build(options=BuildOptions(count=1, reuse_tags=reuse_tags or None))
    return builder.result


def build_all_rungs(
    netlist: SystemNetlist, partition: PartitionResult
) -> dict[str, BuildResult]:
    """Builds every rung in topological order, wiring up tag reuse."""
    rungs_by_key = {r.key: r for r in netlist.rungs}
    x_of = _column_positions(partition, netlist)

    # (user_rung, tag) -> owner_rung, for BOTH tag-echo and severed-wire links
    # (a severed wire's terminal still needs to reuse the same allocated pin
    # numbering scheme via the terminal id itself, but tag reuse only applies
    # to symbol prefixes -- terminals share identity by id, not reuse_tags).
    owner_of: dict[tuple[str, str], str] = {}
    for link in netlist.tag_links:
        if link.owner_boundary is None and link.user_boundary is None:
            owner_of[(link.user_rung, link.tag)] = link.owner_rung

    results: dict[str, BuildResult] = {}
    state = create_initial_state()

    for key in partition.build_order:
        rung = rungs_by_key[key]
        markers = partition.markers.get(key, ())
        start_markers = [m for m in markers if m.boundary == "start"]
        end_markers = [m for m in markers if m.boundary == "end"]

        reuse_tags: dict[str, BuildResult] = {}
        for comp in rung.components:
            if comp.kind != "symbol":
                continue
            owner_key = owner_of.get((rung.key, comp.id_or_prefix))
            if owner_key is not None:
                reuse_tags[comp.id_or_prefix] = results[owner_key]

        result = _build_rung(
            rung,
            state,
            x=x_of[key],
            start_markers=start_markers,
            end_markers=end_markers,
            reuse_tags=reuse_tags,
        )
        results[key] = result
        state = result.state

    return results


def render_project(
    netlist: SystemNetlist,
    partition: PartitionResult,
    results: dict[str, BuildResult],
    *,
    output_dir: str,
    pdf_path: str,
) -> None:
    """Assembles a `Project` from precomputed rung results and compiles a PDF."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    project = Project(
        title="Synthetic Cabinet System",
        drawing_number="RESEARCH-PAGINATION-01",
        author="pagination-partitioner spike",
        project="layout-improvement research",
        revision="00",
    )

    for key, result in results.items():
        project.add_circuit(key, (lambda state, _r=result: replace(_r, state=state)))

    for page in partition.pages:
        project.page(page.title, list(page.rung_keys))

    project.terminal_report()

    project.build(pdf_path, temp_dir=output_dir, keep_temp=True)
