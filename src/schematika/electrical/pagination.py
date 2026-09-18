"""Automatic multi-page splitting for electrical cabinet systems.

A cabinet system is described as a flat list of vertical "rungs" (the
Fuse -> Switch -> Coil chains `CircuitBuilder` already builds one at a
time) plus the tag reuses that link them (a contactor's coil on one rung,
its main contacts on another; a shared bus terminal repeated across many
rungs). `partition_netlist_to_pages` splits that list into pages by
structural role (power distribution first, then control/logic grouped by
function, then terminal strips), and decides which cross-rung links need a
rendered off-page connector (`electrical.symbols.references.ref`) versus
which resolve for free via a repeated terminal id or `reuse_tags`.

The role/function split is a heuristic and gets some rungs wrong on
purpose-built rungs whose electrical role doesn't match their structural
shape (e.g. a safety-permissive rung that gates a contactor is shaped
exactly like that contactor's own coil rung). `RungSpec.pin_to_function`
is the escape hatch for those: no automatic classifier can tell the two
apart from topology alone, so the model exposes an explicit override
instead of guessing.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from schematika.core.exceptions import CircuitValidationError
from schematika.core.options import BuildOptions, SymbolConfig, TerminalConfig
from schematika.core.state import create_initial_state
from schematika.electrical.builder import CircuitBuilder
from schematika.electrical.symbols.references import ref as offpage_ref

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from schematika.core.state import GenerationState
    from schematika.electrical.builder_models import BuildResult

DEFAULT_MAX_RUNGS_PER_PAGE = 5

ComponentKind = Literal["terminal", "symbol", "stub"]
LinkClass = Literal["terminal_crossing", "tag_echo", "severed_signal"]

_COLUMN_SPACING_1P = 80.0
_COLUMN_SPACING_3P = 220.0
_THREE_PHASE_POLES = 3
_OFFPAGE_MARKER_PAIR_SIZE = 2


@dataclass(frozen=True)
class ComponentSpec:
    """One link in a rung's chain: a physical terminal, a symbol, or a stub.

    A ``"stub"`` carries no ports of its own — it declares "this chain end
    is genuinely severed here"; :func:`partition_netlist_to_pages` replaces
    it with a rendered `ref()` off-page connector, or nothing at all if the
    link it terminates never crosses a page boundary.

    Examples:
        >>> ComponentSpec(kind="terminal", id_or_prefix="X1")
        ComponentSpec(kind='terminal', id_or_prefix='X1', poles=1, symbol_fn=None)
    """

    kind: ComponentKind
    id_or_prefix: str
    poles: int = 1
    symbol_fn: Callable[..., Any] | None = None  # only for kind="symbol"


@dataclass(frozen=True)
class RungSpec:
    """One vertical chain — the atomic unit both build and page.

    `pin_to_function` is the manual override hook for the ambiguous-role
    problem: when set, this rung is bucketed as if it belonged to the named
    function group instead of its own, for paging purposes only —
    `role`/`function` stay unchanged for display and `CircuitBuilder`
    construction. `None` (the default) uses automatic bucketing.

    Examples:
        >>> RungSpec("r1", "power", "incomer", "Incomer",
        ...          (ComponentSpec("terminal", "X1"),)).function
        'incomer'
    """

    key: str
    role: Literal["power", "control", "terminal"]
    function: str
    title: str
    components: tuple[ComponentSpec, ...]
    pin_to_function: str | None = None


@dataclass(frozen=True)
class TagLink:
    """`tag` is first defined on `owner_rung` and reused on `user_rung`.

    The electrical meaning of the crossing (terminal repeat / tag echo /
    severed signal) is derived by :func:`classify_link` from what
    `ComponentSpec.kind` the tag resolves to on each rung — not declared
    here — so the same physical tag can't be classified inconsistently at
    different crossings.

    Examples:
        >>> TagLink(tag="X4", owner_rung="loop_1", user_rung="loop_2")
        TagLink(tag='X4', owner_rung='loop_1', user_rung='loop_2')
    """

    tag: str
    owner_rung: str
    user_rung: str


@dataclass(frozen=True)
class SystemNetlist:
    """A full cabinet system: every rung plus their cross-rung tag links.

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("r1", "power", "incomer", "Incomer",
        ...              (ComponentSpec("terminal", "X1"),)),
        ... ))
        >>> netlist.rung("r1").title
        'Incomer'
    """

    rungs: tuple[RungSpec, ...]
    tag_links: tuple[TagLink, ...] = ()

    def rung(self, key: str, /) -> RungSpec:
        """Look up a rung by key."""
        for r in self.rungs:
            if r.key == key:
                return r
        msg = f"no rung with key {key!r}"
        raise CircuitValidationError(msg)


@dataclass(frozen=True)
class OffPageMarker:
    """One half of an off-page connector pair, attached to one rung's chain end.

    `label` names the page/column a reader should jump to.

    Examples:
        >>> OffPageMarker(tag="WD", boundary="end", direction="down", label="/5.C1")
        OffPageMarker(tag='WD', boundary='end', direction='down', label='/5.C1')
    """

    tag: str
    boundary: Literal["start", "end"]
    direction: Literal["up", "down"]  # "up" = jump-in, "down" = jump-out
    label: str  # e.g. "/3.C2"


@dataclass(frozen=True)
class PageAssignment:
    """One page's worth of rungs, in render order.

    Examples:
        >>> PageAssignment(number=1, title="Power", rung_keys=("incomer",)).number
        1
    """

    number: int
    title: str
    rung_keys: tuple[str, ...]


@dataclass(frozen=True)
class PartitionResult:
    """The full output of `partition_netlist_to_pages`.

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("r1", "power", "incomer", "Incomer",
        ...              (ComponentSpec("terminal", "X1"),)),
        ... ))
        >>> partition_netlist_to_pages(netlist).pages[0].title
        'Power Distribution (incomer)'
    """

    pages: tuple[PageAssignment, ...]
    build_order: tuple[str, ...]
    markers: dict[str, tuple[OffPageMarker, ...]] = field(default_factory=dict)
    plain_cross_refs: tuple[TagLink, ...] = ()
    terminal_crossings: tuple[TagLink, ...] = ()


def _find_component(rung: RungSpec, tag: str) -> ComponentSpec | None:
    for comp in rung.components:
        if comp.id_or_prefix == tag:
            return comp
    return None


def classify_link(netlist: SystemNetlist, link: TagLink) -> LinkClass:
    """Derive the electrical meaning of a cross-rung tag link.

    Args:
        netlist: The system `link` belongs to.
        link: The cross-rung tag reuse to classify.

    Returns:
        ``"terminal_crossing"`` if both sides are the same physical
        terminal (never a marker, at any fan-out); ``"tag_echo"`` if both
        sides are a component tag (`reuse_tags` already resolves it, never
        a marker); ``"severed_signal"`` otherwise (at least one side is a
        bare ``"stub"`` — this is the only case a `ref()` marker is used).

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("a", "power", "fa", "A", (ComponentSpec("terminal", "X4"),)),
        ...     RungSpec("b", "power", "fb", "B", (ComponentSpec("terminal", "X4"),)),
        ... ))
        >>> classify_link(netlist, TagLink("X4", "a", "b"))
        'terminal_crossing'
    """
    owner_comp = _find_component(netlist.rung(link.owner_rung), link.tag)
    user_comp = _find_component(netlist.rung(link.user_rung), link.tag)

    if owner_comp is not None and user_comp is not None:
        if owner_comp.kind == "terminal" and user_comp.kind == "terminal":
            return "terminal_crossing"
        if owner_comp.kind == "symbol" and user_comp.kind == "symbol":
            return "tag_echo"
    return "severed_signal"


def _effective_bucket(rung: RungSpec, netlist: SystemNetlist) -> tuple[str, str]:
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
    groups: dict[str, list[RungSpec]] = {}
    for r in rungs:
        groups.setdefault(bucket_of[r.key][1], []).append(r)
    return list(groups.values())


def _pack_groups(
    groups: list[list[RungSpec]],
    *,
    max_per_page: int,
    base_title: str,
    start_number: int,
    bucket_of: dict[str, tuple[str, str]],
) -> list[PageAssignment]:
    """Packs whole function-groups onto pages.

    A group only splits across pages if it alone exceeds the budget.
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
                current = group[i : i + max_per_page]
                flush()
            continue
        if len(current) + len(group) > max_per_page:
            flush()
        current.extend(group)
    flush()
    return pages


