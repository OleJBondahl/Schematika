# Layout Improvement Spike — Final Recommendation

Two rounds of research on branch `layout-improvment`: a 12-track broad survey (round 1), then
a much deeper investigation of the 3 strongest, highest-production-impact directions
(round 2). See `SYNTHESIS.md` for the full round-1 verdict table and `docs/research/layout-improvement/*.md`
for every track's individual writeup. This doc is the "what to actually do next" summary.

## Post-implementation status (all four pieces built, merged, demonstrated on a real cabinet)

Everything below this line was written *before* any production code existed. All four pieces
it recommends have since been implemented on this branch and demonstrated against the real
`auxillary_cabinet_v3` cabinet (see that repo's own `layout-improvment` branch: three demo/report
scripts + docs under `src/`). Status:

- **Pin-metadata bugs** (motor port count, `component_tags()`, `fuse` defaults): fixed, tested,
  merged (`d839d7c`+follow-ups). No issues found demonstrating against the real cabinet.
- **`core/geometry_lint.py`**: built, merged (`8919f89`). Run against all 12 real production
  circuits in `auxillary_cabinet_v3` — found a genuine, reproducible defect (4 non-orthogonal
  wires in `fan_controll`, traced to `circuits/fan_controll.py` combining `x_offset` with
  `position="below"`) and correctly flagged the text-collision check as noisy on real wire/PLC
  labels (194 of 198 findings) rather than a real defect category — that check needs narrowing
  before use as a hard gate.
- **Automatic pagination** (`electrical/pagination.py`): built, merged (`7bb82ff`). Demonstrated
  against a real-shaped 43-rung model of the cabinet: produced 14 pages vs. the real cabinet's
  10 hand-written ones, over-splitting 3 groups purely from the default 5-rung-per-page budget
  (fixable by raising it to 8). Grouping quality matched or exceeded the manual page layout.
- **`electrical.layout.router` (`route_wires`)**: built, merged (`0ee05a2`). **NOT ready for
  real integration** — demonstrating it against the real `fan_controll` circuit (the exact
  circuit the linter flagged) surfaced a new, more serious bug than the one it was meant to
  fix: `derive_routing_input` resolves wire endpoints by symbol *label* in a plain dict
  (last-write-wins). This codebase's real circuits routinely reuse the same tag across multiple
  sub-circuit instances (e.g. `K8`/`K9` each label 3 physical symbols; `count=2` fan circuits
  duplicate `PLC:DI`/`PLC:DO`/etc.) — a normal, correct pattern that label-only lookup can't
  disambiguate. Result: the router silently cross-wired fan 1 and fan 2, and dropped 15 of the
  circuit's 22 wire connections into `LayoutResult.unresolved` — while the geometry-lint score
  *improved* (26 findings vs. 28, 0 vs. 4 non-orthogonal), because a wrong-but-straight wire
  scores better than a right-but-diagonal one. **The lint score alone is not sufficient evidence
  that a re-routed circuit is correct** — this is the clearest finding of the whole spike on
  that point. Fix needed before any further use: resolve each connection against the specific
  symbol *instance* `CircuitBuilder` actually wired (not a label re-lookup), and make label
  collisions raise/report rather than silently pick a survivor. Full trace in
  `auxillary_cabinet_v3/src/auto_router_demo.md`.
- **Real-cabinet regression check**: `auxillary_cabinet_v3`'s actual `cabinet.py` (which uses
  none of the new opt-in features) rebuilds byte-identical to before this work — confirmed via
  `cmp`. All four features are additive; nothing in the existing production path changed.

**Bottom line for tomorrow's review**: pagination, the bug fixes, and the geometry linter are
demonstrated, real, and reasonable to build on. The router's core A*/obstacle-avoidance logic
works and is fast (19-24ms on a real 22-connection circuit) but its `BuildResult` bridge has a
correctness bug that only a real multi-instance cabinet (not the round-2 spike's smaller
hand-built test circuits) was able to surface — do not wire it into any real rendering path
until that's fixed.

## Round 3 (2026-09-19): the router bug was worse than it looked, plus a real second bug

