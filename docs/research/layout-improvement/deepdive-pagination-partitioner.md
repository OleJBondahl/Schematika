# Pagination partitioner -- round 2 deep dive

Track: `pagination-partitioner`. Round 1: `pagination-partitioner.md`. This
round takes the one surviving mechanism (rule-based rung-to-page splitting)
and does the work round 1 explicitly deferred: a much larger system, real
fixes for both open problems, and a `Project.partition()`-shaped API driven
end to end to a rendered PDF.

**Verdict: promote to a real `project.py` feature, with two concrete
prerequisite fixes (below) and one already-fixed prototype bug worth folding
into the promotion PR.** Both open problems from round 1 are solved with
code, not just a plan, and proven against a system 4x round 1's size. The
remaining work is genuinely small: wire `partition_to_pages`/`add_partition`
into `project.py`, fix `_render_multi_circuit_pages`'s long-filename bug,
and hand page-internal placement to `grid-astar-router`.

## What was built

`research/layout/deepdive-pagination-partitioner/`:

- `netlist.py` -- the rung/component/tag-link model, revised from round 1.
  The key change: `TagLink` no longer carries a manually-set
  `owner_boundary`/`user_boundary` flag. `ComponentSpec.kind` gained a third
  value, `"stub"` (an explicit "this chain end is genuinely severed here"
  placeholder), so the electrical meaning of a crossing is a *fact derived
  from the rung's own chain contents*, not an opinion a caller can get
  inconsistent. `RungSpec` gained `pin_to_function: str | None` -- the
  manual override hook for the ambiguous-role problem.