def _page_numbers(pages: Sequence[PageAssignment]) -> dict[str, int]:
    return {key: page.number for page in pages for key in page.rung_keys}


def _check_severed_signal_fanout(links: list[TagLink]) -> None:
    """Raise if a severed-signal tag is referenced by more than one owner+user pair.

    `ref()` exposes exactly one port — a chain terminus, not a branch
    point — so a wider fan-out can't be rendered without duplicating
    arrows onto one port. This refuses up front with an actionable message
    instead of silently producing an unrenderable layout.
    """
    endpoints_by_tag: dict[str, set[str]] = defaultdict(set)
    for link in links:
        endpoints_by_tag[link.tag].add(link.owner_rung)
        endpoints_by_tag[link.tag].add(link.user_rung)

    for tag, rungs in endpoints_by_tag.items():
        if len(rungs) > _OFFPAGE_MARKER_PAIR_SIZE:
            msg = (
                f"severed-signal tag {tag!r} is referenced by {len(rungs)} rungs "
                f"({sorted(rungs)}) with no physical terminal or symbol anchoring "
                "it. ref() exposes one port and cannot fan out beyond one owner "
                "and one user. Anchor this net at a physical terminal (so the "
                "crossing self-documents via terminal-id repetition, at any "
                "fan-out) instead of declaring it as a bare stub."
            )
            raise CircuitValidationError(msg)


