# Round 2 deep dive: grid-astar-router

Round 1 built a working `CabinetGridAllocator` + `OrthogonalRouter` and rendered
a hand-authored 14-symbol ladder, then flagged two real gaps: (a) no bridge
from real `CircuitBuilder`/`BuildResult` data to "(port, port) pairs +
obstacles," and (b) a `_compress_to_turns` bug, already fixed by round 1
before this round started. This round builds the bridge for real, tests it on
a 98–152-component synthetic cabinet built entirely from real symbol
factories, found a **new** orthogonality bug the old bug's fix didn't cover,
measured performance at four scales, and ran the sibling
`svg-geometry-linter` track's linter against the output for an objective
defect count instead of a visual impression.

**Verdict: pursue, with a narrower and more specific scope than round 1
thought.** The router itself works and is now demonstrably correct on
1400+ routed segments across four scales (zero diagonal wires, zero
unresolved connections, zero routing failures). The real, unresolved problem
is not the A* search — it's (1) a scaling cost that is quadratic-ish in
practice because the search space isn't bounded per-route, and (2) label
placement, which was never in scope and remains the single largest
objective-defect category (label/wire collisions, ~0.5–0.7 per routed pair
at scale). Both are fixable with concrete, scoped follow-up work described
below — neither is a reason to stop.

## What was built

All under `research/layout/deepdive-grid-astar-router/` (throwaway, not
`src/schematika/`):

- **`pin_resolver.py`** — the `(tag, pin) -> Port` resolver round 1 called
  "the harder half of the work." Two-phase, not the naive one-pass heuristic
  elk-bridge sketched: exact matches (a label that is literally a real port
  id — true for `coil`'s `A1`/`A2`, `fuse`'s `1`/`2`) are claimed first and
  removed from the position pool; only the leftover labels fall back to
  position-order assignment. See "Bugs found" below for why the one-pass
  version was insufficient.
- **`topology_bridge.py`** — `derive_routing_input(result, extra_connections=)`
  turns a real `BuildResult` into `RoutingInput(symbols, pairs, unresolved)`.
  Accepts cross-branch connection tuples in the exact same 4-tuple shape as
  `wire_connections`, because — this is the round's central finding —
  `CircuitBuilder`'s relative-placement API cannot express more than one
  active vertical chain, so any real cabinet's cross-functional-group wiring
  (a shared e-stop chain, a supply feed into a separately-built branch) has
  to arrive this way regardless of which layout engine consumes it.
- **`router_core.py`** — hardened `OrthogonalRouter`: `route_with_fallback`
  (never raises; falls back to a naive 1-turn jog with a warning) plus
  `route_pure`, a stateless sibling that threads `used_cells` explicitly
  instead of mutating `self`. Fixes a **new** diagonal-wire bug (below).
- **`route_all.py`** — the real per-page routing loop, and the reason this
  round recommends the functional form over the stateful class for
  integration (see "Mutable state" below).
- **`large_cabinet.py`** — a `6*n_branches + 2`-component synthetic cabinet
  (main power row + e-stop + neutral bus, `n_branches` independent
  contactor/motor branches, `3*n_branches` terminals), built entirely through
  `CircuitBuilder.add_symbol`/`add_terminal` and real
  `electrical.symbols` factories (`estop`, `fuse`, `contactor`, `motor`,
  `terminal`) — nothing hand-placed with `Point()`.
- **`quality_report.py`** — runs the sibling `svg-geometry-linter` track's
  `lint_elements` (0 false positives on real circuits in round 1) against
  this track's own output.
- **`scale_benchmark.py`** — wall-clock sweep at 14/50/98/152 components.
- **`test_router_core.py`** — 5 synthetic regression checks (off-grid
  endpoints, same-cell diagonal endpoints, fallback path, `RoutingError`
  without fallback, pure/stateful equivalence).

Run order: `build_demo.py [n_branches]` (default 16 → 98 components) builds,
bridges, routes, renders to `output/large_cabinet_Nbranches.svg`, and prints
stats; `scale_benchmark.py` and `quality_report.py [n_branches]` are
standalone.

## The bridge: built and tested on real BuildResult data

