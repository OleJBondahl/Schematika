# pid-layout: does P&ID need its own layout heuristic?

Track: `pid-layout`. Branch: `layout-improvment-pid-layout`. Prototype:
`research/layout/pid-layout/`.

## What today's manual model actually is

`PIDBuilder` (`src/schematika/pid/builder.py`) already separates concerns
cleanly:

- **Placement** (`src/schematika/pid/layout.py`) is a BFS over a
  port-to-port `Placement` graph (anchor + port pair + `Vector` offset), or
  a bare absolute `Point`. It is not "manual" in the sense of raw pixel
  pushing — it's anchor-relative, like the `electrical` module — but the
  *offset* (the pipe-run length between two anchored ports) is always a
  number the author picks by hand and iterates on via the render → inspect
  → adjust loop in `CLAUDE.md`.
- **Routing** (`src/schematika/pid/connections.py`) is already a generic
  two-segment Manhattan router (`manhattan_route`), with the bend axis
  chosen from the source port's direction. This is exactly the "layered
  graph, edges are pipes" building block the research question describes —
  it already exists and needs no reinvention.
- **Instrument stubs** are placed by a single fixed `(dx, dy)` offset from
  the parent port (`_DEFAULT_INSTRUMENT_OFFSET` in `builder.py`), independent
  of the equipment's actual shape or the port's direction.

So the real question isn't "orthogonal routing vs. P&ID routing" (routing is
already generic and shared-code-ready) — it's specifically **equipment
placement**: can a layered-graph node-positioning pass replace the
hand-picked offsets, and does the rest of the pipeline (routing, stubs,
validation) hold up once positions come from an algorithm instead of a human.

## Prototype

`research/layout/pid-layout/`:

- `scenario.py` — one synthetic process shared by both layouts: `tank1 →
  pump → control_valve → tank2`, a `bypass_valve` parallel branch around
  the control valve, a `tank2 → tank1` recycle line (forces a back-edge /
  routing decision), and three ISA instruments (PT on the pump outlet, FT
  on the control valve outlet, LT on tank2).