- `large_synthetic_system.py` -- 46 rungs: 2 independent power domains (each
  with a main incomer + 24VDC control bus), 10 functional control loops (5
  per domain, each motor-power + start/stop + contactor-coil), 2 ambiguous
  e-stop "master enable" rungs (one per domain, structurally identical to a
  loop's contactor-coil rung), 6 field terminal strips, and one legitimate
  bare severed-signal net (`WATCHDOG`, single owner/user pair, deliberately
  declared far apart so it lands on different pages).
- `partitioner.py` -- `classify_link()` (the Finding-1/3 fix),
  `_effective_bucket()` (the `pin_to_function` pre-pass), the severed-signal
  fan-out guard, and `partition_netlist_to_pages()` tying it together.
- `role_heuristic.py` -- the min-cut-style graph heuristic alternative,
  plus a curated ground truth and a comparison function.
- `render_pages.py` -- rung builder + `Project` bridge, revised to splice
  `ref()` in at an explicit `"stub"` component instead of round 1's
  start/end marker lists.
- `pagination_api.py` -- `partition_to_pages()` (layer-2 free function) and
  `add_partition()` (the `Project.partition()`-shaped registration step).
- `cross_page_lint.py` -- the pagination-specific coherence check.
- `guard_demo.py` -- proves the fan-out guard fires on a broken netlist and
  that the same fan-out resolves cleanly once terminal-anchored.
- `run.py` -- orchestrates all of the above; prints a full report and
  renders `output/large_synthetic_cabinet.pdf` (12 pages, committed).
- `_svg_to_png.py` -- visual-review helper, copied from round 1 unchanged.

Reproduction:

```bash
cd research/layout/deepdive-pagination-partitioner
uv run python run.py
uv run python _svg_to_png.py output/<page>.svg
```

## The large synthetic system

46 rungs vs. round 1's 12; two power domains instead of one; 10 functional
loops instead of 3; 6 terminal strips instead of 2. `partition_netlist_to_pages`
(budget 5 rungs/page) splits it into 12 pages: 4 power, 6 control/logic, 2
terminal. The full breakdown is in `run.py`'s printed output and reproduced
in the PDF's table of contents.

Three things were deliberately engineered in, per the assignment:

1. **A genuinely ambiguous rung, twice.** `estop_master_enable_a`/`_b`:
   `role="control"`, content is exactly "an aux contact tag-echoed in, a
   coil tag-echoed out, one terminal" -- structurally **identical** to
   `loop_N_contactor_coil`. The only thing that makes one "obviously power"
   and the other "obviously control" is what the tags mean, which no shape-
   or graph-based signal can see.
2. **A bus reused by more pages than a pairwise link can express cleanly.**
   Each domain's 24VDC terminal (`X4` / `X103`) is the first component of 6
   rungs (5 loop start/stops + 1 e-stop chain), which land on 3-4 different
   pages per domain once packed.
3. **A legitimate single-pair bare signal net** (`WATCHDOG`), to prove
   `ref()` still has a real job once terminal-anchored crossings are
   excluded from ever needing one.

## Problem 2: the ambiguous-role rung, solved

### The fix: `RungSpec.pin_to_function`

`_effective_bucket(rung, netlist)` (`partitioner.py`): if `pin_to_function`
is set, look up any *other* rung already declared under that function name
and adopt its `(role, function)` for bucketing purposes only.
`estop_master_enable_a` sets `pin_to_function="main_incomer_a"`; the
partitioner then buckets it exactly as if it were a native member of the
`main_incomer_a` function group.

### Before/after, on the actual system

```
estop_master_enable_a:
  before fix : page 9: Control & Logic (estop_a, estop_b, watchdog)
  after fix  : page 1: Power Distribution (control_supply_a, main_incomer_a, main_incomer_b)
estop_master_enable_b:
  before fix : page 9: Control & Logic (estop_a, estop_b, watchdog)
  after fix  : page 1: Power Distribution (control_supply_a, main_incomer_a, main_incomer_b)
```

Both ambiguous rungs move from a control-logic page shared with unrelated
e-stop/watchdog content onto the power page, directly beside the main
incomer whose contactor they gate -- rendered and visually confirmed
(`output/c000_c036_c001_c002_c038.png`, page 1: `X1/F1/Q1` main incomer with
`K12`->`Q1` coil immediately to its right, and the mirror for domain B).
That is exactly what round 1's Finding 2 said a human drafter would want.

### A real bug this surfaced: power wasn't grouped by function at all

Round 1's `_pack_groups` call for the power bucket was
`_pack_groups([power] if power else [], ...)` -- wrapping the *entire*
power-role rung list as a single undifferentiated group, then chunk-splitting
it every `max_rungs_per_page` rungs in **declaration order**. That was
harmless in round 1 (every power rung had a unique function name, so
grouping-vs-chunking made no difference), but it silently defeats
`pin_to_function`: the override changes a rung's effective *function*, but
if the power bucket never groups by function, a pinned rung can still be
separated from its target by an arbitrary positional chunk boundary. This
happened on first implementation here -- `estop_master_enable_a` initially
landed on page 3 while the real `main_incomer_a` stayed on page 1, 22 rungs
apart, silently defeating the override while every other test looked green.
Fixed by routing the power bucket through `_group_by_function` like the
other two buckets (`partitioner.py`, `partition_netlist_to_pages`). Worth
calling out because it is exactly the kind of defect an "it partitioned
without crashing" smoke test would miss -- only checking the *actual page
number* of the pinned rung against its target caught it.

### The min-cut-style heuristic, tried and compared

`role_heuristic.suggest_role_overrides()`: flags a rung when every one of
its tag-echo links points to rungs of a single role other than its own.
Run against the same system:

- **24 rungs flagged**, including both target rungs (`estop_master_enable_a`/`_b`)
  but also **all 10 `loop_N_power`, all 10 `loop_N_contactor_coil`, and
  both `main_incomer_a`/`_b`** -- 22 of 24 flags are false positives against
  the curated ground truth (0 false negatives).
- **Why it fails so completely**: a coil/contact pair crossing the
  power/control role boundary is not an anomaly in ladder logic, it is the
  *normal shape* of a contactor circuit. `loop_1_contactor_coil` and
  `estop_master_enable_a` are topologically indistinguishable (aux-contact-
  in, coil-out, one terminal) -- there is no shape or graph feature that
  tells them apart; only the modeler's intent does (one is "this loop's
  actuator, keep it with the loop's logic," the other is "a safety
  permissive, keep it with the power it gates"). A community-detection
  signal on this graph would need to reason about domain semantics no
  structural heuristic has access to.

This matches round 1's hedge but resolves it decisively rather than just
asserting it: the manual override is not "simpler but worse," it is the
only one of the two that produces the right answer at all on a realistic
system. **Recommendation confirmed: ship `pin_to_function`, do not ship a
graph heuristic.**

## Problem 3: shared-bus / severed-wire conflation, solved

### The fix: derive the classification, don't declare it

`classify_link(netlist, link)` (`partitioner.py`) looks at what
`ComponentSpec.kind` the tag actually resolves to on both sides:

| Owner kind | User kind | Classification | Arrow? |
|---|---|---|---|
| `terminal` | `terminal` | `terminal_crossing` | Never, any fan-out |
| `symbol` | `symbol` | `tag_echo` | Never (`reuse_tags`), any fan-out |
| anything else (a `stub` on one/both sides) | | `severed_signal` | Yes, capped at 1 owner + 1 user |

This directly fixes round 1's Finding 1 (the exact same physical terminal,
`X4`, got an arrow at one crossing and none at two structurally identical
ones, because a human had to remember to flip a flag consistently) by
removing the flag: there is nothing left to get inconsistent, because the
answer comes from the rung's own declared components.

