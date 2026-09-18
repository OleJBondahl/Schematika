"""Rule-based page partitioner for a rung-level electrical netlist.

Implements the "Automatic Page Partitioning Rules" from the Gemini research
conversation (`Optimizing Code-Generated Electrical Schematic Layouts.md`,
"Page Budgeting and Pagination Architecture" section, repo root):

    1. Primary power distribution goes on the earliest page(s).
    2. Control/logic is grouped by function, packed onto pages up to a rung
       budget, never splitting a function group across pages.
    3. Terminal strips get their own dedicated page(s).
    4. A net that spans a chosen page boundary gets truncated and replaced
       with an off-page connector marker carrying source/destination page
       and a stable column label (e.g. "/3.C2").

See `netlist.py` for why rule 4 only fires for `TagLink`s with a boundary
set (a severed wire), never for a bare component-tag echo.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from netlist import RungSpec, SystemNetlist, TagLink

MAX_RUNGS_PER_PAGE = 4


@dataclass(frozen=True)
class OffPageMarker:
    """One half of an off-page connector pair, attached to one rung's chain
    end. `label` names the *other* page/column -- what a reader should jump
    to -- not this one.
    """

    tag: str
    boundary: str  # "start" | "end"
    direction: str  # "up" (jump-in, placed at chain start) | "down" (jump-out)
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
    plain_cross_refs: tuple[TagLink, ...]  # tag echoes, no marker inserted


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
    remaining = deque(keys)  # already in declaration order
    # Simple stable Kahn's algorithm: repeatedly take the earliest-declared
    # rung whose dependencies are already placed.
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
            raise ValueError(msg)
    return ordered


def _group_by_function(rungs: list[RungSpec]) -> list[list[RungSpec]]:
    """Groups consecutive-in-declaration rungs by function, first-seen order."""
    groups: dict[str, list[RungSpec]] = {}
    order: list[str] = []
    for r in rungs:
        if r.function not in groups:
            groups[r.function] = []
            order.append(r.function)
        groups[r.function].append(r)
    return [groups[f] for f in order]


def _pack_groups(
    groups: list[list[RungSpec]],
    *,
    max_per_page: int,
    base_title: str,
    start_number: int,
) -> list[PageAssignment]:
    """Packs whole function-groups onto pages, greedily, budget-respecting.

    A group is never split across pages unless it alone exceeds the budget
    (then it gets its own overflow page(s) -- a caveat worth flagging to a
    human, not silently hidden).
    """
    pages: list[PageAssignment] = []
    current: list[RungSpec] = []
    number = start_number

    def flush() -> None:
        nonlocal current, number
        if not current:
            return
        functions = sorted({r.function for r in current})
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
            # Oversized single function: split it, but this is exactly the
            # "a control loop wants to straddle pages" case flagged in the
            # findings doc -- pack_groups does the mechanical split, a human
            # would rethink the function boundary instead.
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


def partition_netlist_to_pages(
    netlist: SystemNetlist, *, max_rungs_per_page: int = MAX_RUNGS_PER_PAGE
) -> PartitionResult:
    """Split `netlist` into pages by structural role, then function.

    Returns page assignments, a topological rung build order (owners before
    users), and off-page connector markers for every `TagLink` whose two
    sides land on different pages *and* whose boundary marks a severed wire
    (see `netlist.TagLink`).
    """
    power = [r for r in netlist.rungs if r.role == "power"]
    control = [r for r in netlist.rungs if r.role == "control"]
    terminal = [r for r in netlist.rungs if r.role == "terminal"]

    pages: list[PageAssignment] = []
    pages += _pack_groups(
        [power] if power else [],
        max_per_page=max_rungs_per_page,
        base_title="Power Distribution",
        start_number=len(pages) + 1,
    )
    pages += _pack_groups(
        _group_by_function(control),
        max_per_page=max_rungs_per_page,
        base_title="Control & Logic",
        start_number=len(pages) + 1,
    )
    pages += _pack_groups(
        _group_by_function(terminal),
        max_per_page=max_rungs_per_page,
        base_title="Terminal Strips",
        start_number=len(pages) + 1,
    )

    page_of: dict[str, int] = {}
    for page in pages:
        for key in page.rung_keys:
            page_of[key] = page.number

    markers: dict[str, list[OffPageMarker]] = defaultdict(list)
    plain_cross_refs: list[TagLink] = []
    col_counter: dict[int, int] = defaultdict(int)

    def next_col(page_number: int) -> int:
        col_counter[page_number] += 1
        return col_counter[page_number]

    for link in netlist.tag_links:
        owner_page = page_of[link.owner_rung]
        user_page = page_of[link.user_rung]
        if link.owner_boundary is None or link.user_boundary is None:
            # Tag echo: reuse_tags resolves it regardless of page. No marker.
            if owner_page != user_page:
                plain_cross_refs.append(link)
            continue
        if owner_page == user_page:
            # Severed-wire tag, but it didn't actually cross a page boundary
            # this time -- no marker needed, plain chain connection suffices.
            continue
        owner_col = next_col(owner_page)
        user_col = next_col(user_page)
        owner_dir = "down" if link.owner_boundary == "end" else "up"
        user_dir = "up" if link.user_boundary == "start" else "down"
        markers[link.owner_rung].append(
            OffPageMarker(
                tag=link.tag,
                boundary=link.owner_boundary,
                direction=owner_dir,
                label=f"/{user_page}.C{user_col}",
            )
        )
        markers[link.user_rung].append(
            OffPageMarker(
                tag=link.tag,
                boundary=link.user_boundary,
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
    )
