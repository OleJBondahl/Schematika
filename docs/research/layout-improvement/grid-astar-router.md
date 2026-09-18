# Track: grid-astar-router

Question: can a pure-Python deterministic zone/grid placement engine plus an
orthogonal A* wire router, grounded in Schematika's real symbol/port/geometry
model, produce visibly better cabinet-ladder layouts than today's manual
`position: Point` placement?

## What was built

`research/layout/grid-astar-router/` (runnable prototype, no changes to
`src/schematika/`):

- `cabinet_grid.py` — `CabinetGridAllocator`: fixed Y-zones
  (`power_rail_top` / `protection` / `control` / `coils` / `power_rail_bottom`
  / `terminals`) reusing the existing `SPACING_STANDARD` (60mm) constant for
  zone pitch and `CIRCUIT_SPACING` (100mm) for column (rung) pitch, instead of
  inventing new numbers. `slot(column, zone) -> GridSlot(Point)` and
  `rail_span(zone, first_col, last_col)` for bus lines.
- `astar_router.py` — `OrthogonalRouter`: A* on an implicit grid
  (`cell_size=5mm`, matching `core.constants.GRID_SIZE`), state = `(cell,
  incoming_direction)`, cost = 1 + `turn_penalty` (15) on direction change +
  `crossing_penalty` (5) for cells a prior route already used. Obstacles are
  `BoundingBox`es (from `schematika.core.bbox.compute_bounding_box`) of every
  *other* placed symbol, inflated by a clearance. Output is compressed to a
  turn-point polyline, then `polyline_to_wires()` turns it into a
  `list[Line]` — the exact type `electrical.layout.layout.draw_wire` already
  returns, so it drops into the existing renderer with zero adapter code.
- `synthetic_circuit.py` — a 5-column, 14-symbol synthetic cabinet ladder
  built entirely from real factories (`breaker`, `fuse`, `estop`, `coil`,
  `no_contact`, `nc_contact`, `terminal`): a start rung (F1→S0→K1), a seal-in
  feed rung (F2→K1 aux NO contact), a spare/obstacle rung (F3→S2), and two
  remotely-interlocked coils (Q1, Q2) in separate columns. K1's auxiliary
  contact fans out to both Q1 and Q2 — both wires must cross the F3/S2
  column, and both start from the same pin, which exercises the router's
  obstacle avoidance *and* its crossing-penalty in the same run.
- `build_demo.py` — runs the above, renders through the real
  `schematika.rendering.svg.render_to_svg`, prints stats. Output:
  `research/layout/grid-astar-router/output/cabinet_ladder.svg` (37 elements,
  14 symbols, auto-sized viewBox).

## How it performed

```
Placed 14 symbols
Total drawable elements: 37
A* route K1_aux -> Q1: 3 points -> (100,125) (100,175) (300,175)
A* route K1_aux -> Q2: 4 points -> (100,125) (100,105) (400,105) (400,175)
A* grid cells consumed by both routed wires: 129
Build + route time: 33 ms
```

Both routes are correctly orthogonal (verified programmatically: no wire
segment's bounding rectangle overlaps any non-endpoint symbol's inflated
bbox) and both routes are meaningfully *not* the naive path:

- Route 1 (K1_aux → Q1) cannot go straight across at y=125 (the height it
  starts at) because S2's NC-contact bbox (y 115–125, x 195–203) sits
  directly in that row. The router drops to y=175 (Q1's own row) before
  crossing — one turn, obstacle cleared.
- Route 2 (K1_aux → Q2) starts from the identical pin and would want the
  same cheap y=175 corridor route 1 just claimed. The crossing penalty makes
  that costlier than detouring via y=105 instead, so the two wires visibly
  separate rather than overlapping for 200mm — this is the actual mechanic
  the Gemini sketch's "wire crossing / overlap penalty" was meant to produce,
  and it produced it on the first real multi-route test.

One real bug was caught during this spike: the initial `_compress_to_turns`
logged the turn vertex one grid cell late, which silently produced a
*diagonal* segment between two "turn points" — i.e. a wire that isn't
actually orthogonal, just looks like it in the coordinate list. This is
exactly the kind of defect `svg-geometry-linter` (the sibling track) is
meant to catch mechanically; here it was caught by re-deriving the geometry
by hand and checking segment axis-alignment, which is not something a
casual visual read of the rendered SVG would necessarily have caught either.

## Integration effort to become `electrical.layout`

Moderate, not large:

- `CabinetGridAllocator` as-is is close to shippable: it is a thin,
  side-effect-free wrapper around existing constants (`SPACING_STANDARD`,
  `CIRCUIT_SPACING`) plus `Point`. It would need to become a real frozen
  config object per API_STYLE (currently `GridZones` already is; the
  allocator itself is a small mutable-free helper, not a builder, so it
  doesn't need `add_*`/`build()` — closer to a pure function module).
- `OrthogonalRouter` needs more work before it's production code: (a) a
  proper obstacle-source (today the caller manually excludes the two
  endpoint symbols; a real integration needs a "does this bbox belong to a
  port I'm connecting" check, since two adjacent rungs will legitimately
  need to route wires that touch their own symbols' edges); (b) a decision
  on what happens when `route()` raises `RoutingError` (currently the A*
  simply fails outward — a real caller needs a fallback, e.g. relaxing
  clearance or falling back to `draw_wire`'s straight line with a logged
  warning, not a hard crash mid-`build()`); (c) performance is fine at this
  scale (33ms for 14 symbols + 2 routes) but was never tested at
  full-cabinet scale (60-100 symbols, dozens of routes) — cost is
  `O(routes × grid_cells)` and grid cell count scales with page area, not
  symbol count, so a large low-density page could get expensive. Given the
  README's explicit "runtime speed is not a constraint" this is likely fine
  but is untested here.
- The bigger gap is *upstream* of routing: this prototype's circuit topology
  (which symbol connects to which, which contact shares a tag with which
  coil) was hand-authored in Python, not derived from anything
  `CircuitBuilder`/`Harness` already produces. A real integration needs a
  bridge from `BuildResult`'s existing connection data (or a new
  `Harness`-level graph) to "here are the (symbol, port) pairs that need a
  wire, and here are all the obstacle bboxes" — that bridge doesn't exist
  yet and is arguably the harder half of the work, not the router itself.

## Fit with invariants

- **`core/` I/O-free**: respected. Neither `cabinet_grid.py` nor
  `astar_router.py` does I/O; only `build_demo.py` (the shell) calls
  `render_to_svg`.
- **Frozen dataclasses**: `GridZones` and `GridSlot` are frozen. `Symbol`
  placement uses the existing `translate()` free function (returns new
  frozen instances), never mutates. `OrthogonalRouter` itself is a stateful
  object (it accumulates `_used_cells` across `route()` calls by design —
  that's the whole point of the crossing penalty) — this is the same kind of
  exception the architecture doc already carves out for the seven allowed
  mutable builders (`CircuitBuilder`, `Harness`, etc.); a real
  `OrthogonalRouter` would need to be added to that list or made explicitly
  page-scoped/short-lived like `CircuitBuilder`.
- **No domain-package imports from `project.py`, no sideways imports**: the
  prototype only imports from `core` and `electrical` (one-directional,
  layer 2 importing layer 0), consistent with where a real `electrical.layout`
  addition would sit.
- **Return-type rule**: not directly applicable — this track produces
  `list[Element]`/`list[Line]`, matching what `draw_wire` (an existing,
  accepted free function in `electrical/layout/layout.py`) already returns,
  not a `*BuildResult`. A real integration would likely want a small
  `LayoutResult`-style frozen wrapper (placed symbols + wires) to match the
  domain convention, rather than a bare list.

## Pros / cons vs. today's manual placement

**Pros**

- Genuinely automated: zero manual `Point` arithmetic for either symbol
  placement or wire routing in the demo circuit.
- Grounded in real units and real constants — the output is dimensionally a
  normal Schematika page, not a rescaled abstract grid.
- The router's core value proposition (turn/crossing penalties producing
  legible, separated wires) is demonstrated, not just asserted — see the
  Q1/Q2 divergence above.
- Output is a real `Line`/`Symbol` element list, renders through the
  existing SVG pipeline unmodified.
- Deterministic and fast enough that "runtime speed is not a constraint" is
  moot at demo scale.

**Cons**

- Today's manual placement already handles the *common* case (a single
  vertical chain, `CircuitBuilder.add_terminal`/`add_symbol` with
  `draw_wire`) with less code and no grid/A* machinery at all — this engine
  only pays for itself on the *cross-column, cross-referenced* case (aux
  contacts, interlocks spanning rungs), which is common in real cabinets but
  is a minority of the wiring in any given diagram.
- The router has no knowledge of *label* placement, port-number text, or
  wire-label boxes — it can route a clean wire straight through where a
  label would visually collide. That's out of scope for this track
  (`svg-geometry-linter` territory) but is a real gap before this could ship.
- No pagination/cross-reference awareness (that's `pagination-partitioner`'s
  job) — a real cabinet spans pages, and this router has no concept of an
  off-page marker as a route endpoint.
- The "circuit topology → router input" bridge doesn't exist; this is the
  single largest remaining unknown for real integration effort.

## Verdict: pursue with caveats

The core idea holds up under an actual multi-route test on a realistic
(if small) cabinet ladder, not just a single toy wire — the crossing-penalty
mechanic visibly changed the second route's shape, and the grid allocator's
zone/column model maps cleanly onto Schematika's existing spacing constants.
This is worth carrying forward as the wire-routing half of a future
`electrical.layout` module, specifically for the cross-referenced-contact
case that today requires manual jogging.

Caveats that should gate "pursue" rather than "ship":

1. Build the topology→router bridge (from `Harness`/`BuildResult` connection
   data to (port, port, obstacle-set) triples) before investing further in
   the router itself — that bridge, not the A* search, is the load-bearing
   unknown.
2. Decide `OrthogonalRouter`'s mutability story against the
   architecture doc's "seven mutable places" list rather than adding an
   eighth ad hoc one.
3. Pair this with `svg-geometry-linter` before shipping — this router can
   produce a *geometrically* correct but *visually* colliding result (wire
   through a label) and has no way to know that on its own.
4. Don't build a second grid/placement engine for `pid`/`pcb` on top of this
   one without checking `pid-layout`/`pcb-layout`'s findings first — the
   Y-zone model here is specifically ladder-shaped (power rail → protection
   → control → coils → power rail → terminals) and does not obviously
   generalize to P&ID's free-form equipment placement.