def partition_netlist_to_pages(
    netlist: SystemNetlist, *, max_rungs_per_page: int = DEFAULT_MAX_RUNGS_PER_PAGE
) -> PartitionResult:
    """Split `netlist` into pages by structural role, then function.

    Args:
        netlist: The full rung-level system to partition.
        max_rungs_per_page: Page budget; a function group only splits
            across pages if it alone exceeds this.

    Returns:
        Page assignments, a topological rung build order (owners before
        users), and off-page connector markers for every `TagLink`
        classified `"severed_signal"` (see `classify_link`) whose two
        sides land on different pages.

    Raises:
        CircuitValidationError: A rung's `pin_to_function` matches no other
            rung's `function`; a severed-signal tag fans out to more than
            one owner+user pair; or the tag-link graph is cyclic.

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("r1", "power", "incomer", "Incomer",
        ...              (ComponentSpec("terminal", "X1"),)),
        ... ))
        >>> len(partition_netlist_to_pages(netlist).pages)
        1
    """
    bucket_of = {r.key: _effective_bucket(r, netlist) for r in netlist.rungs}

    power = [r for r in netlist.rungs if bucket_of[r.key][0] == "power"]
    control = [r for r in netlist.rungs if bucket_of[r.key][0] == "control"]
    terminal = [r for r in netlist.rungs if bucket_of[r.key][0] == "terminal"]

    pages: list[PageAssignment] = []
    # Every bucket groups by function before packing — including power.
    # Packing power as one undifferentiated blob (chunked in declaration
    # order) is harmless when every power rung has a unique function name,
    # but silently defeats `pin_to_function`: the override changes a
    # rung's effective *function*, and an arbitrary positional chunk
    # boundary can separate a pinned rung from the group it was pinned to.
    for bucket, title in (
        (power, "Power Distribution"),
        (control, "Control & Logic"),
        (terminal, "Terminal Strips"),
    ):
        pages += _pack_groups(
            _group_by_function(bucket, bucket_of),
            max_per_page=max_rungs_per_page,
            base_title=title,
            start_number=len(pages) + 1,
            bucket_of=bucket_of,
        )

    page_of = _page_numbers(pages)

    links_by_class: dict[LinkClass, list[TagLink]] = defaultdict(list)
    for link in netlist.tag_links:
        links_by_class[classify_link(netlist, link)].append(link)

    _check_severed_signal_fanout(links_by_class["severed_signal"])

    markers: dict[str, list[OffPageMarker]] = defaultdict(list)
    col_counter: dict[int, int] = defaultdict(int)

    def next_col(page_number: int) -> int:
        col_counter[page_number] += 1
        return col_counter[page_number]

    def _crosses(link: TagLink) -> bool:
        return page_of[link.owner_rung] != page_of[link.user_rung]

    plain_cross_refs = [link for link in links_by_class["tag_echo"] if _crosses(link)]
    terminal_crossings = [
        link for link in links_by_class["terminal_crossing"] if _crosses(link)
    ]

    for link in links_by_class["severed_signal"]:
        owner_page = page_of[link.owner_rung]
        user_page = page_of[link.user_rung]
        if owner_page == user_page:
            # Both stubs already on the same page — a marker pointing at
            # the page the reader is already on would be noise.
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

    return PartitionResult(
        pages=tuple(pages),
        build_order=tuple(_topological_build_order(netlist.rungs, netlist.tag_links)),
        markers={k: tuple(v) for k, v in markers.items()},
        plain_cross_refs=tuple(plain_cross_refs),
        terminal_crossings=tuple(terminal_crossings),
    )


