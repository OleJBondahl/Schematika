"""Pagination-specific quality check, alongside the geometry linter.

The generic `svg-geometry-linter` (round 1, `research/layout/
svg-geometry-linter/linter.py`) checks orthogonality, text/wire collisions,
near-misalignment, and redundant jogs -- all geometric. None of those checks
can tell whether a cross-page net's off-page connectors are *semantically*
coherent: exactly one arrow on each side, pointing at each other, never zero
(a dangling reference) and never duplicated (an unrenderable multi-arrow
situation on one `ref()` port). This module is that check, run against the
`PartitionResult` model -- before rendering, same "lint the model, not just
the pixels" approach the geometry linter's own findings doc recommends.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from netlist import SystemNetlist
from partitioner import PartitionResult, classify_link


@dataclass(frozen=True)
class CrossPageFinding:
    kind: str
    message: str


def _page_of(partition: PartitionResult) -> dict[str, int]:
    page_of: dict[str, int] = {}
    for page in partition.pages:
        for key in page.rung_keys:
            page_of[key] = page.number
    return page_of


def check_offpage_connector_coherence(
    netlist: SystemNetlist, partition: PartitionResult
) -> tuple[CrossPageFinding, ...]:
    """Every severed-signal net crossing a page boundary gets exactly one
    coherent marker pair; no other link class ever gets a marker.

    Checks:
        1. Every marker belongs to a tag classified `severed_signal` by
           `classify_link` (a `terminal_crossing` or `tag_echo` marker would
           be exactly round 1's Finding-1 bug: an arrow implying a severed
           wire where none exists).
        2. Every severed-signal tag that crosses a page boundary has
           *exactly* two markers total (one per side) -- not zero (a
           dangling off-page reference nobody can follow) and not more than
           two (unrenderable: `ref()` exposes one port, see
           `partitioner._check_severed_signal_fanout`, which should have
           already refused to partition before this check ever runs).
        3. The two markers' labels point at each other's actual page/column,
           and their directions are opposite (one jump-in, one jump-out).

    Returns:
        One `CrossPageFinding` per violation. Empty means clean.
    """
    findings: list[CrossPageFinding] = []
    page_of = _page_of(partition)

    tag_to_link = {link.tag: link for link in netlist.tag_links}
    severed_tags = {
        link.tag for link in netlist.tag_links if classify_link(netlist, link) == "severed_signal"
    }

    markers_by_tag: dict[str, list[tuple[str, str]]] = defaultdict(list)  # tag -> [(rung_key, label)]
    for rung_key, markers in partition.markers.items():
        for marker in markers:
            markers_by_tag[marker.tag].append((rung_key, marker.label))
            if marker.tag not in severed_tags:
                findings.append(
                    CrossPageFinding(
                        kind="marker_on_non_severed_tag",
                        message=(
                            f"rung {rung_key!r} has an off-page marker for tag "
                            f"{marker.tag!r}, but that tag classifies as "
                            f"{classify_link(netlist, tag_to_link[marker.tag])!r}, "
                            "not severed_signal -- this is round-1 Finding 1's bug"
                        ),
                    )
                )

    for tag in severed_tags:
        link = tag_to_link[tag]
        crosses = page_of[link.owner_rung] != page_of[link.user_rung]
        occurrences = markers_by_tag.get(tag, [])
        if crosses and len(occurrences) == 0:
            findings.append(
                CrossPageFinding(
                    kind="missing_offpage_pair",
                    message=f"tag {tag!r} crosses a page boundary but has no marker",
                )
            )
        elif crosses and len(occurrences) == 1:
            findings.append(
                CrossPageFinding(
                    kind="incomplete_offpage_pair",
                    message=f"tag {tag!r} has only one marker (expected a pair)",
                )
            )
        elif crosses and len(occurrences) > 2:
            findings.append(
                CrossPageFinding(
                    kind="duplicated_offpage_markers",
                    message=(
                        f"tag {tag!r} has {len(occurrences)} markers -- "
                        "ref() cannot render more than one pair"
                    ),
                )
            )
        elif crosses and len(occurrences) == 2:
            (rung_a, label_a), (rung_b, label_b) = occurrences
            page_a, page_b = page_of[rung_a], page_of[rung_b]
            if not (label_a.startswith(f"/{page_b}.") and label_b.startswith(f"/{page_a}.")):
                findings.append(
                    CrossPageFinding(
                        kind="mismatched_offpage_labels",
                        message=(
                            f"tag {tag!r} markers don't point at each other: "
                            f"{rung_a!r}({page_a}) says {label_a!r}, "
                            f"{rung_b!r}({page_b}) says {label_b!r}"
                        ),
                    )
                )

    return tuple(findings)
