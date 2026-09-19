"""(tag, semantic_pin_label, role) -> real Symbol.Port id resolver.

`BuildResult.wire_connections` logs *semantic* pin labels (a symbol factory's
declared `*_pins`/`pins` default, e.g. contactor's `"L1"`/`"T1"`), while
`Symbol.ports` is keyed *positionally* (`"1".."N"`) regardless of those
labels -- so a naive `symbol.ports[pin_label]` lookup fails for any
non-trivial symbol.

Two-phase resolution, not a lazy one-call-at-a-time heuristic: a one-pass,
order-only pool walk assigns a contactor's first "source"-role query to
whichever port happens to sort first by x -- physically wrong when the coil
sits left of the power contacts, because the down-facing pool becomes
`[A2, T1, T2, T3]` and the *coil return* gets treated as a power contact.
Fixed by:

1. Exact matches first: if a semantic label IS literally one of the tag's
   real port ids (true for `coil`'s `A1`/`A2`, `fuse`'s `1`/`2`), claim that
   port immediately and remove it from the position pool -- not a guess.
2. Position-heuristic fallback, over the pool with step 1's exact matches
   already removed: remaining ports are split into up-facing
   (`direction.dy < 0`, target/input side) and down-facing
   (`direction.dy > 0`, source/output side), sorted left-to-right by x, and
   assigned to the remaining unresolved queries in first-seen order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schematika.core.symbol import Symbol

if TYPE_CHECKING:
    from collections.abc import Sequence

Query = tuple[str, str, str]  # (tag, label, role); role is "source" or "target"


def _merge_ports_by_tag(elements: Sequence[Any]) -> dict[str, dict[str, Any]]:
    """Pool every labeled `Symbol`'s ports per tag, dropping ambiguous ids.

    A tag can legitimately name more than one physical symbol instance (a
    relay's coil and its SPDT contact drawn as separate symbols both tagged
    "K8", each with disjoint port ids) -- merge each tag's instances into one
    port pool instead of letting the last instance silently replace the rest.
    A specific port id claimed by *more than one* instance under the same tag
    (e.g. a fixed reference symbol repeated once per identical sub-circuit
    instance) is genuinely ambiguous and is dropped from the pool entirely,
    rather than resolved to whichever instance came last.
    """
    ports_by_tag: dict[str, dict[str, Any]] = {}
    ambiguous: set[tuple[str, str]] = set()
    for elem in elements:
        if not isinstance(elem, Symbol) or elem.label is None:
            continue
        pool = ports_by_tag.setdefault(elem.label, {})
        for port_id, port in elem.ports.items():
            if port_id in pool:
                ambiguous.add((elem.label, port_id))
            else:
                pool[port_id] = port
    for tag, port_id in ambiguous:
        del ports_by_tag[tag][port_id]
    return ports_by_tag


def build_pin_resolver(
    elements: Sequence[Any],
    queries: Sequence[Query],
) -> tuple[dict[Query, str | None], dict[Query, str]]:
    """Resolve every (tag, label, role) query to a real port id, in one pass.

    Only labeled `Symbol` instances in *elements* contribute ports; queries
    are assigned in first-seen order, so the result is reproducible.

    Returns:
        `(resolved, resolution_kind)`. `resolved[query]` is the real port id,
        or `None` when the tag's pool for that role was exhausted.
        `resolution_kind[query]` is `"exact"` when the label was literally a
        real port id and `"heuristic"` when it came from position order; an
        unresolved query has no entry.

    Limits (real, not speculative -- hit while building the round-2 spike's
    98/152-component test cabinets, see `electrical/layout/router.py`):

    1. The position heuristic is order-only, not name-aware, once past the
       exact-match check: two labels that both miss a literal match are
       assigned in first-seen order from whatever real ports are left, with
       no check that the assignment is physically sensible.
    2. Direction-classified pools assume every port is purely vertical
       (`direction.dy` dominates). A symbol with horizontal-only ports
       (`dy == 0` for all ports) produces two empty pools and every
       heuristic resolution for that tag fails.
    3. A pool can run out before the label list does (e.g. a poles-derived
       label count exceeding the symbol's real port count) -- the query
       resolves to `None`, the correct, safe outcome (the caller drops that
       wire rather than routing to a nonexistent port).
    4. Exact-match removal is global per tag, not per role: if the same real
       port id is legitimately usable from both a "source" and a "target"
       query, the first query to claim it via exact match removes it from
       both pools.
    """
    ports_by_tag = _merge_ports_by_tag(elements)

    resolved: dict[Query, str | None] = {}
    resolution_kind: dict[Query, str] = {}
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
    # A label repeated across queries resolves to the port it got the first time.
    label_cache: dict[tuple[str, str], str | None] = {}
    for query in remaining:
        tag, label, role = query
        cache_key = (tag, label)
        if cache_key in label_cache:
            port_id = label_cache[cache_key]
        else:
            pool = down_pool.get(tag, []) if role == "source" else up_pool.get(tag, [])
            idx = seen_index.get((tag, role), 0)
            seen_index[(tag, role)] = idx + 1
            port_id = pool[idx].id if idx < len(pool) else None
            label_cache[cache_key] = port_id

        resolved[query] = port_id
        if port_id is not None:
            resolution_kind[query] = "heuristic"

    return resolved, resolution_kind