def _rung_width(rung: RungSpec) -> float:
    poles = max((c.poles for c in rung.components), default=1)
    return _COLUMN_SPACING_3P if poles >= _THREE_PHASE_POLES else _COLUMN_SPACING_1P


def _column_positions(
    partition: PartitionResult, netlist: SystemNetlist
) -> dict[str, float]:
    """Left-to-right cumulative x-offset per rung, reset at each page.

    Deliberately simple placeholder: real page-internal placement belongs
    to a placement/routing engine, not this module — see
    `docs/research/layout-improvement/RECOMMENDATION.md`.
    """
    x_of: dict[str, float] = {}
    for page in partition.pages:
        cursor = 0.0
        for key in page.rung_keys:
            x_of[key] = cursor
            cursor += _rung_width(netlist.rung(key))
    return x_of


def _build_rung(
    rung: RungSpec,
    state: GenerationState,
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
                comp.id_or_prefix, config=TerminalConfig(poles=comp.poles)
            )
        elif comp.kind == "symbol":
            if comp.symbol_fn is None:
                msg = f"symbol component {comp.id_or_prefix!r} has no symbol_fn"
                raise CircuitValidationError(msg)
            builder.add_symbol(
                comp.symbol_fn,
                config=SymbolConfig(tag_prefix=comp.id_or_prefix, poles=comp.poles),
            )
        else:  # "stub"
            marker = markers_here.get(comp.id_or_prefix)
            if marker is not None:
                builder.add_symbol(
                    offpage_ref,
                    config=SymbolConfig(
                        tag_prefix="REF",
                        factory_kwargs={
                            "label": marker.label,
                            "direction": marker.direction,
                        },
                    ),
                )
            # else: both sides of this severed-signal link landed on the
            # same page — the stub terminates the chain with no marker.

    return builder.build(options=BuildOptions(count=1, reuse_tags=reuse_tags or None))


def _build_all_rungs(
    netlist: SystemNetlist, partition: PartitionResult
) -> dict[str, BuildResult]:
    """Builds every rung in topological order, wiring up tag reuse."""
    rungs_by_key = {r.key: r for r in netlist.rungs}
    x_of = _column_positions(partition, netlist)

    owner_of: dict[tuple[str, str], str] = {}
    for link in netlist.tag_links:
        if classify_link(netlist, link) == "tag_echo":
            owner_of[(link.user_rung, link.tag)] = link.owner_rung

    results: dict[str, BuildResult] = {}
    state = create_initial_state()

    for key in partition.build_order:
        rung = rungs_by_key[key]
        markers_here = {m.tag: m for m in partition.markers.get(key, ())}

        reuse_tags: dict[str, BuildResult] = {}
        for comp in rung.components:
            if comp.kind != "symbol":
                continue
            owner_key = owner_of.get((rung.key, comp.id_or_prefix))
            if owner_key is not None:
                reuse_tags[comp.id_or_prefix] = results[owner_key]

        result = _build_rung(
            rung, state, x=x_of[key], markers_here=markers_here, reuse_tags=reuse_tags
        )
        results[key] = result
        state = result.state

    return results


@dataclass(frozen=True)
class PartitionedElectricalResult:
    """Frozen result of partitioning and building a whole rung-level netlist.

    Shape mirrors `PCBBuildResult`: `partition` describes page structure
    (comparable to `PCBBuildResult.pages`), `circuit_results` is the
    already-built-piece lookup (comparable to `PCBBuildResult.connector_blocks`).

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("r1", "power", "incomer", "Incomer",
        ...              (ComponentSpec("terminal", "X1"),)),
        ... ))
        >>> result = partition_to_pages(netlist)
        >>> list(result.circuit_results)
        ['r1']
    """

    partition: PartitionResult
    circuit_results: dict[str, BuildResult]


