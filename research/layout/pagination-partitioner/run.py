"""Entry point: build the synthetic system, partition it, render it.

Usage:
    uv run python research/layout/pagination-partitioner/run.py
"""

from __future__ import annotations

from pathlib import Path

from partitioner import partition_netlist_to_pages
from render_pages import build_all_rungs, render_project
from synthetic_system import build_synthetic_system

OUTPUT_DIR = Path(__file__).parent / "output"


def _print_summary(netlist, partition) -> None:
    print("=== Partition summary ===")
    for page in partition.pages:
        print(f"Page {page.number}: {page.title}")
        for key in page.rung_keys:
            rung = netlist.rung(key)
            print(f"    - {key}  ({len(rung.components)} components)")
    print()
    print("Build order (topological, owners before users):")
    print("   ", " -> ".join(partition.build_order))
    print()
    print("Off-page connector markers:")
    if not any(partition.markers.values()):
        print("    (none)")
    for key, markers in partition.markers.items():
        for m in markers:
            print(f"    {key}: {m.direction} arrow, tag={m.tag}, label={m.label}")
    print()
    print("Plain cross-page tag echoes (no marker, resolved by reuse_tags):")
    for link in partition.plain_cross_refs:
        print(f"    {link.tag}: {link.owner_rung} -> {link.user_rung}")


def main() -> None:
    netlist = build_synthetic_system()
    partition = partition_netlist_to_pages(netlist)
    _print_summary(netlist, partition)

    results = build_all_rungs(netlist, partition)

    pdf_path = str(OUTPUT_DIR / "synthetic_cabinet.pdf")
    render_project(netlist, partition, results, output_dir=str(OUTPUT_DIR), pdf_path=pdf_path)
    print(f"\nCompiled PDF: {pdf_path}")


if __name__ == "__main__":
    main()