Visual review of `auxillary_cabinet_v3/src/auto_router_demo_after.svg` (rendered to PNG and
actually inspected, not judged by the lint-score summary above) showed the router wasn't
producing "cross-wired but plausible-looking" output — it was drawing long horizontal wires
straight across the entire page connecting two electrically unrelated relay rungs (K8's rung to
K9's rung), because `derive_routing_input` resolved wire endpoints by symbol *label* in a flat
dict, and this circuit repeats `"PLC:DI"`/`"PLC:DO"` reference tags identically once per fan
instance. The lint-score-only signal genuinely could not have caught this: the fabricated wires
were orthogonal and didn't cross text, so they scored *better* than the original diagonal wires.

Two real fixes landed as a result:

1. **`core/geometry_lint.py` gained a fifth check, `check_wire_symbol_collisions`** — the gap
   that let the fabricated wires score well: nothing previously flagged a wire that visibly cuts
   through an unrelated symbol's footprint (the obstacle bboxes existed, but were only ever used
   to judge whether a redundant-jog *alternative* would be clear, never as a check in their own
   right). A wire's own start/end symbol is excluded from its own collision test (ports commonly
   sit inside their symbol's bbox, not exactly on its edge) so legitimate connections don't
   false-positive. Run against all 12 real cabinet circuits: **10 new, real findings** in
   `pumps`/`fans` — traced to `pump_circuit.py`/`fan_circuit.py`'s current-transformer (`CT`)
   assembly, which is placed inline in the L1/L2/L3 power column but is *not* wired into that
   power path (only its secondary sense pins are connected) — the main conductor's auto-wire
   runs straight through CT's box because nothing else occupies that column position in the
   connection graph. Needs a domain call (is a clamp-style CT meant to sit inline in the drawing
   or offset beside the rail?), not fixed here.
2. **`router.py`/`pin_resolver.py`: replaced label-keyed resolution with per-`(tag, port_id)`
   instance resolution.** The first attempt (excluding any tag with more than one physical
   instance) was too aggressive — this domain routinely draws one logical component's coil and
   its SPDT contact as *separate* symbols sharing one tag (`"K8"` names both), which is legitimate
   and must still resolve correctly. The real fix: merge a tag's ports across all its instances
   into one pool (`pin_resolver.build_pin_resolver`), and only exclude a specific `(tag, port_id)`
   pair when *more than one instance under that tag* claims the identical real port id — which is
   exactly the `PLC:DI`/`PLC:DO` case (both fan instances' reference arrows expose the same port
   id `"1"`) and exactly *not* the K8 coil/contact case (disjoint port ids, no collision).
   `RoutingInput.symbols` (tag -> Symbol) became `RoutingInput.symbols_by_port`
   (`(tag, port_id)` -> Symbol) throughout `router.py` to carry this precision into the obstacle
   exclusion and position lookup.

Verified outcome on the real `fan_controll` circuit: re-rendered and visually inspected (not just
lint-scored) — the fabricated cross-page wires are gone; the router now safely drops 20 of 22
connections to `unresolved` (correct: `K8`/`K9`/`PLC:DI`/`PLC:DO`/`PLC:RELAY:3`/`4`/`X13`/`X51`/
`X52` are all genuinely multi-instance-shared tags in this specific circuit) rather than guessing
wrong. Re-run against `pumps` (a circuit *without* heavy tag reuse): 30 of 51 connections resolve
and route cleanly, producing tight ladder-style vertical rails with right-angle jogs — and the
router's own obstacle-avoidance correctly routes *around* the CT assembly's box that the manual
`draw_wire` path runs straight through (bug found in point 1, above), rather than needing a
separate fix. The remaining 21 unresolved in `pumps` are all genuinely multi-instance-shared
terminal/reference tags (`X01`, `X52`, `X53`, `PLC:AI:Sig`, `PLC:AI:GND` — one shared literal tag
per 3 pump instances), correctly refused rather than guessed.

**Remaining real limitation, unchanged in kind but now precisely scoped**: `BuildResult.wire_connections`
carries tag *strings*, not per-instance identity, so any circuit that legitimately reuses a tag
across more than one instance *and* repeats a port id under that tag (any bank of `count=N`
identical sub-circuits sharing fixed reference/terminal tags — common in this codebase) will see
those specific connections safely dropped, not routed. Fixing this for real needs
`CircuitBuilder` to log a real per-instance identity in `wire_connections` (bug #1 in the original
list below), not a smarter downstream resolver — pin_resolver/router can't invent identity that
was never recorded.

