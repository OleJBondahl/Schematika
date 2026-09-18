"""Graph-heuristic alternative to `RungSpec.pin_to_function`, for comparison.

Round 1's Finding 2 named two possible fixes for the ambiguous-role problem:
a manual override hook, or "a min-cut/community-detection signal on the
tag-link graph." This module implements the simplest version of the latter
so it can be run against the same large system and compared honestly,
rather than asserted to be worse from reasoning alone.

Heuristic: a control rung is flagged as "probably belongs to a different
role" when every one of its tag-echo links (the only link class that ever
crosses roles -- see `partitioner.classify_link`) points to rungs of a
single role other than its own declared role.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from netlist import RungSpec, SystemNetlist
from partitioner import classify_link


@dataclass(frozen=True)
class RoleSuggestion:
    rung_key: str
    own_role: str
    suggested_role: str
    reason: str


def suggest_role_overrides(netlist: SystemNetlist) -> tuple[RoleSuggestion, ...]:
    """Flag rungs whose tag-echo links all point to a single foreign role.

    Returns:
        One `RoleSuggestion` per rung meeting the criterion, in declaration
        order. Empty if no rung qualifies.
    """
    role_of: dict[str, str] = {r.key: r.role for r in netlist.rungs}
    foreign_roles: dict[str, set[str]] = defaultdict(set)

    for link in netlist.tag_links:
        if classify_link(netlist, link) != "tag_echo":
            continue
        owner_role = role_of[link.owner_rung]
        user_role = role_of[link.user_rung]
        if owner_role != user_role:
            foreign_roles[link.owner_rung].add(user_role)
            foreign_roles[link.user_rung].add(owner_role)

    suggestions: list[RoleSuggestion] = []
    for rung in netlist.rungs:
        foreign = foreign_roles.get(rung.key)
        if not foreign:
            continue
        if len(foreign) == 1 and rung.role not in foreign:
            (target,) = foreign
            suggestions.append(
                RoleSuggestion(
                    rung_key=rung.key,
                    own_role=rung.role,
                    suggested_role=target,
                    reason=(
                        "every tag-echo link from this rung points to role "
                        f"{target!r}, never to its own role {rung.role!r}"
                    ),
                )
            )
    return tuple(suggestions)


def rungs_a_human_would_actually_move(netlist: SystemNetlist) -> tuple[str, ...]:
    """The curated, hand-picked answer this deep dive uses as ground truth.

    Only the two `estop_master_enable_*` rungs: their entire content is
    "forward a permissive into the power domain," with no independent
    control-loop identity of their own. A loop's `contactor_coil` rung is
    structurally identical (aux-contact-in, coil-out, one terminal) but is
    NOT in this list -- a human reading the diagram wants it grouped with
    its loop's start/stop logic, because "which loop does this actuate" is
    the more useful adjacency for that rung, even though it also tag-echoes
    into the power role. See the deep-dive doc for the full argument.
    """
    return tuple(
        r.key for r in netlist.rungs if r.key.startswith("estop_master_enable_")
    )


def compare_heuristic_to_ground_truth(
    netlist: SystemNetlist,
) -> tuple[tuple[RoleSuggestion, ...], tuple[str, ...], tuple[str, ...]]:
    """Returns (all suggestions, false positives, false negatives)."""
    suggestions = suggest_role_overrides(netlist)
    truth = set(rungs_a_human_would_actually_move(netlist))
    suggested_keys = {s.rung_key for s in suggestions}
    false_positives = tuple(sorted(suggested_keys - truth))
    false_negatives = tuple(sorted(truth - suggested_keys))
    return suggestions, false_positives, false_negatives
