"""Bridges a PartitionResult to real Schematika output -- round-2 version.

Same job as round 1's `render_pages.py`: build one `CircuitBuilder` chain per
rung, register each rung's `BuildResult` with a `Project`, group them into
pages exactly as the partitioner decided, and compile a real multi-page PDF.

The one structural change from round 1: off-page markers are no longer
spliced in as extra elements bracketing a rung's declared components --
they *replace* an explicit `kind="stub"` component wherever the partitioner
put one, because a stub is a first-class chain element now (see
`netlist.ComponentSpec`), not an inferred position.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from netlist import RungSpec, SystemNetlist
from partitioner import OffPageMarker, PartitionResult, classify_link

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

    Deliberately simple -- page-internal placement is `grid-astar-router`'s
    job, not this track's. See the deep-dive doc's integration-awareness
    section for the handoff shape.
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


def _markers_by_tag(
    partition: PartitionResult, rung_key: str
) -> dict[str, OffPageMarker]:
    return {m.tag: m for m in partition.markers.get(rung_key, ())}


def _build_rung(
    rung: RungSpec,
    state,
    *,
    x: float,
    markers_here: dict[str, OffPageMarker],
    reuse_tags: dict[str, BuildResult],
) -> BuildResult:
    builder = CircuitBuilder(state)
    builder.set_layout(x=x, y=0)

    for comp in rung.components:
        if comp.kind == "terminal":
            builder.add_terminal(
                comp.id_or_prefix,
                config=TerminalConfig(poles=comp.poles),
            )
        elif comp.kind == "symbol":
            if comp.symbol_fn is None:
                msg = f"symbol component {comp.id_or_prefix!r} has no symbol_fn"
                raise ValueError(msg)
            builder.add_symbol(
                comp.symbol_fn,
                config=SymbolConfig(tag_prefix=comp.id_or_prefix, poles=comp.poles),
            )
        else:  # "stub"
            marker = markers_here.get(comp.id_or_prefix)
            if marker is not None:
                _add_marker(builder, marker)
            # else: both sides of this severed-signal link landed on the
            # same page -- no arrow needed (see `partitioner.py`'s
            # same-page `continue` for severed-signal links); the stub
            # simply renders as nothing, terminating the chain at the
            # previous component.

    builder.build(options=BuildOptions(count=1, reuse_tags=reuse_tags or None))
    return builder.result


def build_all_rungs(
    netlist: SystemNetlist, partition: PartitionResult
) -> dict[str, BuildResult]:
    """Builds every rung in topological order, wiring up tag reuse."""
    rungs_by_key = {r.key: r for r in netlist.rungs}
    x_of = _column_positions(partition, netlist)

    # (user_rung, tag) -> owner_rung, only for tag-echo links (terminal
    # crossings and severed signals need no BuildResult-level reuse -- a
    # terminal is re-declared by id, and a severed signal has no BuildResult
    # on the other side to reuse from).
    owner_of: dict[tuple[str, str], str] = {}
    for link in netlist.tag_links:
        if classify_link(netlist, link) == "tag_echo":
            owner_of[(link.user_rung, link.tag)] = link.owner_rung

    results: dict[str, BuildResult] = {}
    state = create_initial_state()

    for key in partition.build_order:
        rung = rungs_by_key[key]
        markers_here = _markers_by_tag(partition, key)

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
            markers_here=markers_here,
            reuse_tags=reuse_tags,
        )
        results[key] = result
        state = result.state

    return results


def render_project(
    results: dict[str, BuildResult],
    partition: PartitionResult,
    *,
    output_dir: str,
    pdf_path: str,
) -> None:
    """Assembles a `Project` from precomputed rung results and compiles a PDF."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    project = Project(
        title="Large Synthetic Cabinet System (round 2)",
        drawing_number="RESEARCH-PAGINATION-02",
        author="pagination-partitioner deep dive",
        project="layout-improvement research",
        revision="00",
    )

    for key, result in results.items():
        project.add_circuit(key, (lambda state, _r=result: replace(_r, state=state)))

    for page in partition.pages:
        project.page(page.title, list(page.rung_keys))

    project.terminal_report()

    project.build(pdf_path, temp_dir=output_dir, keep_temp=True)
