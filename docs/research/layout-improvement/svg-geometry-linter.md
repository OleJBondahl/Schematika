# Track: svg-geometry-linter

Question: can a deterministic geometry linter (no vision model, no pixels)
reliably catch the visual defects that make generated schematics look sloppy
-- crooked/non-orthogonal wires, text-on-wire collisions, misaligned pins,
redundant wire jogs -- and could its defect count double as an optimization
objective for any layout engine?

**Verdict: pursue with caveats.** The four checks are cheap, deterministic,
and (once two real false-positive sources were found and fixed) came back
clean on two real hand-built circuits while still catching every hand-built
synthetic defect. But "clean on two examples" is a weak sample, and the
prototype's biggest lesson is that *naive* geometry linting produces
confident, plausible-looking false positives -- getting a trustworthy
pass/fail (or a trustworthy cost number) required understanding Schematika's
own rendering internals, not just its output SVG.

## What was built

`research/layout/svg-geometry-linter/`:

- `linter.py` -- the linter itself, stdlib-only. Two entry points into the
  same four checks:
  - `lint_elements(elements)` walks Schematika's pre-render geometry model
    (`Circuit.elements`: `Line`/`Text`/`Group`/`Symbol` from
    `schematika.core.primitives` / `schematika.core.symbol`).
  - `lint_svg_text(svg_source)` regex-extracts `<line>`/`<text>` tags from a
    rendered SVG string -- the "no access to internals" alternative.
  - Checks: `check_orthogonal`, `check_text_wire_collisions`,
    `check_near_alignment`, `check_redundant_jogs`.
  - `LintReport.cost` sums each finding's `weight` into one scalar.
- `run_model_linter.py` -- builds two real circuits through the actual
  `schematika` API (identical to `examples/02_dol_starter.py` and
  `examples/04_spdt_positioning.py`), lints both entry points, writes
  `findings/findings.txt`.
- `test_synthetic_defects.py` -- feeds each check a hand-built true positive
  and a hand-built true negative, so a future "0 findings" run means "clean"
  and not "the checks silently stopped firing."