`build_large_cabinet(n)` produces one merged `BuildResult` (main row +
per-branch builders + terminal strip, combined via `CircuitBuilder.merge`)
plus a short list of cross-branch tuples. `derive_routing_input` turns that
into routable pairs. At every tested scale (`n_branches` = 2, 8, 16, 25 →
14, 50, 98, 152 components):

```
n_branches  components  pairs  unresolved  routing fallbacks  diagonal wires
2           14          12     0           0                  0
8           50          48     0           0                  0
16          98          96     0           0                  0
25          152         150    0           0                  0
```

Every connection resolved, every route found a path, every wire is
orthogonal. This is not "it ran" — it's backed by the geometry linter (below)
and by `test_router_core.py`'s synthetic checks.

### Bugs found while building this (new, beyond elk-bridge's two)

1. **The real diagonal-wire bug** (the one round 1's fix didn't cover).
   `_compress_to_turns` substitutes the raw, off-grid port position for the
   search's own grid-snapped path endpoint. `motor`'s port y-coordinates come
   from `-math.sqrt(radius**2 - x_pos**2)` and essentially never land on a
   5mm grid line. The segment connecting the last snapped grid point to the
   true port position can therefore be diagonal even though the cell path
   itself was perfectly orthogonal — round 1's hand-picked demo coordinates
   were grid-aligned by luck and never hit this. Caught by the geometry
   linter (40 `non_orthogonal_wire` errors on the 98-component cabinet, 0
   after the fix — see "Quality" below), not by inspection. Fixed by
   `_orthogonalize_ends` in `router_core.py`: insert a corner point wherever
   two consecutive polyline points aren't axis-aligned.

2. **`contactor`'s coil and contact ports collide in the naive position
   pool.** `contactor()` combines a coil (`A1`/`A2`) with 3 power contacts;
   with a lazy, single-pass, order-only heuristic (elk-bridge's original
   design), the down-facing pool for a contactor is `[A2, T1-real, T2-real,
   T3-real]` sorted by x — because the coil sits to the left of the contact
   block — so the *first* "source"-role query for that tag (physically a
   power contact, `T1`) gets wrongly assigned to the coil's return terminal
   instead. Not a "plausible guess that might be wrong" — a specific,
   reproducible, physically incorrect assignment. Fixed two ways: (a) the
   resolver now does exact-match-first (any label that's literally a real
   port id is claimed immediately and removed from the pool, which is why
   `coil_pins=("A1","A2")` is passed explicitly in `large_cabinet.py`), and
   (b) the test circuit wires every `K.A2` to a real neutral terminal, which
   is both electrically correct (the coil return needs *somewhere* to go)
   and removes `A2` from the pool via an exact match before any heuristic
   assignment runs. Documented as `pin_resolver.py`'s limitation #4 (exact
   match is per-tag, not per-role) rather than hidden.

3. **`draw_wire` (`electrical/layout/layout.py:37`) never uses the semantic
   pin label at all.** It matches a downward port on the upper symbol to an
   upward port on the lower symbol by **x-alignment**
   (`get_connection_ports`), not by name. This means the pin strings
   `BuildResult.wire_connections` logs are purely informational bookkeeping
   that CircuitBuilder's own wiring never actually validates against real
   geometry — they were never guaranteed to be resolvable in the first
   place. See "Next steps" for what this implies for a real fix.

4. **`BuildResult.component_map`/`component_tags()` silently drops earlier
   tags when a spec places more than one component under the same prefix in
   a single `build()` call.** `captured_tags` in `builder.py` assumes one
   tag per prefix per circuit instance (true for a repeated single-instance
   spec via `count=`, false for `large_cabinet.py`'s main row, which places
   N fuses under prefix `"F"` in one `build()`). `component_tags("F")`
   returned `["F16"]`, not all 16 tags, even though every fuse *is* correctly
   placed and labeled in `circuit.elements`. Worked around by reconstructing
   tags directly (autonumbering on a fresh `state` is deterministic); not
   fixed, since it's outside this track's scope, but real and worth a
   one-line fix upstream (`builder.py`'s `_single_instance_gen`, append
   every tag instead of overwriting).

