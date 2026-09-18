"""Abstract rung-level netlist model for the pagination-partitioner spike.

Schematika's actual unit of construction is a *rung*: one `CircuitBuilder`
chain of terminals/symbols wired top-to-bottom (see `docs/ARCHITECTURE.md`'s
`electrical` row and `examples/06_full_cabinet.py`). There is no finer-grained
"netlist" inside a rung to partition -- it is a single straight-through
connection. `partitioner.py` therefore operates at rung granularity: a page
is a set of whole rungs, never a rung split mid-chain.

Cross-rung dependencies come in two electrically distinct flavours, both
modelled by `TagLink`:

- A **severed wire** (`owner_boundary`/`user_boundary` set to "start"/"end"):
  a terminal or bus sits at the very edge of both rungs' chains and the wire
  genuinely has nowhere else to go on either page. Needs an off-page
  connector arrow when the two rungs land on different pages.
- A **tag echo** (`owner_boundary`/`user_boundary` left `None`): a component
  tag (e.g. a contactor's coil vs. its main contacts) is reused mid-chain on
  another rung. Both rungs are already fully self-terminated; Schematika's
  existing `reuse_tags` mechanism resolves this regardless of which page
  either rung ends up on. No arrow is ever needed -- see
  `pagination-partitioner.md` for why conflating the two would be wrong.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Boundary = Literal["start", "end"] | None


@dataclass(frozen=True)
class ComponentSpec:
    """One link in a rung's chain: either a physical terminal or a symbol."""

    kind: Literal["terminal", "symbol"]
    id_or_prefix: str  # terminal id (e.g. "X1") or symbol tag_prefix (e.g. "F")
    poles: int = 1
    symbol_fn: Callable | None = None  # None for "terminal"


@dataclass(frozen=True)
class RungSpec:
    """One vertical chain -- the atomic unit both Schematika and this
    partitioner build and page.
    """

    key: str
    role: Literal["power", "control", "terminal"]
    function: str  # grouping tag within a role, e.g. "conveyor_1", "estop"
    title: str
    components: tuple[ComponentSpec, ...]


@dataclass(frozen=True)
class TagLink:
    """Declares that `tag` is first defined on `owner_rung` and reused on
    `user_rung`. See module docstring for the start/end vs. None distinction.
    """

    tag: str
    owner_rung: str
    user_rung: str
    owner_boundary: Boundary = None
    user_boundary: Boundary = None


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