**Tooling fix, same investigation**: `scripts/pid_review.py`'s Playwright fallback (bug #11,
below) had a hardcoded A3-landscape viewport that silently cropped/distorted any SVG with a
different aspect ratio — exactly the router demo's 422.5mm x 165mm output. Fixed to size the
viewport from the SVG's own `width`/`height` attributes. This is very likely why the original
router bug shipped without being visually caught: the lint-score summary looked like an
improvement, and the one rendered artifact available for review was being cropped/scaled in a way
that made the defect harder to spot at a glance.

## Recommended architecture

A three-stage pipeline for `electrical` cabinet schematics, each stage independently useful
and separately shippable:

```
[ Full cabinet system ]
        │
        ▼
1. Partition into pages    ── project.partition() / add_partition()
   (pagination-partitioner)   manual override hook for ambiguous roles,
        │                     classify_link() for cross-page connectors
        ▼
2. Place & route each page ── electrical.layout.router (functional route_pure())
   (grid-astar-router)        real BuildResult -> port resolver, A* + turn/crossing penalties
        │
        ▼
3. Lint the result          ── core/geometry_lint.py + per-domain validation.py
   (svg-geometry-linter)       0 false positives on all 12 real electrical circuits;
                                also the QA gate for stages 1 and 2's own output
```

All three survived round 2 with working, tested prototypes at realistic scale (46-152
units depending on track) — not toy examples. Full evidence is in each track's deep-dive doc.

## Recommended implementation order

Ordered by dependency, not narrative order above — stage 3 (the linter) has zero dependency
on the other two and is immediately useful standalone, so it should land first:

1. **Fix the upstream port-naming bug** (see bug list below, #1). This unblocks a clean
   `(tag, pin) -> Port` resolver without heuristics, which `grid-astar-router`'s bridge needs
   and which is useful independent of any layout decision.
2. **Land `core/geometry_lint.py`** (svg-geometry-linter's 4 checks: orthogonality, text/wire
   collision, near-alignment, redundant jogs). Layer 0 — only touches `core.primitives`/
   `core.symbol` types, no domain knowledge, fits `ARCHITECTURE.md`'s file-role convention with a
   thin per-domain `validation.py` wrapper. Immediately useful as a standalone linter even
   before the other two stages exist.
3. **Fix the two real false-positive sources it found** (bug list #8, #9) — small, decoupled,
   improves linter accuracy immediately: `pcb/render.py`'s NC-marker needs a `Group` wrapper;
   `pid/builder.py` needs to either stop flattening equipment symbols or ship the
   `lint_pid_diagram()` workaround.
4. **Land the pagination API** (`partition_to_pages()` / `add_partition()`, mirrors
   `Project.add_pcb()`). Depends only on existing `CircuitBuilder`/`Project`, not on the new
   router — its column spacing is deliberately crude today but functional, so this can ship
   independently and start solving the "I currently split pages by hand" pain point immediately.
5. **Fix the pre-existing `Project` bug it found** (bug list #7) before shipping multi-page
   output broadly (Windows path-length failure on descriptive circuit keys).
6. **Land the router last** — most complex piece, and the one with real remaining work:
   - Fix the near-quadratic routing time (bbox-scoped search per route instead of whole-page
     search) before using it on real 100+ component cabinets.
   - Label-placement collision avoidance is out of scope for the router itself (68 remaining
     findings/run, ~0.25 per wire segment) — needs a separate label-placement pass.
   - Ship the functional `route_pure()` form, not a stateful class (round 2 reversed round 1's
     lean here: each route needs its own per-call exclusion set).
7. **Swap pagination's crude per-page column spacing for the router's placement** once step 6
   lands — round 2 confirmed the output shapes are a clean fit, no impedance mismatch.

## Bugs found along the way (independent of the redesign — fix regardless)

Ordered roughly by how many downstream findings depend on them:

1. **`BuildResult.wire_connections` logs semantic pin names** (e.g. `"L1"`/`"T1"`) that are not
   `Symbol.ports` dict keys (always positional `"1".."N"`) — found by `elk-bridge`, confirmed
   critical by the `grid-astar-router` deep-dive (a one-pass heuristic resolver based on this
   produced a *physically wrong* port assignment on a contactor's coil-return pin). Real fix:
   make `CircuitBuilder` log the port id it already resolves internally, not a smarter
   downstream resolver.
2. **`motor`'s port-count fallback assumes `poles*2=6`** but it only exposes 4 real ports —
   caused 3/15 wire connections in a test circuit to reference nonexistent pins. (`elk-bridge`)
3. **`draw_wire` never actually uses the semantic pin label** — matches by x-alignment instead.
   (`grid-astar-router` deep-dive)
4. **`component_tags()` silently drops all but the last tag** when multiple same-prefix
   components exist in one `build()` call. (`grid-astar-router` deep-dive)
5. **`fuse`'s default pins are `("", "")`.** (`grid-astar-router` deep-dive)
6. **`Project._render_multi_circuit_pages` (`project.py:1406`) joins circuit keys into a
   filename** — exceeds Windows' path length limit on a page with several descriptive keys.
   (`pagination-partitioner` deep-dive)
7. **`pcb/render.py`'s unconnected-pin "NC" X-marker is drawn as bare top-level `Line`s**,
   never wrapped in a `Symbol`/`Group` — a 1-line fix. (`svg-geometry-linter` deep-dive)
8. **`PIDBuilder.build()` flattens every placed equipment `Symbol` into `diagram.elements`**
   instead of preserving the wrapper (unlike `electrical`) — causes a tank's own outline to be
   misread as a wire. (`svg-geometry-linter` deep-dive)
9. **`pid`'s `pipe_tee`/junction primitive is defined but never wired into `PIDBuilder.pipe()`**
   — two pipes converging on one point render as exactly-coincident lines. (`pid-layout`)
10. **`manhattan_route` has no obstacle avoidance** — pipes cross instrument bounding boxes.
    (`pid-layout`)
11. **`scripts/pid_review.py`'s Playwright fallback hardcodes an A3-landscape viewport**,
    silently cropping tall electrical-ladder SVGs instead of erroring. (`vlm-critic`)
12. **`StandardTags.TRANSFORMER = "T"` is reserved but has no backing symbol factory.**
    Also missing: `indicator_light` (electrical), `relief_valve` (P&ID). Full geometry specs
    for all three are in `symbol-standards.md`, ready to implement directly. (`symbol-standards`)

## Dropped, deferred, or narrowed (see SYNTHESIS.md for full reasoning)

- **Dropped**: `constraint-solver` (a fixed total order beats z3/OR-tools by 100-11,000x),
  `pcb-layout` (already has a good deterministic engine, no change needed),
  `overview-shared-engine` (already has its own deterministic engine, no change needed),
  `llm-dsl-pipeline` (the placement API it wanted already exists — `PlacementOptions`/
  `EquipmentPlacement` — no new module needed).
- **Deferred**: `vlm-critic` — every real defect found reduces to bounding-box math the
  geometry linter already covers; revisit only if some defect category resists formalization.
- **Narrowed**: `pure-python-graph-layout` (`grandalf`'s crossing-minimization works, but it's
  dual GPLv2/EPLv1 — a real license conflict for this MIT project — and no candidate models
  ports/orthogonal routing; useful only as a future ordering-within-layer technique with a
  permissively-licensed reimplementation, not a standalone engine).
- **Not pursued for `electrical`**: `elk-bridge` — technically works end-to-end (Node
  subprocess bridge), but has no IEC-ladder awareness and neither `pid` nor `overview` need it
  either (each already has an adequate non-ELK solution). Worth rechecking the pure-Python
  `pyelk` port (found via this track, EPL-2.0, appeared Feb 2026) in 6-12 months once it
  matures — would eliminate the Node dependency entirely if ELK is ever needed for a future
  general-graph use case.
- **Separate track, lower urgency**: `pid-layout` — a working longest-path layered engine for
  P&ID equipment placement, clean architectural fit, but `pid` has no production consumer yet.
  Worth returning to once `pid` ships to a real consumer.

## Where everything is

- Branch `layout-improvment` has every finding, doc, and prototype consolidated (this doc,
  `SYNTHESIS.md`, 15 individual track docs under `docs/research/layout-improvement/`, and all
  prototype code under `research/layout/`).
- The 15 individual per-track branches (`layout-improvment-<track>` and
  `layout-improvment-deepdive-<track>`) still exist with their original commits if you want to
  inspect a track's raw history; their worktrees have been removed but the branches are intact.
- Dependency additions each track made in its own worktree (z3-solver, OR-tools, grandalf,
  networkx) were **not** merged into `layout-improvment` — check each track's own doc for what
  extras to `uv add` if you want to re-run its prototype directly.
- This is still throwaway spike code per the original scope — nothing here has touched
  `src/schematika/`. Turning any of the three recommended directions into production code is
  the next, separate piece of work (a `writing-plans`-style implementation plan per direction,
  once you've reviewed and picked what to act on).