### Proof: the bus at fan-out 6, zero arrows

Each domain's bus terminal (`X4` / `X103`) is now wired with an explicit
`TagLink` to every rung that repeats it (6 links per domain: 5 loop
start/stops + 1 e-stop chain) -- round 1 only ever declared one such link
per bus and treated the other reuses as implicitly fine, which is exactly
the inconsistency this fix removes. Run output:

```
terminal crossings (no marker, self-documenting): 12
off-page connector markers emitted: 2
```

12 terminal crossings (6 per domain) span 3-4 different pages each, all
correctly resolved to zero arrows -- visually confirmed: every rung
repeating `X4`/`X103` simply redraws the terminal circle with its id, which
is how a real terminal strip drawing convention already works.

### Proof: the fan-out guard fires instead of producing garbage

`guard_demo.py` builds a deliberately bad netlist -- a bare `"BROKEN"` stub
tag referenced by 1 owner + 3 users (fan-out 4, no terminal or symbol
anchoring it anywhere). `partition_netlist_to_pages` raises before ever
reaching the render step:

```
[guard fired, as expected]
  severed-signal tag 'BROKEN' is referenced by 4 rungs (['broken_owner',
  'broken_user_0', 'broken_user_1', 'broken_user_2']) with no physical
  terminal or symbol anchoring it. ref() exposes one port and cannot fan
  out beyond one owner and one user. Anchor this net at a physical terminal
  ...
[fix verified] same fan-out, terminal-anchored: 1 pages, 0 off-page markers
```

The same fan-out, re-anchored at a terminal instead of a bare stub, resolves
with zero arrows and no error -- proving the fix is "use a terminal," not
"reduce fan-out," which matches how real cabinets already avoid this
problem (a bus almost always terminates at a physical block).

### Proof: the one legitimate arrow pair still works, and only when it should

`WATCHDOG` (owner `watchdog_relay`, user `watchdog_consumer`) is deliberately
declared far apart in the netlist so the packer puts them on different
pages (5 and 10). Visually confirmed both sides
(`output/c037_c045.png` shows the jump-in arrow labeled `/5.C1`, matching
`output/c003_c005_c008_c011_c014.png`'s domain -- see `run.py`'s printed
page list for the exact page-to-svg mapping). When the same two rungs were
first declared adjacently (an earlier iteration of this system), they landed
on the *same* page and the partitioner correctly emitted **no** arrows at
all (added a same-page guard mirroring the existing `terminal_crossing`/
`tag_echo` same-page skip) -- an arrow pointing at "the page you're already
on" would be noise, not signal.

## The `Project.partition()`-shaped API

`pagination_api.py`. Two functions, two different layers, deliberately not
one:

