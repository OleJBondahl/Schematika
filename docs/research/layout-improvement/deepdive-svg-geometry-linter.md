# Deep dive: svg-geometry-linter (round 2)

Round 1 verdict: **pursue with caveats.** `lint_elements` (walks Schematika's
pre-render `Circuit.elements`, not rendered SVG) hit 0 false positives on 2
hand-curated `electrical` circuits after fixing two real gaps (symbol-glyph
lines mistaken for wires, rotated text bboxes). Explicitly flagged as
unresolved: only 2 examples tested, no obstacle model for the redundant-jog
check, an uncalibrated text-width constant, and the optimizer-objective use
case was sketched, not built.

**Round 2 verdict: pursue, with a concrete scope correction.** The core
finding survives and strengthens: model-level linting generalizes cleanly
across every real `electrical` circuit this repo has (12/12, 0 false
positives) with zero changes needed. But testing beyond `electrical` --
which round 1 never did -- surfaced a **second, more severe instance of
round 1's own founding false-positive class** in both `pcb` and `pid`, each
requiring a different fix. The obstacle model, calibration, and optimizer
tasks are all done and proven; the biggest news this round is where the
`Symbol`-vs-wire assumption breaks, not that it holds.

## What changed since round 1

`research/layout/deepdive-svg-geometry-linter/` (this round's code; round
1's `research/layout/svg-geometry-linter/` is untouched):

- `linter.py` -- same four checks, four substantive changes:
  1. `check_redundant_jogs` is now obstacle-gated (`obstacles: tuple[Box, ...]`)
     -- only fires when a simpler candidate route is *proven* unobstructed.
  2. `_chain_wires` is rewritten as a degree-aware graph walk, fixing a real
     bug in round 1's version (see below).
  3. `estimate_text_bbox` uses `CHAR_WIDTH_EM`, a per-glyph table calibrated
     from the actual Times New Roman font file via `fontTools`, replacing
     the single guessed `AVG_CHAR_WIDTH_EM = 0.52` constant.
  4. New `lint_build_result()` (single-call convenience wrapper) and
     `lint_pid_diagram()` (domain-specific workaround for `pid`'s equipment
     flattening -- see below).
- `calibrate_text_metrics.py` -- PEP 723 script (fontTools, calibration-time
  only), reads `C:\Windows\Fonts\times.ttf`, prints the `CHAR_WIDTH_EM` table
  pasted into `linter.py`.
- `run_real_circuits.py` -- builds and lints every real circuit this repo's
  `examples/`/builders can produce: 12 `electrical` circuits (examples
  01-05 standalone, plus every page circuit inside examples 06 and 07's
  `Project`s), 1 `pcb` circuit (example 09's interface board), 1 `pid`
  circuit (`pid_process_train`, built directly through `PIDBuilder` --
  no `examples/` script uses `pid` yet).
- `perturb_messy.py` -- injects 3 known, targeted defects into a real clean
  circuit (simulating messy auto-placed output) and checks recall/precision
  against exactly what was injected.
- `optimizer_demo.py` -- a real coordinate-descent nudge loop using
  `LintReport.cost` as its sole objective, run against the same injected
  defects.
- `test_synthetic_defects.py` -- round 1's 7 tests plus 8 new ones covering
  every fix above, including reproductions of the specific bugs being
  fixed. 15/15 pass.
- `examples/`, `findings/` -- generated SVGs/output text from the above.

## Task 1: every real circuit, not just 2

`run_real_circuits.py`'s results (`findings/real_circuits.txt`):

| Domain | Circuits tested | Findings | False positives |
|---|---|---|---|
| `electrical` | 12 (examples 01-05 standalone + all page-circuits in 06's and 07's `Project`s) | 0 | 0 |
| `pcb` | 1 (example 09's interface board) | 12 | **12 (100%)** -- all one root cause |
| `pid` | 1 (`pid_process_train`, hand-built: tank->pump->heat_exchanger->valve, 2 instruments, 1 off-axis pipe forcing a Manhattan bend) | 7 via naive `lint_elements`; 4 via `lint_pid_diagram` | **3 of 7 (43%) via naive call; 0 of 4 via the fixed entry point** |

**Electrical: the round-1 result generalizes for free.** All 12 circuits --
including `05_multi_builder` (custom `block` symbol, explicit `connect()`
wiring, PLC reference arrows) and every multi-page `Project` in 06/07 --
came back at 0 findings with zero changes to round 1's `Symbol`-vs-wire
filter. This is the strongest evidence yet that the model-level approach
generalizes across circuit *shape* within a domain, not just the 2 examples
it was built against.

**`pcb`: 12/12 findings are one root cause, not a linter bug.** Every
finding traces to `src/schematika/pcb/render.py:80-96`
(`_render_terminator`, `Terminator.NC` branch): an unconnected-pin marker is
drawn as two literal diagonal `Line`s forming an X, appended **directly to
`circuit.elements` at the top level** -- not wrapped in a `Symbol` or
`Group` the way `electrical`'s breaker/fuse glyphs are (round 1's fix
target). `lint_elements`'s `inside_symbol` filter has nothing to catch here
because there is no `Symbol` boundary to detect; the X-mark's two lines
look exactly like a crooked 45-degree wire, and its "NC" label looks exactly
like it collides with one. Confirmed by direct correspondence: 3 NC pins x
(2 lines + 2 text collisions) = 12, matching the reported findings exactly,
and the reported coordinates (`(90,40)`, `(100,40)`, `(110,40)`, all `half=1.0`
per `render.py:81`) match `_render_terminator`'s literal `x-1`/`x+1` geometry.
**This is round 1's exact false-positive class, recurring because it was
fixed at the call site (`lint_elements`'s `Symbol` check), not at the root
(every domain's renderer being disciplined about wrapping decorative
non-wire geometry in a `Symbol`/`Group`).**

**`pid`: a worse version of the same problem, at the whole-equipment level.**
Tracing the `redundant_jog_candidate` finding on a diagram with a *single,
pipe-free* `tank` equipment (see `test_lint_pid_diagram_excludes_equipment_glyph_lines`
for the reduced repro) led to `src/schematika/pid/builder.py:459-465`:

```python
diagram.equipment.append(sym)
diagram.elements.extend(sym.elements)   # <-- flattens, doesn't wrap
```

`PIDBuilder.build()` flattens **every placed equipment `Symbol`'s children**
directly into `diagram.elements`, unlike `electrical/system/system.py:54`
(`add_symbol`), which appends the `Symbol` itself as one element. Round 1's
entire fix -- "don't treat symbol-interior `Line`s as wires" -- depends on
that wrapper still being there to recurse into with `inside_symbol=True`.
For `pid`, it is gone by the time `diagram.elements` exists: a tank's
rectangular outline is 4 bare top-level `Line`s that close into a loop and
trip `check_redundant_jogs` (`turns=3` on the 4-segment closed rectangle) --
a defect that does not exist, on a diagram with zero pipes. On the fuller
`pid_process_train` circuit, this same flattening also produced a spurious
`redundant_jog_candidate` (heat exchanger's internal U-tube pass lines
merging into a nearby pipe's chain) and a spurious `near_misaligned_pins`
(an equipment-interior point coincidentally 0.5mm from an unrelated point
elsewhere) -- 3 of the naive path's 7 findings, all eliminated once
equipment-glyph lines are excluded, none of which reflect anything about
the actual pipe routing.

**Fix, without touching `pid/builder.py`:** `linter.py::lint_pid_diagram()`
exploits the fact that `diagram.equipment` *still* holds each placed
equipment as an un-flattened `Symbol` (`build()` extends `diagram.elements`
from the same `Symbol` object, so the `Line` instances in
`diagram.equipment[i].elements` and the flattened copies in
`diagram.elements` are identical by `id()`, not copies). It collects every
`Line` reachable from any `diagram.equipment` entry, excludes those
specific objects from the wire population, and feeds each equipment's
bounding box to `check_redundant_jogs` as an obstacle -- restoring both
things the `Symbol` wrapper would have given `lint_elements` for free.
Proven both against the reduced synthetic repro
(`test_lint_pid_diagram_excludes_equipment_glyph_lines`) and against
`pid_process_train`: naive `lint_elements(diagram.elements)` returns 7
findings (3 false positives), `lint_pid_diagram(diagram)` returns exactly
the 4 real ones (a signal line from an instrument bubble back to its host
equipment crossing the bubble's own tag-number text -- a genuine geometry
overlap, most likely from this test circuit's own simplistic port choice of
routing the signal line through the same x-coordinate as the bubble, but a
real, correctly-caught overlap either way).

**Scope note (not tested, not applicable):** `examples/08_showcase_harness.py`
(`cable`/`CableRun`) and `examples/10_showcase_overview.py` (`overview`)
were deliberately excluded -- neither produces a `core.primitives.Element`
tree (`cable` renders through a WireViz-style drawing DSL; `overview` is
Cytoscape/JS-based). `lint_elements`/`lint_pid_diagram` do not apply to them
at all; a geometry linter for either would need a different data model
entirely, not a variant of this one.

## Task 2: messy/auto-placed output

The sibling round-2 track `deepdive-grid-astar-router` had produced no
round-2 output yet at the time this was run (`git status` in that worktree
is clean past round 1's commit) -- so this uses the task's fallback:
targeted perturbation of a real, verified-clean circuit
(`perturb_messy.py`).

Three known defects injected into `02_dol_starter` (0 findings before):
a near-miss wire (both endpoints shifted +0.3mm in x -- stays straight,
drifts off its column), a crooked wire (one endpoint shifted +0.6mm --
tilts past the 0.5deg tolerance), and a wire label dragged onto a wire it
doesn't belong to. Result: **all 3 injected defect kinds detected, 0
unexpected finding kinds** (`redundant_jog_candidate` -- the kind that would
indicate the perturbation accidentally created bogus chain topology -- did
not appear).

One real, worth-noting side effect: the single near-miss injection produced
**12** `near_misaligned_pins` findings, not 1. `check_near_alignment`
compares every pair of points in the whole diagram, so one wire drifting
0.3mm off its column registers once against every other point in that
column (6 other points at that column's exact x, symmetric pairs both
directions = 12). This is not a bug -- each pairing is independently true
-- but it means raw finding *count* overstates distinct defects by a
combinatorial factor that grows with diagram size; a human-facing report
should probably dedupe by wire/column before display (the cost sum used by
the optimizer does not need this fix -- see below).

## Task 3: obstacle-aware jog check, with adversarial proof

**The bug in round 1's `_chain_wires`, found by code reading, not fuzzing:**
it computed `head, tail = chain[0].start, chain[-1].end` once per
`while extended` pass, then let its inner `for seg in remaining` loop keep
matching every remaining segment against that **same stale tail** without
refreshing it after a match. If two *different* segments both touched the
tail (a T-junction -- e.g. a shared rail feeding two independent
downstream devices), both got appended back-to-back into one fictitious
chain, even though the second segment has nothing to do with the first two.

Concrete, reproduced false positive (`test_junction_false_positive_reproduced_and_fixed`):
three segments meet at `(0, 10)` -- a vertical `drop` ending there, and two
**independent** wires (`tap_a` running right, `tap_b` continuing up) both
starting there. Verified directly against round 1's linter:

```
round-1 _chain_wires: [[drop, tap_a, tap_b]]   # fabricated single chain
round-1 findings: [redundant_jog_candidate (3 segments, 2 turns, weight 1.0)]  # FALSE POSITIVE

round-2 _chain_wires: [[drop], [tap_a], [tap_b]]   # correctly stops at the junction
round-2 findings: []
```

**Fix:** `_chain_wires` now computes the degree of every snapped endpoint
first (how many segment-endpoints coincide there) and only continues a
chain through a point where degree is *exactly* 2 (this segment's own
endpoint, plus exactly one other). Degree 1 (free end) or degree >= 3
(junction) always stops the chain -- it never guesses which of several
touching segments "continues" it. This cannot prove two wires that happen
to meet end-to-end at a true degree-2 point are the *same* logical wire
(`Line`/`Circuit.elements` carries no net/wire identity to check against --
confirmed by reading `electrical/layout/layout.py::draw_wire`, which
returns one `Line` per matched port pair with no id field), but it
eliminates the provably-wrong multi-branch-merge bug above, which was a
real defect independent of that irreducible limitation.

**Obstacle gating** (`check_redundant_jogs(segments, obstacles=...)`): a
chain's extra turns are only reported if at least one simpler candidate
route (0-turn if collinear, else either single-L-bend) between its overall
endpoints is *provably unobstructed* by every given `Box`. Proven both ways
(`test_jog_suppressed_when_obstacle_justifies_it` /
`test_jog_still_flagged_when_route_is_clear`): the identical 3-turn
staircase is suppressed when an obstacle blocks every simpler route, and
still flagged when the obstacle is nowhere near either candidate.
`lint_elements` feeds every `Symbol`'s bounding box (via a duck-typed
`_bbox_of`, mirroring `core/bbox.py::compute_bounding_box`'s coverage) as an
obstacle automatically -- no caller wiring needed.

## Task 4: calibrated text-collision metrics

Schematika's renderer names an exact font: `TEXT_FONT_FAMILY` /
`TEXT_FONT_FAMILY_AUX` in `core/constants.py` are both literally
`"Times New Roman"`. `calibrate_text_metrics.py` reads
`C:\Windows\Fonts\times.ttf` via `fontTools` (PEP 723, calibration-time
only -- never a runtime dependency, matching round 1's shapely verdict) and
extracts real per-glyph advance widths (`hmtx` table / `unitsPerEm`) for the
character set Schematika's labels actually use (A-Z, 0-9, space, and
`.-_:()/`), plus `hhea` ascent/descent.

Measured spread is large -- round 1's single 0.52em/char guess was wrong in
both directions:

| String | Old (0.52em/char) | Calibrated | Delta |
|---|---|---|---|
| `"X1"` | 1.040 | 1.222 | **+17.5%** |
| `"PE"` | 1.040 | 1.167 | +12.2% |
| `"GY_0_5"` | 3.120 | 3.444 | +10.4% |
| `"-K1"` | 1.560 | 1.555 | -0.3% |
| `"WWWW"` | 2.080 | 3.775 | **+81.5%** |
| `"IIII"` | 2.080 | 1.332 | **-36.0%** |

`TEXT_HEIGHT_EM` (the above-baseline height used for `dominant_baseline="auto"`,
the only value Schematika emits) is likewise recalibrated from a guessed
`0.72` to the font's real `hhea` ascent, `0.8911`. Descent (`0.2163em`) is
documented but not modeled -- Schematika's real label content (tags,
wire-codes, pin IDs) is uppercase with no descenders, so the omission is a
scoped decision, not an oversight.

**Validated as a real verdict-flipping change, not a cosmetic number**
(`test_calibrated_width_catches_missed_collision` /
`test_calibrated_width_clears_false_collision`): a wire placed just past
where the *old* uniform estimate would put `"WWWW"`'s edge is a false
negative under the old constant and a correct catch under calibration; the
symmetric case with `"IIII"` is a false positive under the old constant and
correctly cleared under calibration.

## Task 5: optimizer-objective demo, built for real

`optimizer_demo.py`: a plain coordinate-descent hill-climber (try +-step on
each of 2 movable parameters, keep any move that strictly reduces
`lint_elements(...).cost`, halve the step on a sweep with no improvement),
run against `02_dol_starter` with the same near-miss + crooked-wire defects
`perturb_messy.py` injects (text-collision defect excluded -- nothing in
this demo's move set, wire-endpoint nudges, can fix a label placement; an
honest scope note, not a hidden failure).

**Result: cost 10.46 -> 1.87 (-82%), findings 13 -> 1 (-92%) in 48 candidate
evaluations.** This proves the core premise: `LintReport.cost` is a real,
usable, cheap-to-evaluate objective that a naive search can act on with no
rendering step in the loop.

**It does not fully converge to the injected ground truth (x=10.0 exactly),
and the reason why is itself a useful finding.** `check_near_alignment`'s
weight formula, `(tolerance - delta) / tolerance * 2.0`, is deliberately
*highest* when `delta` is smallest ("closer to exact -> more clearly a bug,
not a coincidence" per round 1's own comment) -- a reasonable choice for a
human-facing severity signal, but it means the gradient right next to the
true fix points *away* from it: moving from `delta=0.3` toward `0.2` and
`0.1` *increases* that pairing's weight before the discontinuous drop to
`0` at exactly `delta=0`. Combined with the check's own hard tolerance
cutoff (moving fully past `0.5mm` costs nothing, since the pairing stops
being "near" at all), a single large step can find it cheaper to escape the
tolerance window entirely than to climb down the reverse-sloped hill toward
the actual fix -- which is exactly what the demo's optimizer did with
wire 7 (settled at `x=10.8`, clear of the window, rather than `x=10.0`).
Confirmed by experiment: swapping in a monotonic-in-distance weight
(`weight = delta / tolerance * 2.0`, increasing toward the tolerance edge
instead of the true fix) measurably changes which local optimum the same
search finds, supporting the diagnosis. **This is a real, generalizable
insight, not a demo artifact:** a weight designed to signal "how confident
are we this is a bug" to a human and a weight designed to be "how far is
this from the fix" for a gradient search are different functions, and round
1's formula optimizes only for the former. A production optimizer built on
this cost function should either use a monotonic-in-distance weight
variant for the near-alignment check specifically, or use a search strategy
that isn't purely greedy (simulated annealing, multi-start, or a
larger-neighborhood move that can jump straight to `delta=0` candidates)
to avoid this class of trap. The orthogonality check has no such cutoff
(continuous in angle) and converges to it without the corresponding issue.

## Task 6: integration awareness / calling convention

Round 1's calling convention was two steps: get `.circuit.elements` (or
whatever field), then call `lint_elements`. That is not quite a single call
for a `grid-astar-router`/`pagination-partitioner` caller that wants to lint
whatever `*BuildResult` it just produced without knowing which domain it
came from. `linter.py::lint_build_result(result)` is now the one function to
call: duck-typed on `.circuit` (electrical/pcb, unchanged path),
`.diagram` (pid, dispatches to `lint_pid_diagram` -- see task 1's findings
for why that dispatch matters, not just a rename), or a bare `.elements`
otherwise. `grid-astar-router` and `pagination-partitioner` should both call
`lint_build_result(result)` and read `.cost`/`.findings`/`.by_kind()`; no
other setup needed.

## Verdict and next steps

**Pursue.** The four checks remain cheap, deterministic, and -- for
`electrical`, which is what actually ships to consumers -- proven clean
across every real circuit this repo has, not a curated pair. Round 2 closed
all three gaps round 1 flagged (obstacle model, text calibration, optimizer
demo) with working, tested code, and the obstacle-aware jog check has a
concrete adversarial proof (not just "no false positive found yet"). The
real news this round is structural, not incremental: **the `Symbol`-vs-wire
distinction round 1 fixed for `electrical` is not automatically safe in
other domains**, and this round found two different ways it breaks
(`pcb`'s NC-marker glyph bypassing the `Symbol` wrapper entirely; `pid`
discarding the wrapper for *every* equipment). Both are real Schematika
modeling gaps, not linter bugs, and are worth fixing regardless of this
linter's fate.

**Where this belongs, revisited:** round 1 proposed a `validation.py` per
domain package (matching `docs/ARCHITECTURE.md`'s aspirational file-role
convention). Round 2's findings sharpen that: the four checks themselves
(`check_orthogonal`, `check_text_wire_collisions`, `check_near_alignment`,
`check_redundant_jogs`) operate purely on `core.primitives`/`core.symbol`
shapes (`Line`, `Text`, `Symbol`, `Group`, `Point`) with zero domain
knowledge of breakers, tanks, or connectors -- they satisfy `core`'s
zero-domain-import invariant today (this prototype only avoids importing
`schematika` for standalone-testability, not because it needs to; a real
version could import `core.primitives`/`core.geometry` directly, same as
`core/bbox.py` already does). Recommendation:

1. **Shared engine as `core/geometry_lint.py`** (or `core/validation.py`) --
   layer 0, the four checks plus `lint_elements` verbatim. This is safe
   under the one-way dependency rule (`core` importing nothing from any
   domain package) and avoids `electrical`/`pid`/`pcb` each reimplementing
   the same orthogonality/collision/alignment/jog math.
2. **Each domain gets a thin `validation.py`** per the existing aspirational
   convention, supplying only domain-specific wire/obstacle extraction:
   `electrical/validation.py` is close to a direct passthrough (already 0
   findings everywhere tested); `pid/validation.py` wraps the
   equipment-exclusion logic `lint_pid_diagram` prototypes here (or, better
   long-term, `pid/builder.py:459-465` should stop flattening and preserve
   the `Symbol` wrapper the way `electrical` does -- a real production fix
   that would make `pid/validation.py` trivial too, but needs someone to
   check what else in `pid`/its tests assumes the flattened shape before
   changing it; out of scope for this spike); `pcb/validation.py` needs the
   same audit `pid` just got -- this round only found the one `NC`-marker
   case because that's what the test circuit exercised, and `pcb/render.py`
   should be checked for other decorative-line-outside-`Symbol` spots
   before shipping.
3. **Fix `pcb/render.py:82-87`** to wrap the `NC` X-mark in a `Group` (a
   1-line change, same pattern `electrical`'s breaker/fuse glyphs already
   use) -- removes the false-positive source at the root instead of
   teaching the linter to special-case it.
4. Before wiring either placement engine (`grid-astar-router`,
   `pagination-partitioner`) to this: have both call `lint_build_result`
   (task 6) so neither needs domain-specific knowledge, and re-run
   `run_real_circuits.py`-style coverage against `grid-astar-router`'s
   actual auto-routed output once it exists (still not available as of this
   run) -- the perturbation test here is a reasonable proxy but is not a
   substitute for the real thing.
