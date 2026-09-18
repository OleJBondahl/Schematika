"""Rung-level netlist model for the round-2 pagination-partitioner deep dive.

Round 1 (`research/layout/pagination-partitioner/netlist.py`) modeled a
cross-rung dependency (`TagLink`) with a manually-chosen `owner_boundary`/
`user_boundary` flag deciding whether it was a "severed wire" (needs an
off-page `ref()` arrow) or a "tag echo" (needs nothing, `reuse_tags` already
handles it). Round 1's own Finding 1 and Finding 3 caught that this manual
flag was applied *inconsistently* on the exact same physical entity (the 24V
bus terminal `X4` got an arrow at one crossing and no arrow at two other,
structurally identical, crossings) -- because nothing forced the flag to
agree with what the rung's chain actually contains at that tag.

This version removes the manual flag entirely and derives the classification
from `ComponentSpec.kind`, which is a fact about the rung's chain, not an
opinion:

- `kind="terminal"`: a physical terminal block. Two rungs sharing a terminal
  id are the *same physical terminal drawn twice* -- self-documenting by
  real drafting convention, at any fan-out (2 pages or 20). Never an arrow.
- `kind="symbol"`: a component tag (e.g. a contactor's coil vs. its main
  contacts). Reused across rungs, this is a tag echo -- `reuse_tags` already
  resolves it, page-agnostically, at any fan-out. Never an arrow.
- `kind="stub"`: an explicit declaration that *this end of this rung's chain
  has no physical terminal and no component* -- the wire genuinely leaves
  the page bare. This is the only case that needs `ref()`. Because it is a
  distinct chain element (not a flag on a `TagLink`), its position (start vs.
  end of the tuple) is a structural fact, not something a caller has to get
  right by hand.

See `partitioner.py::classify_link` for the derivation and
`docs/research/layout-improvement/deepdive-pagination-partitioner.md` for the
worked before/after proof.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ComponentKind = Literal["terminal", "symbol", "stub"]


@dataclass(frozen=True)
class ComponentSpec:
    """One link in a rung's chain: a physical terminal, a symbol, or a stub.

    A "stub" carries no ports of its own in the source netlist -- it is a
    placeholder meaning "this chain end is genuinely severed here"; the
    render bridge replaces it with a real `ref()` off-page-connector symbol.
    """

    kind: ComponentKind
    id_or_prefix: str  # terminal id, symbol tag_prefix, or stub tag (net name)
    poles: int = 1
    symbol_fn: Callable | None = None  # only for kind="symbol"


@dataclass(frozen=True)
class RungSpec:
    """One vertical chain -- the atomic unit both Schematika and this
    partitioner build and page.

    `pin_to_function` is the manual override hook for the "ambiguous role"
    problem (round 1 Finding 2): when set, the partitioner buckets this rung
    as if it belonged to the named function group instead of its own
    `role`/`function`, while `role`/`function` are kept unchanged for
    display/build purposes. `None` (the default) means "use the automatic
    rules" -- this is purely additive, no existing behaviour changes unless
    a caller opts a specific rung in.
    """

    key: str
    role: Literal["power", "control", "terminal"]
    function: str  # grouping tag within a role, e.g. "conveyor_1", "estop_a"
    title: str
    components: tuple[ComponentSpec, ...]
    pin_to_function: str | None = None


@dataclass(frozen=True)
class TagLink:
    """Declares that `tag` is first defined on `owner_rung` and reused on
    `user_rung`. No boundary flag -- see module docstring. The electrical
    meaning (terminal crossing / tag echo / severed signal) is derived from
    `ComponentSpec.kind` by `partitioner.classify_link`, not declared here.
    """

    tag: str
    owner_rung: str
    user_rung: str


@dataclass(frozen=True)
class SystemNetlist:
    """The full synthetic cabinet system: every rung plus their cross-links."""

    rungs: tuple[RungSpec, ...]
    tag_links: tuple[TagLink, ...]

    def rung(self, key: str) -> RungSpec:
        for r in self.rungs:
            if r.key == key:
                return r
        msg = f"no rung with key {key!r}"
        raise KeyError(msg)