- **`partition_to_pages(netlist, *, max_rungs_per_page=5) -> PartitionedElectricalResult`**
  (layer 2, plain function, not a new builder class). It partitions the
  whole rung graph and builds every rung's `BuildResult` in one call. This
  is a **free function**, not a mutable builder, because there is no
  meaningful partial state between "have a `SystemNetlist`" and "have every
  rung built and paged" -- the whole graph is known upfront in one call,
  unlike `CircuitBuilder`, which exists specifically to accumulate one
  rung's components across many incremental calls. `pcb.build(circuit,
  mapping)` is the existing precedent for exactly this shape.
- **`add_partition(project, result, /) -> Project`** (layer 4, mirrors
  `Project.add_pcb`, `project.py:424`, almost line for line): loops
  `add_circuit`/`page` calls to register an *already-built* result. It does
  not partition or render anything itself -- `API_STYLE.md`'s verb table
  reserves `add_<noun>` for registration and bare verbs (`build`, `render`,
  `compile`) for producing output, so `add_partition` (register) is the
  correct verb, not a bare `partition()` (which would wrongly claim to do
  the computation itself).

Driven end to end in `run.py`: `build_large_system()` ->
`partition_to_pages()` -> `add_partition(project, result)` ->
`project.build(pdf_path, ...)` -> a real 12-page PDF.

### A real bug this surfaced: long merged-page filenames break on Windows

`Project._render_multi_circuit_pages` (`project.py:1406`) names a merged
page's SVG `"_".join(page_def.circuit_keys) + ".svg"`. With this system's
rung keys (`loop_9_start_stop`, `estop_master_enable_a`, ...), a 5-rung
page's merged filename exceeds Windows' ~260-char path limit and
`ElementTree.write` fails with a bare `FileNotFoundError` -- no error
message pointing at the real cause. `add_partition` works around it by
registering short synthetic circuit keys (`c000`, `c001`, ...) instead of
the netlist's own descriptive keys. **This is a pre-existing `project.py`
bug, independent of this track**, and will bite any real cabinet with
enough rungs per page and descriptive circuit keys, on Windows, regardless
of whether pagination is automatic or hand-written. Worth fixing in
`project.py` directly (e.g. hash/truncate merged keys past some length)
before or alongside promoting this feature.

## Quality checks

### Cross-page connector coherence (new, pagination-specific)

`cross_page_lint.check_offpage_connector_coherence()`: verifies every
severed-signal net crossing a page boundary has *exactly* one marker on
each side, pointing at each other, with opposite directions; and that no
`terminal_crossing`/`tag_echo` link ever produced a marker (round 1's
Finding-1 bug, now enforced as a check rather than just documented). Run
against the full 12-page partition:

```
clean -- every severed-signal net has exactly one coherent pair
```

### Geometry linter (round 1's `svg-geometry-linter`)

Only the round-1 version of the sibling track was available in this
worktree (`research/layout/svg-geometry-linter/linter.py`) -- `deepdive-
svg-geometry-linter/` is being built in a sibling git worktree, a genuinely
separate directory this agent was instructed not to read. Ran
`lint_elements` against every one of the 46 built rungs' pre-render element
trees:

```
total: 0 finding(s) across 46 rungs, cost=0.00
```

Zero findings across orthogonality, text/wire collision, near-alignment,
and redundant-jog checks, on a system 4x round 1's size. Consistent with
round 1's own report of 0 false positives on real circuits -- this track's
job (page membership + off-page markers) doesn't introduce the geometry
defect categories that linter targets, which is expected: it never draws a
wire, only decides which rung goes on which page and which rung ends get a
`ref()` symbol appended (a normal `add_symbol` call, geometrically no
different from any other symbol).

## Integration awareness: does the output shape fit `grid-astar-router`?

This track's output per page is `PageAssignment.rung_keys` -- an ordered
tuple of whole rungs, each independently built (`BuildResult`) with only a
flat per-rung x-offset (`render_pages._column_positions`, a constant per
pole-count, unchanged from round 1's deliberately crude placeholder). That
is the right *granularity* to hand to a placement engine: `grid-astar-router`
would need to consume "a page is an ordered set of rung `BuildResult`s, each
with declared ports" to place them and route between them, which is exactly
what this shape provides -- no impedance mismatch there.

One real mismatch to flag: **this track completely decides column order and
x-position before any router runs** (`_column_positions`). A real
integration should invert that -- `partition_to_pages` should hand
`grid-astar-router` the *unpositioned* per-page rung list and let it own all
placement, rather than layering a router under an already-fixed layout. The
`x`/`y` this track sets via `builder.set_layout` would need to become the
router's output, not this track's input. Not a blocker, just a sequencing
note for whoever wires the two together: don't call `_column_positions`
(or its production equivalent) at all once the router exists.

## Concrete next steps to ship this as a real `project.py` feature

1. Fix `Project._render_multi_circuit_pages`'s long-merged-filename bug
   (`project.py:1406`) -- independent prerequisite, will affect any large
   real cabinet regardless of pagination automation.
2. Port `netlist.py`'s model (`RungSpec`, `ComponentSpec`, `TagLink`,
   `pin_to_function`) into `electrical/` as the partitioner's public input
   type -- these are stable, not spike-only.
3. Port `partitioner.py`'s `classify_link`/`_effective_bucket`/
   `partition_netlist_to_pages` and `pagination_api.py`'s
   `partition_to_pages`/`add_partition` into `electrical/` and `project.py`
   respectively, matching the shapes justified above.
4. Replace `render_pages._column_positions`'s flat constant with
   `grid-astar-router`'s placement output once that track lands (see
   integration-awareness note).
5. Port `cross_page_lint.py`'s coherence check into whatever validation
   layer `electrical/validation.py` (per `ARCHITECTURE.md`'s aspirational
   file-role convention) ends up being -- it is a real invariant check, not
   spike-only, and it is cheap (pure model-level, no rendering).
6. Decide a default `max_rungs_per_page` from real cabinet data (this
   spike used 5, tuned only against this synthetic system) and make it a
   `Project.partition()` parameter, not a hardcoded constant.