def partition_to_pages(
    netlist: SystemNetlist, *, max_rungs_per_page: int = DEFAULT_MAX_RUNGS_PER_PAGE
) -> PartitionedElectricalResult:
    """Partition a rung-level netlist into pages and build every rung.

    A free function, not a builder method: unlike `CircuitBuilder`, which
    accumulates one rung's components incrementally across many calls,
    there's no meaningful partial state between "have a `SystemNetlist`"
    and "have every rung built and paged" — the whole rung graph is known
    upfront in one call, the same shape as `pcb.build(circuit, mapping)`.

    Args:
        netlist: The full rung-level system to partition.
        max_rungs_per_page: Forwarded to `partition_netlist_to_pages`.

    Returns:
        Page assignments plus every rung's built `BuildResult`, ready to
        hand to `Project.add_partition`.

    Raises:
        CircuitValidationError: See `partition_netlist_to_pages`.

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("r1", "power", "incomer", "Incomer",
        ...              (ComponentSpec("terminal", "X1"),)),
        ... ))
        >>> result = partition_to_pages(netlist)
        >>> result.circuit_results["r1"].used_terminals
        ['X1']
    """
    partition = partition_netlist_to_pages(
        netlist, max_rungs_per_page=max_rungs_per_page
    )
    circuit_results = _build_all_rungs(netlist, partition)
    return PartitionedElectricalResult(
        partition=partition, circuit_results=circuit_results
    )


@dataclass(frozen=True)
class CrossPageFinding:
    """One violation found by `check_offpage_connector_coherence`.

    Examples:
        >>> CrossPageFinding(kind="missing_offpage_pair", message="tag 'X' ...").kind
        'missing_offpage_pair'
    """

    kind: str
    message: str


def check_offpage_connector_coherence(
    netlist: SystemNetlist, partition: PartitionResult
) -> tuple[CrossPageFinding, ...]:
    """Verify every cross-page severed-signal net has exactly one coherent marker pair.

    No `terminal_crossing`/`tag_echo` link should ever get one. Geometric
    layout checks (orthogonality, collisions) can't see this —
    it's a check on the partition model itself, not on rendered geometry.

    Args:
        netlist: The system `partition` was computed from.
        partition: The result of `partition_netlist_to_pages`.

    Returns:
        One `CrossPageFinding` per violation. Empty means clean.

    Examples:
        >>> netlist = SystemNetlist(rungs=(
        ...     RungSpec("r1", "power", "incomer", "Incomer",
        ...              (ComponentSpec("terminal", "X1"),)),
        ... ))
        >>> partition = partition_netlist_to_pages(netlist)
        >>> check_offpage_connector_coherence(netlist, partition)
        ()
    """
    findings: list[CrossPageFinding] = []
    page_of = _page_numbers(partition.pages)

    tag_to_link = {link.tag: link for link in netlist.tag_links}
    severed_tags = {
        link.tag
        for link in netlist.tag_links
        if classify_link(netlist, link) == "severed_signal"
    }

    markers_by_tag: dict[str, list[tuple[str, str]]] = defaultdict(list)
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
                            "not severed_signal"
                        ),
                    )
                )

    for tag in severed_tags:
        link = tag_to_link[tag]
        if page_of[link.owner_rung] == page_of[link.user_rung]:
            continue
        occurrences = markers_by_tag.get(tag, [])
        if not occurrences:
            findings.append(
                CrossPageFinding(
                    kind="missing_offpage_pair",
                    message=f"tag {tag!r} crosses a page boundary but has no marker",
                )
            )
        elif len(occurrences) < _OFFPAGE_MARKER_PAIR_SIZE:
            findings.append(
                CrossPageFinding(
                    kind="incomplete_offpage_pair",
                    message=f"tag {tag!r} has only one marker (expected a pair)",
                )
            )
        elif len(occurrences) > _OFFPAGE_MARKER_PAIR_SIZE:
            findings.append(
                CrossPageFinding(
                    kind="duplicated_offpage_markers",
                    message=(
                        f"tag {tag!r} has {len(occurrences)} markers — "
                        "ref() cannot render more than one pair"
                    ),
                )
            )
        else:
            (rung_a, label_a), (rung_b, label_b) = occurrences
            page_a, page_b = page_of[rung_a], page_of[rung_b]
            if not (
                label_a.startswith(f"/{page_b}.") and label_b.startswith(f"/{page_a}.")
            ):
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