- `shapely_compare.py` -- PEP 723 standalone script (`uv run --script`,
  pins `shapely==2.1.2`, never touches this repo's `pyproject.toml`)
  comparing the stdlib and shapely implementations of two checks.
- `examples/dol_starter.svg`, `examples/spdt_positioning.svg` -- the real
  generated SVGs the linter was run against.
- `findings/findings.txt` -- full run output.

## What it actually found

### First pass: two real false-positive sources, not real defects

The first run against the real DOL-starter circuit (`examples/02_dol_starter.py`,
regenerated fresh via `uv run examples/02_dol_starter.py`) reported 27
findings -- 12 "non-orthogonal wire," 12 "text/wire collision," 3 "redundant
jog." All 27 were false positives, from two distinct bugs in the naive
version of the linter, not from the circuit:

1. **Symbol-interior glyph lines counted as wires.** IEC 60617 breaker and
   thermal-overload symbols are drawn with intentionally diagonal strokes
   (a breaker's isolator blade, a fuse-style "X" cross) --
   `src/schematika/electrical/symbols/breakers.py`'s `blade`/`cross_line_1`/
   `cross_line_2`. These are `Line` elements nested inside a `Symbol`,
   appended to `Circuit.elements` as one placed unit
   (`electrical/system/system.py:54`). Actual connecting wires are a
   *separate* population: bare `Line`s returned by `draw_wire()`
   (`electrical/layout/layout.py:64`) and extended directly into
   `Circuit.elements` (`electrical/builder_phases.py:605`). The naive
   walk recursed into every `Group`/`Symbol` and collected all `Line`s
   indiscriminately, so every diagonal IEC glyph looked like a crooked
   wire. Fix: `lint_elements` now only treats a `Line` as a wire if it is
   not nested inside a `Symbol`; `Text` is still collected everywhere
   (a tag/pin-number label can legitimately crowd a wire).
2. **Rotated text bounding boxes computed as if unrotated.** Wire labels
   (`"BR 2.5"`, etc.) render as `<text transform="rotate(90.0, ...)">` --
   rotated 90 deg to run parallel to the vertical wire they label, offset a
   few mm to the side. `Text.rotation` exists on the dataclass
   (`core/primitives.py`) but the first version of `estimate_text_bbox`
   never read it, so every rotated label's bbox was computed as if it were
   horizontal text sitting on top of the wire -- a guaranteed "collision"
   for every wire label in the diagram, which is the *opposite* of a
   defect (that offset-and-rotate placement is exactly how Schematika
   avoids the collision). Fix: `estimate_text_bbox` now rotates the
   unrotated box's four corners about the anchor point and takes the
   enclosing axis-aligned box. Notably, Schematika's own
   `core/bbox.py::_collect_points` has the same gap ("Text extent is not
   computed; use the anchor position only") and also ignores rotation --
   this isn't a schematika bug (nothing there currently needs text extent),
   but it means a real `validation.py` built on this idea cannot lean on
   existing bbox code as-is.

### Second pass, after fixing both: clean on the model, still dirty via SVG text

After the fix, `lint_elements` on both real circuits (DOL starter, 2-pole
SPDT with relative "above"/"below" placement) returned **0 findings** --
a genuine clean pass, not a silent failure (`test_synthetic_defects.py`
independently confirms all four checks still fire on hand-built defects:
a 16.7-degree tilted line, a label centered on a wire, a 0.2mm alignment
miss, a 4-segment staircase between two points a single L-bend would join).

`lint_svg_text` on the *same* rendered SVGs still reported 12 + 3 = 15 and
2 findings respectively, because the flattened SVG has lost the
symbol-vs-wire structural distinction entirely -- a `<line>` tag from a
breaker's isolator blade is indistinguishable from a `<line>` tag from a
real wire once serialized. This is the clearest evidence from the spike for
linting the pre-render model over the rendered SVG: the fix for false
positive #1 is only expressible with access to `Circuit.elements`'
`Symbol`/`Group` structure. The SVG-text path fixed false positive #2 fine
(the regex was extended to read the `transform="rotate(...)"` attribute),
but has no path to fixing #1 short of re-deriving which lines belong to
symbols by geometric proximity heuristics -- fragile, and just re-invents
the structure the pre-render model already has for free.

### Caveats on what "clean" means here

- Two examples is a small sample, both hand-authored by a careful human
  (they're the repo's own teaching examples). They are not evidence the
  checks would stay quiet on a much bigger auto-placed layout with many
  more wire crossings -- which is the actual target use case
  (`grid-astar-router`/`elk-bridge` output, not curated examples).
  `check_redundant_jogs` in particular has no obstacle model: it can only
  flag ">1 turn" as a *candidate*, never confirm a jog was unnecessary,
  and `_chain_wires`' connectivity heuristic (segments touching
  end-to-end) will merrily chain two unrelated wires that happen to meet,
  a real false-positive source not exercised by either test circuit here
  (neither has two independent wires meeting collinearly at a shared
  point).
- `check_text_wire_collisions` still relies on an *estimated* text bbox
  (`AVG_CHAR_WIDTH_EM = 0.52`, a Times-New-Roman-ish heuristic) since
  neither Schematika nor this prototype computes exact glyph metrics.
  A borderline case (label barely clearing a wire) could go either way
  depending on how good that constant is for the actual rendered font --
  untested here since neither example circuit produced a near-miss case.
- Only `Line` and `Text` are checked. `Circle`, `Path`, `Polygon` (used by
  motor symbols, arcs, PCB footprints) are out of scope for this
  prototype; a production version would need at least `Path` if pid/pcb
  wiring ever uses curved connectors instead of straight `Line` segments
  (a quick grep of `pid/connections.py` shows it does use `Line`, so this
  likely generalizes there without change, but that wasn't verified against
  a running P&ID circuit in this spike).

## Dependency trade-off: shapely vs. stdlib

Tried both. `shapely==2.1.2` has a working `cp314-win_amd64` wheel (`uv run
--with shapely --python 3.14` resolved and imported cleanly); an exact pin
via inline PEP 723 script metadata (`uv run --script`) also worked once
pinned to a version with a prebuilt wheel -- `shapely==2.0.7` failed because
it has no Python-3.14 Windows wheel and fell back to an sdist build that
needs a Visual C++ compiler this machine doesn't have. That's a real
practical constraint for a 3.14-only repo: **pin to a shapely release
confirmed to ship a wheel for the target Python, don't just take "latest".**

Where shapely helps: `check_text_wire_collisions`. The stdlib version
(`linter.py::_segment_intersects_rect`) is a ~35-line hand-rolled
Cohen-Sutherland line-clipping algorithm plus a separate ~15-line manual
corner-rotation step in `estimate_text_bbox`. The shapely equivalent
(`shapely_compare.py`) is `rotate(box(...), deg, origin=...)` plus
`line.intersects(text_box)` -- and it generalizes for free to shapes this
prototype doesn't handle (non-rectangular label boxes, `Polygon`-vs-`Polygon`
symbol-body overlap, buffered arcs for `Path` curves).

Where it doesn't help: `check_orthogonal`. Shapely has no "angle of a
LineString" primitive; `shapely_compare.py::is_orthogonal` is the identical
`atan2` calculation `linter.py::check_orthogonal` already does. Near-alignment
and redundant-jog detection are graph/tolerance logic over point pairs, not
geometric-predicate problems shapely's C (GEOS) core was built to answer
quickly -- stdlib is equally simple there.

**Verdict on the dependency:** for *this* linter's scope (rectangles vs.
line segments, no polygons yet), stdlib wins on simplicity -- it's ~130
lines of geometry code total and CLAUDE.md's zero-runtime-deps philosophy
extends culturally even to a non-`core` module. If a future `validation.py`
grows to include symbol-body overlap (`Polygon`-vs-`Polygon`), P&ID pipe/arc
routing (curved `Path`), or PCB footprint clearance checks, shapely's payoff
crosses over quickly and is worth revisiting then -- it would only ever be a
dependency of that one validation module, never of `core` (matching
`docs/ARCHITECTURE.md`'s "none" deps column for `core`, and mirroring how
`pcb`'s optional deps -- `skidl`, `pillow` -- are already scoped to one
consuming module rather than pulled into every import of `schematika`).

