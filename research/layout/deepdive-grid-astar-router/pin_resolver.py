"""(tag, semantic_pin_label, role) -> real Symbol.Port id resolver.

Round 2 of the `grid-astar-router` research spike. Round 1's sibling track
`elk-bridge` found and documented the underlying bug (see
`docs/research/layout-improvement/elk-bridge.md` and
`research/layout/elk-bridge/to_elk.py::build_pin_resolver`, which this module
started as a direct port of): `BuildResult.wire_connections` logs *semantic*
pin labels (a symbol factory's declared `*_pins`/`pins` default, e.g.
contactor's `"L1"`/`"T1"`), while `Symbol.ports` is keyed *positionally*
(`"1".."N"`) regardless of those labels. The two id spaces are not the same
string space, so a naive `symbol.ports[pin_label]` lookup on a real
`BuildResult` fails for any non-trivial symbol (confirmed on `contactor` and
`motor` in this repo's own doctests).

Two-phase resolution, not a lazy one-call-at-a-time heuristic (that was
elk-bridge's original design and round 2 found a real bug in it -- see
`build_large_cabinet`'s `contactor` branch: a lazy left-to-right pool walk
assigned `K1`'s first "source" label (`"T1"`, a pole-1 power contact) to the
coil's `A2` return terminal, because `A2` happened to sit further left than
any contact pin in the *unfiltered* x-sorted pool -- physically wrong, not
just "a guess"):

1. Exact matches first: if a semantic label IS literally one of the tag's
   real port ids (true whenever a factory's `pins`/`*_pins` default already
   equals its port dict keys -- true for `coil`'s `A1`/`A2`, `fuse`'s
   `1`/`2`, most single-purpose symbols), claim that port immediately and
   remove it from the position pool. This is not a guess.
2. Position-heuristic fallback, over the pool with step-1's exact matches
   already removed: the remaining, unclaimed real ports are split into
   up-facing (`direction.dy < 0`, target/input side) and down-facing
   (`direction.dy > 0`, source/output side), sorted left-to-right by x, and
   assigned to the remaining unresolved (tag, label, role) queries in
   first-seen order.

Every resolution is tagged `"exact"` or `"heuristic"` in the returned
`resolution_kind` map, so a caller can report how much of a large circuit's
wiring rests on a guess rather than a certainty -- see `topology_bridge.py`
and the deep-dive doc's quality section for how that number is used.

Not production code. Throwaway research spike, not imported by `src/schematika`.
"""

from __future__ import annotations

from typing import Any

from schematika.core.symbol import Symbol

Query = tuple[str, str, str]  # (tag, label, role); role is "source" or "target"


