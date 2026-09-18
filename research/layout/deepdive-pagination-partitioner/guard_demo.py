"""Proves the severed-signal fan-out guard fires, instead of silently
producing an unrenderable multiple-arrows-on-one-port situation.

Builds a deliberately bad 4-rung netlist: a bare stub tag ("BROKEN", no
terminal, no symbol anywhere) referenced by *three* different rungs. Round
1's own Finding 3 named this exact failure mode as mechanically unrenderable
with `ref()` (a single-port chain terminus, not a branch point) but round 1
never actually exercised it -- this module does, then shows the fix
(re-anchoring the same net at a terminal) resolves it cleanly at any
fan-out, per `partitioner.classify_link`'s `terminal_crossing` rule.
"""

from __future__ import annotations

from netlist import ComponentSpec, RungSpec, SystemNetlist, TagLink
from partitioner import partition_netlist_to_pages

from schematika.core.exceptions import CircuitValidationError

_C = ComponentSpec


def _broken_netlist() -> SystemNetlist:
    """One stub owner, three stub users sharing tag "BROKEN" -- fan-out 4."""
    owner = RungSpec(
        key="broken_owner",
        role="control",
        function="broken_owner",
        title="Broken Owner",
        components=(_C(kind="stub", id_or_prefix="BROKEN"),),
    )
    users = [
        RungSpec(
            key=f"broken_user_{i}",
            role="control",
            function=f"broken_user_{i}",
            title=f"Broken User {i}",
            components=(_C(kind="stub", id_or_prefix="BROKEN"),),
        )
        for i in range(3)
    ]
    links = tuple(
        TagLink(tag="BROKEN", owner_rung=owner.key, user_rung=user.key)
        for user in users
    )
    return SystemNetlist(rungs=(owner, *users), tag_links=links)


def _fixed_netlist() -> SystemNetlist:
    """Same fan-out, but the net is anchored at a physical terminal instead
    of a bare stub -- resolves via `terminal_crossing`, no cap applies."""
    owner = RungSpec(
        key="fixed_owner",
        role="control",
        function="fixed_owner",
        title="Fixed Owner",
        components=(_C(kind="terminal", id_or_prefix="X999"),),
    )
    users = [
        RungSpec(
            key=f"fixed_user_{i}",
            role="control",
            function=f"fixed_user_{i}",
            title=f"Fixed User {i}",
            components=(_C(kind="terminal", id_or_prefix="X999"),),
        )
        for i in range(3)
    ]
    links = tuple(
        TagLink(tag="X999", owner_rung=owner.key, user_rung=user.key)
        for user in users
    )
    return SystemNetlist(rungs=(owner, *users), tag_links=links)


def run() -> str:
    """Runs both cases; returns a short report string."""
    lines = []

    try:
        partition_netlist_to_pages(_broken_netlist())
    except CircuitValidationError as exc:
        lines.append("[guard fired, as expected]")
        lines.append(f"  {exc}")
    else:
        lines.append("[FAILED] guard did not fire for a fan-out-4 stub tag")

    fixed_partition = partition_netlist_to_pages(_fixed_netlist())
    lines.append(
        "[fix verified] same fan-out, terminal-anchored: "
        f"{len(fixed_partition.pages)} pages, "
        f"{sum(len(m) for m in fixed_partition.markers.values())} off-page markers "
        "(expected 0 -- terminal crossings never need one)"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(run())
