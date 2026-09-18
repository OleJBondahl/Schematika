"""The `Project.partition()`-shaped API this track recommends for real
integration into `src/schematika/project.py`.

Round 1 said this would be "a thin wrapper" around `merge_build_results`,
citing `Project.add_pcb` (`project.py:424`) as the closest existing
precedent: `add_pcb` takes an already-built `PCBBuildResult` (pages,
placements, a connector-block lookup) and does nothing but loop
`add_circuit`/register-page calls to wire it into the project's page list --
it does not itself do PCB layout. This module builds the electrical
equivalent and proves the split: layer-2 partitioning logic (which pages
exist, what's on each, off-page markers) lives in a plain function,
`partition_to_pages`; layer-4 registration (wiring the result into a
`Project`) lives in `add_partition`, mirroring `add_pcb`'s shape exactly.

Neither function touches `src/schematika/` -- see the deep-dive doc for the
concrete next steps to promote this into `project.py` for real.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from netlist import SystemNetlist
from partitioner import PartitionResult, partition_netlist_to_pages
from render_pages import build_all_rungs

from schematika.electrical.builder import BuildResult
from schematika.project import Project


@dataclass(frozen=True)
class PartitionedElectricalResult:
    """Frozen result of partitioning and building a whole rung-level netlist.

    Shape deliberately mirrors `PCBBuildResult`: a `partition` describing
    page structure (comparable to `PCBBuildResult.pages`) plus a lookup of
    the already-built pieces (comparable to `PCBBuildResult.connector_blocks`
    keyed by ref) -- so a future `Project.add_partition` can be reviewed
    side-by-side with the existing `Project.add_pcb` and judged structurally
    equivalent, not just similarly named.
    """

    partition: PartitionResult
    circuit_results: dict[str, BuildResult]


def partition_to_pages(
    netlist: SystemNetlist, *, max_rungs_per_page: int = 5
) -> PartitionedElectricalResult:
    """Partition a rung-level netlist into pages and build every rung.

    This is a **free function**, not a method on a new mutable builder.
    Unlike `CircuitBuilder`, which exists specifically to accumulate one
    rung's components incrementally across many method calls, there is no
    meaningful partial state between "have a `SystemNetlist`" and "have
    every rung built and paged" -- the whole rung graph is known upfront in
    one call, so a mutable builder here would only be a container for that
    one call plus a `build()` rename (the kind of premature-abstraction
    builder `CLAUDE.md` asks to avoid). `pcb.build(circuit, mapping)` is the
    existing precedent for exactly this shape: a whole-graph free function
    at layer 2, alongside (not replacing) `CircuitBuilder`.

    Args:
        netlist: The full rung-level system to partition.
        max_rungs_per_page: Forwarded to `partition_netlist_to_pages`.

    Returns:
        Page assignments plus every rung's built `BuildResult`, ready to
        hand to `add_partition`.

    Raises:
        CircuitValidationError: See `partition_netlist_to_pages`.
    """
    partition = partition_netlist_to_pages(
        netlist, max_rungs_per_page=max_rungs_per_page
    )
    circuit_results = build_all_rungs(netlist, partition)
    return PartitionedElectricalResult(
        partition=partition, circuit_results=circuit_results
    )


def add_partition(project: Project, result: PartitionedElectricalResult, /) -> Project:
    """Register every page and circuit of `result` onto `project`.

    This is the shape a real `Project.add_partition(self, result, /)` method
    would have. `Project.add_pcb` (`project.py:424`) is the exact precedent:
    both take an already-built, already-paginated domain result and do
    nothing but loop `add_circuit`/`page` calls to wire it into the
    project's page list -- neither runs its own domain's layout logic. In
    production this would be a bound method (`self` instead of the
    `project` parameter); it is a free function here only because this is
    research code that does not touch `src/schematika/project.py`.

    Verb choice: `API_STYLE.md` reserves `add_<noun>` for "register a new
    component on a mutable builder" and reserves bare verbs (`build`,
    `render`, `write`, `compile`) for producing or emitting output. This
    call only *registers* pages and circuits that `partition_to_pages`
    already computed -- it neither partitions nor renders -- so `add_partition`
    is the correct verb, exactly parallel to `add_pcb` registering an
    already-built `PCBBuildResult` rather than a bare `partition()` verb
    that would wrongly suggest this function does the partitioning itself.

    Args:
        project: The project to register pages and circuits onto.
        result: The output of `partition_to_pages`.

    Returns:
        `project`, for chaining (matches `add_pcb`'s return-self convention).

    Note:
        `Project._render_multi_circuit_pages` names a merged page's SVG file
        `"_".join(page_def.circuit_keys) + ".svg"` (`project.py:1406`). With
        rung keys as descriptive as this deep dive's (`loop_9_start_stop`,
        `estop_master_enable_a`, ...), a 5-rung page's merged filename
        exceeds Windows' ~260-char path limit and `ElementTree.write` fails
        with a bare `FileNotFoundError` -- surfaced running this exact
        module against the large system, not a hypothetical. This function
        works around it by registering short synthetic circuit keys
        (`c000`, `c001`, ...) instead of the netlist's own rung keys; a real
        `Project.add_partition` would need either the same workaround or a
        fix to `_render_multi_circuit_pages` itself (e.g. hash long merged
        keys past some length). Flagged in the deep-dive doc as a
        cross-cutting bug, independent of this track's own scope.
    """
    short_key_of = {key: f"c{i:03d}" for i, key in enumerate(result.circuit_results)}
    for key, circuit_result in result.circuit_results.items():
        short_key = short_key_of[key]
        project.add_circuit(
            short_key, (lambda state, _r=circuit_result: replace(_r, state=state))
        )
    for page in result.partition.pages:
        project.page(page.title, [short_key_of[k] for k in page.rung_keys])
    return project
