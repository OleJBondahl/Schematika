"""Entry point for the round-2 pagination-partitioner deep dive.

Usage:
    uv run python research/layout/deepdive-pagination-partitioner/run.py

Runs, in order:
    1. Partitions the large synthetic system WITHOUT the role-override fix
       (reproduces round 1's unpatched ambiguous-placement behaviour).
    2. Partitions it again WITH the fix (`pin_to_function`) and diffs the
       two -- proof the ambiguous-role problem is actually resolved.
    3. Runs the graph-heuristic alternative and compares it against a
       curated ground truth -- proof automatic inference over-fires.
    4. Runs the severed-signal fan-out guard demo (proves the shared-bus
       mechanical limit is caught, not silently mis-rendered).
    5. Drives the `Project.partition()`-shaped API (`pagination_api.py`) end
       to end on the fixed netlist: partitions, builds every rung, renders a
       real multi-page PDF.
    6. Runs the pagination-specific cross-page connector coherence check.
    7. Runs the round-1 geometry linter against every rung's pre-render
       element tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "svg-geometry-linter"))

from cross_page_lint import check_offpage_connector_coherence  # noqa: E402
from guard_demo import run as run_guard_demo  # noqa: E402
from large_synthetic_system import build_large_system  # noqa: E402
from linter import lint_elements  # noqa: E402
from pagination_api import add_partition, partition_to_pages  # noqa: E402
from partitioner import partition_netlist_to_pages  # noqa: E402
from role_heuristic import compare_heuristic_to_ground_truth  # noqa: E402

from schematika.project import Project  # noqa: E402

OUTPUT_DIR = HERE / "output"


def _page_title_for(netlist, partition, rung_key: str) -> str:
    for page in partition.pages:
        if rung_key in page.rung_keys:
            return f"page {page.number}: {page.title}"
    return "(not paged)"


def _print_ambiguous_role_before_after() -> None:
    print("=" * 78)
    print("1+2. Ambiguous-role problem: before/after the pin_to_function fix")
    print("=" * 78)
    before_netlist = build_large_system(apply_role_overrides=False)
    after_netlist = build_large_system(apply_role_overrides=True)
    before_partition = partition_netlist_to_pages(before_netlist)
    after_partition = partition_netlist_to_pages(after_netlist)

    for domain in ("a", "b"):
        key = f"estop_master_enable_{domain}"
        incomer_key = f"main_incomer_{domain}"
        before_loc = _page_title_for(before_netlist, before_partition, key)
        after_loc = _page_title_for(after_netlist, after_partition, key)
        incomer_loc = _page_title_for(after_netlist, after_partition, incomer_key)
        print(f"  {key}:")
        print(f"    before fix : {before_loc}")
        print(f"    after fix  : {after_loc}")
        print(f"    ({incomer_key} lives on: {incomer_loc})")
    print()
    print(f"  before-fix page count: {len(before_partition.pages)}")
    print(f"  after-fix  page count: {len(after_partition.pages)}")
    print()


def _print_heuristic_comparison() -> None:
    print("=" * 78)
    print("3. Graph-heuristic alternative vs. curated ground truth")
    print("=" * 78)
    netlist = build_large_system(apply_role_overrides=False)
    suggestions, false_positives, false_negatives = compare_heuristic_to_ground_truth(
        netlist
    )
    print(f"  heuristic flagged {len(suggestions)} rung(s):")
    for s in suggestions:
        print(f"    {s.rung_key}: {s.own_role} -> {s.suggested_role}  ({s.reason})")
    print(f"  false positives ({len(false_positives)}): {false_positives}")
    print(f"  false negatives ({len(false_negatives)}): {false_negatives}")
    print(
        "  verdict: the heuristic cannot distinguish estop_master_enable_* from "
        "loop_*_contactor_coil -- both are structurally identical (aux-contact-in, "
        "coil-out, one terminal). Manual pin_to_function is the honest fix."
    )
    print()


def _print_guard_demo() -> None:
    print("=" * 78)
    print("4. Severed-signal fan-out guard")
    print("=" * 78)
    print(run_guard_demo())
    print()


def _render_and_lint() -> None:
    print("=" * 78)
    print("5+6+7. Project.partition()-shaped API end-to-end + quality checks")
    print("=" * 78)
    netlist = build_large_system(apply_role_overrides=True)
    result = partition_to_pages(netlist, max_rungs_per_page=5)

    print(f"  {len(netlist.rungs)} rungs -> {len(result.partition.pages)} pages")
    for page in result.partition.pages:
        print(f"    page {page.number}: {page.title} ({len(page.rung_keys)} rungs)")

    total_markers = sum(len(m) for m in result.partition.markers.values())
    print(f"  off-page connector markers emitted: {total_markers}")
    print(
        f"  terminal crossings (no marker, self-documenting): "
        f"{len(result.partition.terminal_crossings)}"
    )
    print(f"  plain tag-echo cross-refs (no marker): {len(result.partition.plain_cross_refs)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = Project(
        title="Large Synthetic Cabinet System (round 2, fixed)",
        drawing_number="RESEARCH-PAGINATION-02",
        author="pagination-partitioner deep dive",
        project="layout-improvement research",
        revision="00",
    )
    add_partition(project, result)
    project.terminal_report()
    pdf_path = str(OUTPUT_DIR / "large_synthetic_cabinet.pdf")
    project.build(pdf_path, temp_dir=str(OUTPUT_DIR), keep_temp=True)
    print(f"\n  compiled PDF: {pdf_path}")

    print("\n  cross-page connector coherence check:")
    findings = check_offpage_connector_coherence(netlist, result.partition)
    if not findings:
        print("    clean -- every severed-signal net has exactly one coherent pair")
    for f in findings:
        print(f"    [{f.kind}] {f.message}")

    print("\n  geometry linter (round-1 svg-geometry-linter, model-level):")
    total_findings = 0
    total_cost = 0.0
    by_kind: dict[str, int] = {}
    for key, circuit_result in result.circuit_results.items():
        report = lint_elements(circuit_result.circuit.elements)
        total_findings += len(report.findings)
        total_cost += report.cost
        for kind, count in report.by_kind().items():
            by_kind[kind] = by_kind.get(kind, 0) + count
        if report.findings:
            print(f"    {key}: {len(report.findings)} finding(s) -- {report.by_kind()}")
    print(f"    total: {total_findings} finding(s) across {len(result.circuit_results)} rungs, cost={total_cost:.2f}")
    print(f"    by kind: {by_kind}")
    print()


def main() -> None:
    _print_ambiguous_role_before_after()
    _print_heuristic_comparison()
    _print_guard_demo()
    _render_and_lint()


if __name__ == "__main__":
    main()