## Integration effort as a `validation.py`-style module

`docs/ARCHITECTURE.md`'s file-role convention already names `validation.py`
as a domain package's "post-build consistency checks (overlap, boundary,
label mismatch)" file, alongside `model.py`/`builder.py`/`renderer.py`. This
prototype fits that slot directly:

- Input: `BuildResult.circuit.elements` (electrical) or the equivalent
  `*BuildResult` field for `pid`/`pcb` -- no new data needed, this is the
  same tree `render_system`/`render_to_svg` already consumes. No `core`
  changes required; `core/exceptions.py`'s `CircuitValidationError` family
  is the natural type for `error`-severity findings if a real
  `validation.py` chooses to raise rather than return a report (this
  prototype returns a report, matching the "post-build check" framing
  rather than a build-blocking validator).
- The `Symbol`-vs-top-level-`Line` distinction and the `Text.rotation`
  handling this spike had to add are not currently exposed by
  `core/bbox.py` and would need to land there (or a shared
  `core/text_metrics.py`) so `electrical`, `pid`, and `pcb` don't each
  reinvent them -- this is the one piece of real design work, not just
  wiring.
- Effort estimate: small. The four checks are ~250 lines total including
  docstrings; the real cost is the char-width/font-metric calibration and
  deciding severity thresholds (`angle_tol_deg`, `align_tolerance`) against
  actual print-scale output, which needs a few real full-cabinet drawings
  to tune, not just the two examples used here.

## Sketch: findings as an optimization objective