def build_pin_resolver(
    elements: list[Any],
    queries: list[Query],
) -> tuple[dict[Query, str | None], dict[Query, str], list[Query]]:
    """Resolve every (tag, label, role) query to a real port id, in one pass.

    Args:
        elements: A flat list of placed elements (e.g.
            ``BuildResult.circuit.elements``). Only labeled ``Symbol``
            instances (including ``TerminalSymbol``/``TerminalBlock``, both
            ``Symbol`` subclasses) contribute ports; everything else is
            ignored.
        queries: Every ``(tag, label, role)`` triple that needs a real port,
            in the order they should be assigned when more than one falls
            back to the position heuristic (first-seen order matters for
            reproducibility, not correctness -- see ``Limits``).

    Returns:
        ``(resolved, resolution_kind, unresolved)``. ``resolved[query]`` is
        the real port id, or ``None`` if the tag's pool for that role was
        exhausted. ``resolution_kind[query]`` is ``"exact"`` when the label
        was literally a real port id, ``"heuristic"`` when it came from
        position order. ``unresolved`` lists every query that resolved to
        ``None``.

    Limits (see the deep-dive doc for detail and real examples hit while
    building the large-cabinet test circuit):

    1. The position heuristic is order-only, not name-aware, once past the
       exact-match check: two labels that both miss a literal match are
       assigned in first-seen order from whatever real ports are left,
       with no check that the assignment is physically sensible.
    2. Direction-classified pools assume every port is purely vertical
       (`direction.dy` dominates). A symbol with horizontal-only ports
       (`dy == 0` for all ports) produces two empty pools and every
       heuristic resolution for that tag fails.
    3. A pool can run out before the label list does -- this is the `motor`
       bug: the `poles*2` pin-count fallback generates more semantic labels
       than the symbol has real ports for. When that happens the query
       resolves to `None` and lands in `unresolved`, the correct, safe
       outcome (the caller drops that wire rather than routing to a
       nonexistent port).
    4. Exact-match removal is global per tag, not per role: if the same
       real port id is legitimately usable from both a "source" and a
       "target" query (not hit by any symbol in this spike), the first
       query to claim it via exact match removes it from *both* pools.
    """
    ports_by_tag: dict[str, dict[str, Any]] = {}
    for elem in elements:
        # isinstance, not a type-name/duck-typing check: TerminalSymbol and
        # TerminalBlock (electrical/symbols/terminals.py) subclass Symbol and
        # must be included here too -- an earlier version of this file used
        # `type(elem).__name__ == "Symbol"` (copied from the sibling
        # svg-geometry-linter track, which deliberately avoids a hard import
        # dependency) and silently dropped every terminal from both the pin
        # pools and the obstacle set. Caught by `large_cabinet.py`'s own
        # component-count check, not by inspection.
        if not isinstance(elem, Symbol) or elem.label is None:
            continue
        ports_by_tag[elem.label] = dict(elem.ports)

    resolved: dict[Query, str | None] = {}
    resolution_kind: dict[Query, str] = {}
    unresolved: list[Query] = []
    claimed: dict[str, set[str]] = {}  # tag -> real port ids already spoken for

    # Phase 1: exact matches. A label that is literally a real port id is
    # not a guess -- true whenever a factory's declared pins already equal
    # its port dict keys (coil A1/A2, fuse 1/2, most single-purpose symbols).
    remaining: list[Query] = []
    for query in queries:
        tag, label, _role = query
        real_ports = ports_by_tag.get(tag, {})
        if label in real_ports:
            resolved[query] = label
            resolution_kind[query] = "exact"
            claimed.setdefault(tag, set()).add(label)
        else:
            remaining.append(query)

    # Phase 2: position heuristic over the ports each tag has left.
    up_pool: dict[str, list] = {}
    down_pool: dict[str, list] = {}
    for tag, ports in ports_by_tag.items():
        free = [p for pid, p in ports.items() if pid not in claimed.get(tag, set())]
        up_pool[tag] = sorted(
            (p for p in free if p.direction.dy < 0), key=lambda p: p.position.x
        )
        down_pool[tag] = sorted(
            (p for p in free if p.direction.dy > 0), key=lambda p: p.position.x
        )

    seen_index: dict[tuple[str, str], int] = {}
    label_cache: dict[tuple[str, str], str | None] = {}
    for query in remaining:
        tag, label, role = query
        cache_key = (tag, label)
        if cache_key in label_cache:
            port_id = label_cache[cache_key]
            resolved[query] = port_id
            if port_id is not None:
                resolution_kind[query] = "heuristic"
            else:
                unresolved.append(query)
            continue

        pool = down_pool.get(tag, []) if role == "source" else up_pool.get(tag, [])
        idx = seen_index.get((tag, role), 0)
        seen_index[(tag, role)] = idx + 1
        if idx >= len(pool):
            resolved[query] = None
            label_cache[cache_key] = None
            unresolved.append(query)
            continue

        port_id = pool[idx].id
        resolved[query] = port_id
        resolution_kind[query] = "heuristic"
        label_cache[cache_key] = port_id

    return resolved, resolution_kind, unresolved