5. **`fuse`'s default `pins=("", "")`** means an unconfigured fuse's
   `wire_connections` entries log an empty-string pin id. Harmless for this
   resolver (it never reads the label's content, only its position in
   first-seen order), but a footgun for anything that does.

Bugs 1 and 2 are fixed in this round's code. Bugs 3–5 are documented,
workaround-only, and flagged for whoever picks this up next (3 in particular
changes the recommended fix — see "Next steps").

## Large-cabinet test results

`build_demo.py 16` (98 components: 1 e-stop, 16 fuses, 1 neutral terminal, 16
contactors, 16 motors, 48 terminals):

```
components placed: 98
route pairs derived: 96
unresolved connections: 0
heuristic-dependent pairs: 67%    (both endpoints exact-matched for the rest)
routing fallbacks (no A* path found): 0
total wire segments drawn: 285
grid cells consumed across all routes: 7018
```

Visual spot-check (`output/large_cabinet_2branches.png`, rendered via
Playwright at the SVG's real viewBox size — `scripts/pid_review.py`'s
Playwright fallback hardcodes an A3-landscape viewport and silently crops
anything larger, a known pre-existing bug from round 1's cross-cutting list,
confirmed again here, not re-fixed): the 2-branch case renders as a
recognizable, correctly-topologized DOL-starter-style ladder — S0's
common-stop contact visibly fans out to both K1.A1 and K2.A1 with the two
routes cleanly separated (the crossing-penalty mechanic round 1 first
demonstrated, still working at this scale), F1/F2 feed the contactors'
line-side poles, and each contactor's three load-side poles (T1/T2/T3) route
down to the matching motor pole in three parallel, non-overlapping wires.

## Quality: objective defect count, not a visual impression

`quality_report.py` runs `svg-geometry-linter`'s `lint_elements` against the
full rendered element list (symbols + hand-drawn busbar + every routed wire).

**Before the `_orthogonalize_ends` fix** (98 components, 245 wire segments):

| kind | count |
|---|---|
| `non_orthogonal_wire` (error) | 40 |
| `text_wire_collision` (error) | 44 |
| `redundant_jog_candidate` (info) | 37 |
| **total** | **121** |

**After the fix** (98 components, 285 wire segments — more segments because
each orthogonalized corner adds one):

| kind | count |
|---|---|
| `text_wire_collision` (error) | 68 |
| `redundant_jog_candidate` (info) | 37 |
| **total** | **105** |

`non_orthogonal_wire` is fully eliminated (0/0/0/0 across all four tested
scales — see `test_router_core.py`). The two remaining categories:

