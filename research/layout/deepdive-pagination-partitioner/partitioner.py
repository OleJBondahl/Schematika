"""Rule-based page partitioner -- round-2 deep dive.

Extends `research/layout/pagination-partitioner/partitioner.py` with the two
fixes this round's investigation was scoped to solve for real:

1. **Ambiguous role placement** (round-1 Finding 2): `RungSpec.pin_to_function`
   is a manual override hook, applied in a pre-pass before the automatic
   role/function bucketing runs (`_effective_bucket`).
2. **Shared-bus / severed-wire conflation** (round-1 Findings 1 and 3):
   `classify_link` derives "terminal crossing" (never an arrow, any fan-out)
   vs. "tag echo" (never an arrow, `reuse_tags` resolves it) vs. "severed
   signal" (needs a `ref()` arrow) from `ComponentSpec.kind`, not a
   manually-set flag. Severed-signal tags are capped at fan-out 2 (one owner,
   one user) -- `ref()` is a single-port chain terminus, not a branch point,
   so a wider fan-out is flagged with a clear, actionable error instead of
   silently producing an unrenderable multi-arrow situation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

from netlist import ComponentSpec, RungSpec, SystemNetlist, TagLink

from schematika.core.exceptions import CircuitValidationError

MAX_RUNGS_PER_PAGE = 5

LinkClass = Literal["terminal_crossing", "tag_echo", "severed_signal"]


@dataclass(frozen=True)
class OffPageMarker:
    """One half of an off-page connector pair, attached to one rung's chain
    end. `label` names the *other* page/column -- what a reader should jump
    to -- not this one.
    """

    tag: str
    boundary: Literal["start", "end"]
    direction: Literal["up", "down"]  # "up" = jump-in, "down" = jump-out
    label: str  # e.g. "/3.C2"


@dataclass(frozen=True)
class PageAssignment:
    number: int
    title: str
    rung_keys: tuple[str, ...]


@dataclass(frozen=True)
class PartitionResult:
    pages: tuple[PageAssignment, ...]
    build_order: tuple[str, ...]
    markers: dict[str, tuple[OffPageMarker, ...]]
    plain_cross_refs: tuple[TagLink, ...]  # tag echoes crossing pages, no marker
    terminal_crossings: tuple[TagLink, ...]  # terminal ids crossing pages, no marker


def _find_component(rung: RungSpec, tag: str) -> ComponentSpec | None:
    for comp in rung.components:
        if comp.id_or_prefix == tag:
            return comp
    return None


def classify_link(netlist: SystemNetlist, link: TagLink) -> LinkClass:
    """Derive the electrical meaning of a cross-rung tag link from the two
    rungs' actual chain contents -- see module and `netlist.py` docstrings
    for why this must not be a caller-supplied flag.
    """
    owner = netlist.rung(link.owner_rung)
    user = netlist.rung(link.user_rung)
    owner_comp = _find_component(owner, link.tag)
    user_comp = _find_component(user, link.tag)

    if owner_comp is not None and user_comp is not None:
        if owner_comp.kind == "terminal" and user_comp.kind == "terminal":
            return "terminal_crossing"
        if owner_comp.kind == "symbol" and user_comp.kind == "symbol":
            return "tag_echo"

    # At least one side is a bare "stub" (or the tag kinds disagree, which
    # only happens for a stub paired with a terminal/symbol -- also
    # genuinely severed, since a stub carries no physical anchor at all).
    return "severed_signal"


def _effective_bucket(rung: RungSpec, netlist: SystemNetlist) -> tuple[str, str]:
    """(role, function) used for partitioning purposes.

    Honors `RungSpec.pin_to_function` (the manual override hook): if set,
    adopts the role and function of any *other* rung already declared under
    that function name, so the pinned rung is bucketed exactly as if it were
    a native member of that group. `rung.role`/`rung.function` themselves are
    left untouched -- only where-it-gets-paged changes.
    """
    if rung.pin_to_function is None:
        return rung.role, rung.function
    for other in netlist.rungs:
        if other.key != rung.key and other.function == rung.pin_to_function:
            return other.role, other.function
    msg = f"{rung.key}: pin_to_function={rung.pin_to_function!r} matches no rung"
    raise CircuitValidationError(msg)


def _topological_build_order(
    rungs: tuple[RungSpec, ...], tag_links: tuple[TagLink, ...]
) -> list[str]:
    """Owner rungs before user rungs; otherwise preserves declaration order."""
    keys = [r.key for r in rungs]
    deps: dict[str, set[str]] = defaultdict(set)
    for link in tag_links:
        deps[link.user_rung].add(link.owner_rung)

    ordered: list[str] = []
    placed: set[str] = set()
    remaining = deque(keys)
    while remaining:
        progressed = False
        for _ in range(len(remaining)):
            key = remaining.popleft()
            if deps[key] <= placed:
                ordered.append(key)
                placed.add(key)
                progressed = True
            else:
                remaining.append(key)
        if not progressed:
            msg = f"cyclic tag dependency among rungs: {list(remaining)}"
            raise CircuitValidationError(msg)
    return ordered


def _group_by_function(
    rungs: list[RungSpec], bucket_of: dict[str, tuple[str, str]]
) -> list[list[RungSpec]]:
    """Groups rungs by effective function, first-seen order."""
    groups: dict[str, list[RungSpec]] = {}
    order: list[str] = []
    for r in rungs:
        _role, function = bucket_of[r.key]
        if function not in groups:
            groups[function] = []
            order.append(function)
        groups[function].append(r)
    return [groups[f] for f in order]


def _pack_groups(
    groups: list[list[RungSpec]],
    *,
    max_per_page: int,
    base_title: str,
    start_number: int,
    bucket_of: dict[str, tuple[str, str]],
) -> list[PageAssignment]:
    """Packs whole function-groups onto pages, greedily, budget-respecting.

    A group is never split across pages unless it alone exceeds the budget.
    """
    pages: list[PageAssignment] = []
    current: list[RungSpec] = []
    number = start_number

    def flush() -> None:
        nonlocal current, number
        if not current:
            return
        functions = sorted({bucket_of[r.key][1] for r in current})
        title = f"{base_title} ({', '.join(functions)})"
        pages.append(
            PageAssignment(
                number=number, title=title, rung_keys=tuple(r.key for r in current)
            )
        )
        number += 1
        current = []

    for group in groups:
        if len(group) > max_per_page:
            flush()
            for i in range(0, len(group), max_per_page):
                chunk = group[i : i + max_per_page]
                current = chunk
                flush()
            continue
        if len(current) + len(group) > max_per_page:
            flush()
        current.extend(group)
    flush()
    return pages


def _check_severed_signal_fanout(
    netlist: SystemNetlist, links_by_class: dict[LinkClass, list[TagLink]]
) -> None:
    """Raises if any severed-signal tag has fan-out beyond one owner/one user.

    `ref()` exposes exactly one port -- it is a chain terminus, not a branch
    point (see `electrical/symbols/references.py`). A tag reused by 3+ rungs
    with no physical terminal or symbol anchoring it cannot be rendered as
    off-page arrows without either duplicating arrows onto one port (not
    mechanically possible) or silently dropping references (misleading).
    Both are worse than refusing to partition and telling the caller to
    anchor the net at a terminal instead.
    """
    endpoints_by_tag: dict[str, set[str]] = defaultdict(set)
    for link in links_by_class["severed_signal"]:
        endpoints_by_tag[link.tag].add(link.owner_rung)
        endpoints_by_tag[link.tag].add(link.user_rung)

    for tag, rungs in endpoints_by_tag.items():
        if len(rungs) > 2:
            msg = (
                f"severed-signal tag {tag!r} is referenced by {len(rungs)} rungs "
                f"({sorted(rungs)}) with no physical terminal or symbol anchoring "
                "it. ref() exposes one port and cannot fan out beyond one owner "
                "and one user. Anchor this net at a physical terminal (so the "
                "crossing self-documents via terminal-id repetition, at any "
                "fan-out) instead of declaring it as a bare stub."
            )
            raise CircuitValidationError(msg)
    del netlist  # unused; kept for signature symmetry / future diagnostics


def partition_netlist_to_pages(
    netlist: SystemNetlist, *, max_rungs_per_page: int = MAX_RUNGS_PER_PAGE
) -> PartitionResult:
    """Split `netlist` into pages by structural role, then function.

    Returns page assignments, a topological rung build order (owners before
    users), and off-page connector markers for every `TagLink` classified as
    a severed signal (see `classify_link`) whose two sides land on different
    pages.

    Raises:
        CircuitValidationError: A rung's `pin_to_function` matches no other
            rung's `function`, or a severed-signal tag fans out to more than
            one owner+user pair (see `_check_severed_signal_fanout`), or the
            tag-link graph is cyclic.
    """
    bucket_of = {r.key: _effective_bucket(r, netlist) for r in netlist.rungs}

    power = [r for r in netlist.rungs if bucket_of[r.key][0] == "power"]
    control = [r for r in netlist.rungs if bucket_of[r.key][0] == "control"]
    terminal = [r for r in netlist.rungs if bucket_of[r.key][0] == "terminal"]

    pages: list[PageAssignment] = []
    # Every bucket (power included) groups by function before packing.
    # Round 1 packed the whole `power` list as one undifferentiated blob,
    # splitting it into arbitrary `max_rungs_per_page`-sized chunks in
    # declaration order -- harmless there, because every power rung had a
    # unique function name anyway. It stops being harmless once
    # `pin_to_function` can make a *control* rung share a *power* rung's
    # function: without function-grouping, the positional chunk cut can
    # (and, on this system's rung count, does) separate a pinned rung from
    # its target group again, silently defeating the override.
    pages += _pack_groups(
        _group_by_function(power, bucket_of),
        max_per_page=max_rungs_per_page,
        base_title="Power Distribution",
        start_number=len(pages) + 1,
        bucket_of=bucket_of,
    )
    pages += _pack_groups(
        _group_by_function(control, bucket_of),
        max_per_page=max_rungs_per_page,
        base_title="Control & Logic",
        start_number=len(pages) + 1,
        bucket_of=bucket_of,
    )
    pages += _pack_groups(
        _group_by_function(terminal, bucket_of),
        max_per_page=max_rungs_per_page,
        base_title="Terminal Strips",
        start_number=len(pages) + 1,
        bucket_of=bucket_of,
    )

    page_of: dict[str, int] = {}
    for page in pages:
        for key in page.rung_keys:
            page_of[key] = page.number

    links_by_class: dict[LinkClass, list[TagLink]] = {
        "terminal_crossing": [],
        "tag_echo": [],
        "severed_signal": [],
    }
    for link in netlist.tag_links:
        links_by_class[classify_link(netlist, link)].append(link)

    _check_severed_signal_fanout(netlist, links_by_class)

    markers: dict[str, list[OffPageMarker]] = defaultdict(list)
    plain_cross_refs: list[TagLink] = []
    terminal_crossings: list[TagLink] = []
    col_counter: dict[int, int] = defaultdict(int)

    def next_col(page_number: int) -> int:
        col_counter[page_number] += 1
        return col_counter[page_number]

    for link in links_by_class["tag_echo"]:
        if page_of[link.owner_rung] != page_of[link.user_rung]:
            plain_cross_refs.append(link)

    for link in links_by_class["terminal_crossing"]:
        if page_of[link.owner_rung] != page_of[link.user_rung]:
            terminal_crossings.append(link)

    for link in links_by_class["severed_signal"]:
        owner_page = page_of[link.owner_rung]
        user_page = page_of[link.user_rung]
        if owner_page == user_page:
            # Both stubs landed on the same page -- the two rungs are
            # already adjacent (or at least co-located); an arrow pointing
            # at "the page you're already reading" is noise, not signal, so
            # the stub renders as a plain chain terminus instead (see
            # `render_pages._build_rung`). Same page/no-marker treatment as
            # `terminal_crossing`/`tag_echo` links get above.
            continue
        owner_rung = netlist.rung(link.owner_rung)
        user_rung = netlist.rung(link.user_rung)
        owner_boundary: Literal["start", "end"] = (
            "end" if owner_rung.components[-1].id_or_prefix == link.tag else "start"
        )
        user_boundary: Literal["start", "end"] = (
            "start" if user_rung.components[0].id_or_prefix == link.tag else "end"
        )
        owner_col = next_col(owner_page)
        user_col = next_col(user_page)
        owner_dir: Literal["up", "down"] = "down" if owner_boundary == "end" else "up"
        user_dir: Literal["up", "down"] = "up" if user_boundary == "start" else "down"
        markers[link.owner_rung].append(
            OffPageMarker(
                tag=link.tag,
                boundary=owner_boundary,
                direction=owner_dir,
                label=f"/{user_page}.C{user_col}",
            )
        )
        markers[link.user_rung].append(
            OffPageMarker(
                tag=link.tag,
                boundary=user_boundary,
                direction=user_dir,
                label=f"/{owner_page}.C{owner_col}",
            )
        )

    build_order = _topological_build_order(netlist.rungs, netlist.tag_links)

    return PartitionResult(
        pages=tuple(pages),
        build_order=tuple(build_order),
        markers={k: tuple(v) for k, v in markers.items()},
        plain_cross_refs=tuple(plain_cross_refs),
        terminal_crossings=tuple(terminal_crossings),
    )