- `manual_layout.py` — today's real workflow: `EquipmentPlacement` with
  hand-picked offsets for the main chain and an eyeballed absolute point for
  the off-line bypass valve, iterated once against `validate_pid` (the
  tank2 offset started at 50mm, ran 3mm past the page margin, got knocked
  down to 40mm — that's the actual loop, not a dramatization).
- `layered_layout.py` — a from-scratch longest-path (Sugiyama-style)
  layering: process pipes are edges, flow direction is the layering axis,
  column spacing comes from real symbol bounding boxes
  (`schematika.core.renderer.calculate_bounds`) plus `PID_MIN_EQUIPMENT_GAP`
  instead of a guessed number. A `lane` hint on a `PipeDef` moves
  branch-only nodes to a parallel row; edges can be marked `back_edge` to
  exclude them from layering (the recycle line).
- `auto_layout.py` — same scenario, zero hand-picked coordinates; every
  position comes from `compute_positions`. Pipe/instrument declarations are
  the identical calls used by `manual_layout.py` (`scenario.apply_pipes` /
  `apply_instruments`), so the only variable under test is placement.
- `routing_check.py` — mechanised check (not eyeballing): recomputes the
  recycle pipe's actual waypoints and tests each segment against every
  other equipment's bounding box.
- `out/manual.svg` / `out/auto.svg` (+ rendered `.png` via
  `scripts/pid_review.py`, cairosvg backend) — generated, not committed
  (repo-wide `.gitignore` excludes `*.svg`/`*.png`); regenerate with the
  commands below.

Run: `uv sync --extra dev` (for the PNG conversion), then from
`research/layout/pid-layout/`: `uv run python manual_layout.py`,
`uv run python auto_layout.py`, `uv run python routing_check.py`.

## Results

`validate_pid()` on both (mechanised, not visual):

| | manual | auto |
|---|---|---|
| Equipment overlap | `P1`/`PT1`, `CV1`/`FT1` (instrument-stub default offset overlaps the round pump/valve body — pre-existing, both layouts, not a placement-method issue) | same two |
| Page-boundary violation | 0 (after 1 manual correction) | 0 (correct on the first try — spacing came from measured bounds, not a guess) |
| Duplicate-line warning | none | `Duplicate line at (120.0, 90.0) to (150.0, 90.0)` |

`routing_check.py` (recycle line `tank2.drain → tank1.vent`, recomputed
waypoints vs. every other equipment's bounding box):

```
[manual] recycle line crosses: ['GV1', 'LT1']
[auto]   recycle line crosses: ['PT1', 'FT1']
```

Visual (`out/manual.png`, `out/auto.png`, read back and inspected):

- **Column/x placement**: auto-layout's flow-ordering is correct and needed
  zero manual tuning — equipment lands left-to-right in process order with
  clean, standards-compliant spacing on the first run. This is the biggest
  practical win: the trial-and-error loop in `manual_layout.py` (guess an
  offset, render, see it clip the page margin, adjust) is exactly what a
  layered-graph pass eliminates.
- **Branch/lane placement**: an early version of `compute_positions` had a
  real bug — it moved *every* node touched by a branch edge onto the branch
  lane, which pulled the pump and tank2 (both still on the main line) off
  axis and rendered the bypass valve and control valve as one merged,
  overlapping box. Fixed version (only nodes exclusive to the branch move
  lanes) renders correctly. The fix itself is the finding: a generic
  "longest-path + edge-lane" layering has no notion of "main line vs.
  branch" — that had to be supplied as domain input (the `lane` field), it
  wasn't inferable from graph topology alone (a bypass and a second parallel
  process train are topologically identical; only the diagram's *intent*
  distinguishes them).
- **Asymmetric port geometry**: `tank`'s ports are not centered on its
  bounding box (`inlet` top-left, `outlet` bottom-right per
  `src/schematika/pid/symbols/vessels.py:112-121`) the way `pump`'s and
  `control_valve`'s are (both ports on the horizontal centerline). A layout
  that aligns node *centers* to a column x produces a visible dogleg jog on
  `tank1 → pump` in the auto render that the manual version — placed
  port-to-port via the existing `Placement` BFS — doesn't have. A
  general-purpose layered-graph engine that only knows bounding boxes will
  get this wrong; it needs each symbol factory to expose which port is the
  "primary flow axis" so the engine aligns by port, not by box center.
  `electrical`'s ladder symbols mostly don't have this problem (pins sit on
  a shared grid line); P&ID equipment (tanks, in particular) does.
- **No pipe-tee/junction primitive**: `pipe_tee` exists in
  `src/schematika/pid/symbols/piping.py` but `PIDBuilder.pipe()` has no
  concept of an n-ary junction — it only draws point-to-point edges. When
  the layered-graph engine aligns the bypass and main-line columns (which
  it does, correctly, because it optimizes for column consistency), both
  incoming pipes to `tank2.inlet` become exactly coincident for their last
  segment, and `validate_pid`'s duplicate-line check catches it. The manual
  layout avoided this by accident (the hand-picked bypass position wasn't
  perfectly aligned), not by design. This is a piping-domain gap a node/edge
  graph model doesn't represent at all, regardless of which layout algorithm
  drives it.
- **Routing has no obstacle avoidance in either case**: `manhattan_route`
  is direction-aware but not obstacle-aware. The recycle line crosses two
  unrelated instruments in *both* layouts. This isn't a placement-algorithm
  problem — it's a pre-existing routing gap, equally present whether
  positions come from a human or an algorithm.

## Does P&ID need its own layout heuristic?

**No, not for the placement axis.** A generic layered-graph engine (the
same longest-path/Sugiyama primitive under consideration for `electrical` in
`pure-python-graph-layout`) handles P&ID's left-to-right process-flow
convention correctly and removes essentially all of the manual pipe-length
guessing that dominates today's workflow. Column spacing from real symbol
bounds (not hand-picked offsets) worked with zero tuning.

**Yes, for several P&ID-specific extensions layered on top of it**, none of
which a generic graph engine provides for free:

1. Branch/lane assignment needs an explicit domain hint (which nodes are
   "on the bypass"), not just edge topology.
2. Column alignment needs to key off each symbol's declared flow-axis port,
   not its bounding-box center, or asymmetric-port equipment (tanks) gets
   visible jogs.
3. A pipe-tee/junction primitive is needed wherever two flow edges
   legitimately converge — the node/edge graph model has no such concept,
   and a layered layout's tendency to align columns makes the resulting
   duplicate-line artifact *more* likely to appear, not less.
4. Obstacle-aware (or at least back-edge-lane-routed) pipe routing for
   recycle/return lines — orthogonal to placement, but needed before any
   layout (manual or auto) produces a clean diagram.

## Verdict: pursue with caveats

Build the equipment-placement pass as a thin, additive layer using the same
generic layered-graph primitive as `electrical`/`pure-python-graph-layout`
(shared code, shared review effort), feeding `PIDBuilder.add_equipment(...,
placement=EquipmentPlacement(position=...))` with absolute points — no
`PIDBuilder` API change needed, this prototype never touched it. Do **not**
expect it to be a drop-in "layout wins for free" story: items 1-3 above are
P&ID-domain work (lane hints, flow-axis port declarations per symbol
factory, a junction primitive) that has to be designed and built regardless
of which generic engine supplies the column axis, and item 4 (routing) is a
separate, currently-unsolved problem shared by both approaches.

Fit with invariants: clean fit. `compute_positions` is a pure function
(nodes, edges, symbols) → positions, no I/O, no state; it would live at the
same layer as today's `pid/layout.py`, doesn't need a new runtime
dependency, and stays fully additive (existing hand-placed diagrams are
unaffected — `EquipmentPlacement` already accepts either path).

## Files

- `research/layout/pid-layout/scenario.py` — shared synthetic topology
- `research/layout/pid-layout/layered_layout.py` — longest-path layering +
  bounds-driven column spacing
- `research/layout/pid-layout/manual_layout.py` — hand-placed baseline
- `research/layout/pid-layout/auto_layout.py` — layered-graph auto-layout
- `research/layout/pid-layout/routing_check.py` — mechanised recycle-line
  obstacle-crossing check
- `research/layout/pid-layout/out/{manual,auto}.{svg,png}` — rendered
  output (gitignored, regenerate with `uv run python manual_layout.py` /
  `auto_layout.py` from `research/layout/pid-layout/`)