- **`text_wire_collision` (real, pre-existing scope gap, now quantified):**
  round 1 already named this as out of scope ("the router has no knowledge
  of label placement... that's `svg-geometry-linter` territory"). At scale
  it's not a rounding error: 33 collisions at 50 components, 68 at 98 —
  roughly linear in branch count, ~0.24–0.27 per wire segment. This is the
  single largest reason not to call this "ship-ready" without pairing it
  with a label-aware pass (either the router avoiding label bboxes as
  obstacles, or a post-pass that nudges labels).
- **`redundant_jog_candidate` (mostly a linter limitation, not a router
  defect):** the linter's own docstring flags its chain-grouping as a known
  false-positive source ("two unrelated wires that happen to touch end-to-end
  will be chained together"). Manually inspecting the largest reported chain
  (20 segments spanning the full row width) confirms this: it's several
  independent F→K supply wires that the router's crossing-penalty
  deliberately routed through a shared horizontal corridor (cheaper to reuse
  a used cell than to jog around), which the linter's endpoint-touching
  heuristic merges into one apparent 12-turn "chain." Worth a human look in
  a real cabinet (a shared corridor of unrelated wires is a legitimate
  readability concern even if not literally "redundant jogs"), but not a
  count to trust literally without visual confirmation.

## Performance: measured, not assumed, and worse than round 1's demo suggested

```
n_branches  components  pairs  build_ms  bridge_ms  route_ms   total_ms   ms/pair
2           14          12       3.1       0.13        87.7       91.0      7.31
8           50          48       9.4       0.38      1262.2     1272.0     26.30
16          98          96      17.1       0.73      5213.0     5230.9     54.30
25          152         150     26.3       1.16     15589.9    15617.3    103.93
```

`build` (CircuitBuilder) and `bridge` (`derive_routing_input`) are
negligible and scale linearly, as expected. **`route` is the entire cost, and
`ms/pair` roughly doubles every time `n_branches` doubles** — i.e. total
routing time is closer to quadratic in component count than linear. At 152
components (an ambitious but plausible single-page cabinet) routing alone
takes 15.6 seconds; a real multi-hundred-component, multi-page cabinet could
plausibly reach the low minutes purely in routing, eating into (not yet
exceeding) the project's stated "runtime speed is not a constraint, but
minutes not seconds" tolerance.

**Root cause, isolated by profiling `n_branches=16`:** rasterizing the
per-route obstacle set is cheap (96ms of 5.2s total, ~2%). The A* search
itself is the cost, and the reason is that **every route's search bounds are
the whole page**, not a region around that route's own endpoints. At 16
branches the page is 1728mm × 367mm = ~346×74 grid cells; a short, local
F→K wire and a long S0-to-K16 fan-out wire both search over the same
~25,000-cell space with `(cell, direction)` states (4× that), because
`all_symbols_bounds` is computed once for the whole cabinet and handed to
every route unchanged.

**Recommended fix (not implemented — out of scope for "runtime speed is not
a constraint," but the concrete next step if 152+ components becomes
routine):** bound each route's search to a padded bbox around its own
`(start, end)` pair instead of the full page bounds. This should turn the
per-route cost from "proportional to total page area" into "proportional to
that route's own span," which is what actually varies per route already
(the S0 fan-out is inherently more expensive than a local F→K feed — that's
fine — but every route currently pays the *whole page's* worst case
regardless).

## Mutable state: recommend the functional form, reversing round 1's lean

Round 1 tentatively suggested `OrthogonalRouter` might need to become an 8th
documented mutable place (`docs/ARCHITECTURE.md`'s list), matching
`CircuitBuilder`'s lifecycle. Building the real bridge changed that
recommendation:

**A stateful router's obstacle set is fixed at construction. A real
multi-route pipeline needs a *different* obstacle set per route** — every
route must exclude its own two endpoint symbols (`topology_bridge.
obstacles_excluding`), and which two symbols that is changes every call.
`OrthogonalRouter` as a class can't express this without being reconstructed
per route, at which point its constructor-time obstacle-baking is pure
overhead and its `_used_cells` accumulation (the actual point of keeping
state) has to be re-plumbed in by hand anyway — which is exactly what
`route_pure`'s explicit `used_cells` argument already does, with less
ceremony:

```python
used_cells: frozenset = frozenset()
for pair in routing_input.pairs:
    blocked = rasterize_obstacles(obstacles_excluding(symbols, {pair.from_tag, pair.to_tag}), cfg)
    polyline, used_cells = route_pure(pair.from_point, pair.to_point,
                                       blocked=blocked, used_cells=used_cells,
                                       bounds=bounds, config=cfg)
```

This is what `route_all.py` actually uses for the whole large-cabinet
pipeline — not a toy comparison, the real path. `OrthogonalRouter` is kept
(as a thin wrapper calling `route_pure` internally, so the two are equivalent
*by construction*) for the one case it still fits: a single, page-wide,
never-changing obstacle set — `test_router_core.py::
test_pure_and_stateful_agree_on_a_fixed_obstacle_set` proves the two produce
byte-identical polylines there.

**Recommendation: no 8th mutable place.** A real `electrical.layout.router`
module should expose `route_pure`-shaped free functions (state threaded
explicitly through arguments and return values), matching the repo's stated
preference for frozen dataclasses and functional cores, with `OrthogonalRouter`
kept only as an ergonomic wrapper for the narrow fixed-obstacle-set case, not
promoted to a page-scoped builder analogous to `CircuitBuilder`.

## Integration awareness: pagination-partitioner

`derive_routing_input`'s input shape (a `BuildResult` plus a plain list of
4-tuple cross-branch connections) is something a per-page split could
plausibly produce: a page's own `BuildResult` for its own symbols, plus a
list of connections whose other endpoint lives on a different page. One real
mismatch found while building this: `RoutingInput.unresolved` today conflates
three different reasons a connection didn't resolve — a missing symbol tag
(expected and fine for a cross-page reference), an exhausted pin pool (a real
resolver limitation, bug 2 above), and a tag simply absent from the page
being built. A real integration with `pagination-partitioner` needs these
distinguished (`unresolved` should probably become three separate lists, or
carry a reason code) so "this connection goes to another page, route it to
an off-page marker" and "this connection is a resolver bug, drop it and log
loudly" aren't handled the same way. Not built here — noted per the task's
"don't build the integration, just flag mismatches" instruction.

## Fit with invariants (unchanged from round 1, reconfirmed)

- `core/`-only imports from `router_core.py`/`pin_resolver.py`; `electrical`
  imports (`electrical.symbols`, `CircuitBuilder`) only in `large_cabinet.py`
  and `topology_bridge.py`, consistent with where a real
  `electrical.layout.router` addition would sit (layer 2, same as
  `CircuitBuilder` itself).
- Frozen dataclasses throughout the new code (`RouterConfig`, `RoutingInput`,
  `RoutePair`, `LargeCabinet`, `RouteAllResult`); the one class
  (`OrthogonalRouter`) is now an optional convenience wrapper, not the
  primary API — see "Mutable state" above.
- No new `ValueError`s; `RoutingError` stays a dedicated exception, matching
  the repo's per-domain exception-base convention (it isn't itself a domain
  base since this code doesn't live in `src/schematika/electrical`).

## Next steps for a real `electrical.layout` module

What would need to move into `src/schematika/`, and what the public API
should look like per `API_STYLE.md`:

1. **Fix `wire_connections` at the source, not downstream.** Bug 3 above
   (`draw_wire` matches by x-alignment, never by label) means the real fix
   isn't "a better resolver" — it's making `CircuitBuilder` log the actual
   resolved port id it already computes internally (via
   `get_connection_ports`) instead of the pre-resolution semantic label. This
   makes every wire `CircuitBuilder` draws itself trivially resolvable with a
   dict lookup, and shrinks `pin_resolver.py`'s job to only the connections
   that never went through `CircuitBuilder`'s own wiring (cross-branch /
   `Harness`-level topology) — which is also the only place x-alignment
   doesn't help (the two symbols aren't in the same column), so the
   position-heuristic resolver built this round is still needed there, just
   for a smaller, better-understood slice of the problem.