`LintReport.cost` already reduces every finding to one float via
`sum(finding.weight for finding in findings)`, with each check assigning
its own weight scale (angular deviation in degrees, a fixed per-collision
penalty, closeness to "should have been exact," turns beyond the Manhattan
baseline). That is directly usable as the objective for a nudge/refinement
loop, independent of which placement engine (`elk-bridge`,
`grid-astar-router`, ...) produced the layout being scored:

```
score = geometry_linter.lint_elements(circuit.elements).cost
# optimizer loop: propose a small perturbation (move a symbol, reroute
# a wire), re-lint, keep the perturbation iff score decreases
```

Two properties make this workable as an objective rather than just a gate:

- It is a pure function of geometry with no rendering/rasterization step,
  so it is cheap enough to call once per candidate move in a local-search
  or simulated-annealing refinement loop (the `README.md` scope note that
  "a layout pass taking minutes is acceptable" means even a
  not-fully-optimized `O(n^2)` near-alignment scan across hundreds of
  points, as `check_near_alignment` currently is, is not disqualifying).
- The weight scales are already comparable in kind (all "how far from
  correct," none arbitrary), though not yet calibrated against each other
  -- e.g. is one non-orthogonal wire worse than one text collision? This
  spike picked illustrative constants (5.0 per collision, raw degrees for
  tilt, turns-minus-one for jogs); a real optimizer would need those
  weights tuned against what actually looks bad, which is exactly the kind
  of thing `vlm-critic` (vision-LLM aesthetic review) could calibrate
  against once, rather than being the per-iteration cost itself -- cheap
  deterministic score for the search loop, occasional vision-LLM check to
  validate the score still tracks human judgment.

This does not need to wait for one placement engine to "win" among the
other tracks: any engine's output is just a `Circuit`/`elements` list, and
`lint_elements` doesn't care how it got produced.

## Pros / cons

**Pros**

- Deterministic, fast, no model calls -- fits the repo's "no runtime deps
  beyond `deal`" culture even as a research direction.
- Catches real classes of defect with test-proven true positives
  (`test_synthetic_defects.py`), not just plausible-sounding checks.
- Doubles as both a gate (pass/fail, or `--strict` like
  `scripts/api_style_gate.py`) and a scalar objective for any future
  layout optimizer, with no extra work beyond summing weights.
- Works from the pre-render model with no new instrumentation --
  `Circuit.elements` already exists and is already consumed by
  `render_system`.

**Cons**

- Naive implementations produce confident, plausible-looking false
  positives (100% false-positive rate on this spike's first pass) that
  require Schematika-internals knowledge to diagnose, not just
  SVG-reading -- a maintenance burden if the render internals
  (`draw_wire`, symbol factories, wire-label placement) change shape
  without someone updating the linter's assumptions about them in lockstep.
- Small validation sample (2 examples): "0 findings" here is encouraging,
  not proof the checks are well-calibrated on messy auto-generated
  layouts, which is the actual target.
- `check_redundant_jogs` has no obstacle model and a naive endpoint-chaining
  heuristic -- its findings are explicitly `info`-severity "candidates,"
  weakest of the four checks.
- Text-collision accuracy is bounded by an estimated, uncalibrated
  character-width constant, not real font metrics.

## Verdict

**Pursue with caveats.** The core idea holds up: geometry-based linting is
cheap, catches real defects when it isn't tripping over its own false
positives, and the same findings list is a free scalar objective for
whichever layout engine wins the other tracks. The caveat is that "just
parse the SVG" is the wrong framing -- the two false positives found here
both needed Schematika-internals knowledge (`Symbol` vs. top-level `Line`,
`Text.rotation`) that only the pre-render model exposes, so any real
implementation should be a `validation.py` module inside `electrical`/`pid`/
`pcb` (per `ARCHITECTURE.md`'s existing file-role convention), not a
standalone SVG post-processor. Before this becomes production code: run it
against a much larger and messier auto-placed layout (once
`grid-astar-router` or `elk-bridge` produce one) to see whether
`check_redundant_jogs`' chaining heuristic and the text-width estimate hold
up outside two curated examples.