2. **Bound each route's search to its own span**, not the whole page (see
   "Performance" above) before this sees any circuit larger than ~150
   components in practice.
3. **New module `electrical/layout/router.py`**: `RouterConfig`,
   `RoutingError`, and free functions in `route_pure`'s shape (state threaded
   explicitly, no builder). Public entry point matching `API_STYLE.md`'s
   free-function convention (this isn't a builder — it derives a result from
   an existing `BuildResult`, so it doesn't get a `*BuildResult` name; a
   `LayoutResult` frozen dataclass — `wires: list[Line]`, `unresolved: list[...]`,
   `fallback_pairs: list[tuple[str, str]]` — matches round 1's suggestion and
   this round's `RouteAllResult`):
   ```python
   def route_wires(
       result: BuildResult,
       /,
       *,
       extra_connections: Sequence[WireConnection] = (),
       config: RouterConfig | None = None,
   ) -> LayoutResult: ...
   ```
4. **Promote `pin_resolver.py`** to `electrical/layout/pin_resolver.py` (or
   fold into the same module) once (1) narrows its job — document its
   remaining limits (position-order-only fallback, per-tag not per-role
   exact-match cache) in the factory-docstring style `CLAUDE.md` already
   requires for port IDs.
5. **Do not build a grid/placement allocator alongside this.**
   `CircuitBuilder` already places every symbol in this round's 152-component
   test; `CabinetGridAllocator` (round 1) was never exercised here because
   there was nothing left for it to do once real placement was in play. If
   it ships at all, it should be scoped to cases that bypass `CircuitBuilder`
   entirely, not as a default companion to the router.
6. **Pair with `svg-geometry-linter` before shipping** — unchanged from round
   1's caveat, now with real numbers: 68 label/wire collisions on a
   98-component cabinet is not a rounding error.
