# Pagination partitioner

Track: `pagination-partitioner` (see `docs/research/layout-improvement/README.md`).

**Question:** today, splitting a large electrical cabinet system into pages is
done by hand in user code. Can a rule-based partitioner automatically split a
full system netlist into pages by structural role (power distribution,
control/logic grouped by function, terminal strips), inserting off-page
connectors/cross-references when a net spans pages?

**Verdict: pursue with caveats.** The rule set from the Gemini research
conversation works and produces genuinely sensible pages for the structural
split (power / control-by-function / terminal-strips). It does *not* work
uniformly for cross-page connections: one of the two cross-page mechanisms
Schematika needs (severed-wire arrows) already exists as an unused symbol and
slots in cleanly; the other (component-tag echoes, e.g. a contactor's coil vs.
its main contacts) needs *no new rendering at all* -- it already works today,
on any page, via `reuse_tags`. The partitioner's real job turns out to be
smaller than advertised: decide page membership + build order, not "draw
arrows everywhere a tag repeats." Getting that distinction right needed an
actual rendering pass to surface -- see Finding 3.

## What was built

`research/layout/pagination-partitioner/`:

- `netlist.py` -- abstract rung-level netlist model: `RungSpec` (one
  `CircuitBuilder` chain -- the atomic unit Schematika actually builds and
  pages, per `docs/ARCHITECTURE.md`'s `electrical` row and
  `examples/06_full_cabinet.py`), `ComponentSpec`, and `TagLink` (a
  cross-rung dependency, with an explicit start/end "boundary" distinguishing
  a severed wire from a bare tag echo -- see Finding 3).
- `synthetic_system.py` -- a synthetic cabinet: main incomer, a 24V control
  supply, two motor power branches, two conveyor start/stop+contactor-coil
  function pairs, an e-stop safety chain feeding the main contactor, and two
  field terminal strips. 12 rungs, ~40 components -- large enough that manual
  pagination would be tedious, small enough to read the rendered output by
  eye.
- `partitioner.py` -- `partition_netlist_to_pages()`: buckets rungs by role
  (power / control / terminal), groups control rungs by function, packs whole
  function-groups onto pages up to a rung budget (never splitting a group
  unless it alone exceeds the budget), computes a topological build order
  (tag owners before users), and emits `OffPageMarker` pairs for `TagLink`s
  that (a) cross a page boundary and (b) represent a severed wire.
- `render_pages.py` -- bridges the partition to real Schematika: builds one
  `CircuitBuilder` chain per rung (splicing in `ref()` off-page arrows where
  the partitioner asked for them), registers each rung's `BuildResult` with a
  `Project`, groups them into pages exactly as decided, and calls
  `Project.build()` to produce a real multi-page PDF via the existing Typst
  pipeline.
- `run.py` -- entry point; prints the partition summary and renders.
  `uv run python research/layout/pagination-partitioner/run.py`
- `_svg_to_png.py` -- visual-review helper (browser screenshot sized to the
  SVG's own mm dimensions; `scripts/pid_review.py`'s fixed A3 viewport clips
  the wider power-distribution page).
- `output/synthetic_cabinet.pdf` -- the rendered result (committed).

Scope note: the README also names the `overview` module as a target. This
spike scopes to `electrical` only -- `overview` is a single interactive graph
with no page concept, so "off-page connector" doesn't map onto it the same
way; that overlap belongs to the `overview-shared-engine` track.

## How the automatic split compares to what a human would choose

The rendered pages are genuinely close to what an experienced panel builder
would draw by hand:

- **Page 1 (Power Distribution):** main incomer, 24V control supply, and both
  motor branches, side by side. This is exactly where a human puts them --
  the first sheet, left-to-right by circuit index, matching the "Primary
  Power & Distribution Pages" rule from the source research conversation
  verbatim.
- **Page 2 (Control & Logic -- conveyor_1, conveyor_2):** both conveyors'
  start/stop and contactor-coil rungs, grouped together. A human would very
  plausibly do the same -- two short, related function blocks sharing a
  sheet is normal drafting practice, not a compromise.
- **Page 3 (Control & Logic -- estop):** the e-stop chain alone. Reasonable,
  though see Finding 2 below -- a human might place this differently.
- **Page 4 (Terminal Strips):** X20 and X21 together. Uncontroversial.

Where it diverges from a human's judgment is subtler than "wrong sheet" --
it's *silent arbitrariness* in a spot a human would make a deliberate call
(Finding 1), and one structural case the rule set does not have a rule for at
all (Finding 2).

## Off-page connector design

Two cross-page mechanisms exist in the data, and they need genuinely
different treatment -- this was the single most important thing the
rendering pass (not just reasoning about the rule set on paper) surfaced.

1. **Severed wire** (`TagLink.owner_boundary`/`user_boundary` = `"start"`/
   `"end"`): a terminal/bus sits at the very edge of both rungs' chains and
   the wire has nowhere else to go on either page. Example: the 24V bus
   (`X4`) terminates the control-supply rung on the power page and starts the
   e-stop rung on a control page. **This is what needs an off-page connector
   arrow**, and Schematika already has the exact symbol for it:
   `schematika.electrical.symbols.ref()` (`src/schematika/electrical/symbols/references.py`)
   -- a jump-in/jump-out arrow with a label, ports `"1"`/`"2"`, chains into a
   rung exactly like any other single-port terminus. It is fully implemented,
   tested (doctested), exported from `electrical.symbols.__init__`, and
   **used nowhere in the codebase or examples**. Wiring the partitioner up to
   it required zero changes to Schematika itself -- see the rendered page 1
   (`/3.C1` jump-out) and page 3 (`/1.C1` jump-in) in the PDF.
2. **Tag echo** (`owner_boundary`/`user_boundary` left `None`): a component
   tag is reused mid-chain on a different, fully self-terminated rung --
   a contactor's main contacts on the power page, its coil on a control
   page. **This needs no marker at all.** It's resolved today by
   `BuildOptions(reuse_tags=...)`, the same mechanism
   `examples/06_full_cabinet.py`'s `relay_control()` already uses for a
   same-page coil/contact pair -- the mechanism is completely page-agnostic
   already. The partitioner's only job here is a topological build order
   (owner before user), which `partitioner.py`'s `_topological_build_order`
   provides.

Label format follows the source conversation's convention (`/3.C1`): `/` +
destination page number + a running per-page column counter. It's a page/
column pointer, not a real grid coordinate -- there's no grid engine behind
it (that's `grid-astar-router`'s job).

## Findings

**1. The naive "one tag = one crossing" rule conflates two things that
render very differently, and only rendering the output caught it.** Reasoning
about the rule set on paper ("truncate a net at a page boundary, draw an
arrow") suggested a single mechanism. Building the synthetic system and
actually looking at rendered pages showed that applying an arrow to a
component-tag echo would be wrong: the `ref()` symbol draws a severed wire
with an arrowhead, which misrepresents a contactor coil/contact pair that
is *not* a severed wire -- both rungs are already fully terminated. A correct
partitioner needs the owner/user boundary distinction in `TagLink` (or
equivalent) from the start; a naive implementation that fires an arrow on any
repeated tag would produce misleading drawings.

**2. A genuinely awkward case exists and the rule set has no rule for it.**
The e-stop chain is control logic by role, but its actual job -- gating the
main contactor -- is about power distribution, not about "a function block."
`estop_master_enable`'s only content is `Q1`'s coil, tag-echoing straight
back to the main incomer on page 1. A human drafter would likely draw this
rung immediately next to (or even on) the power page, adjacent to `Q1`'s
contacts, precisely because the coil and its contacts being visually close
is more useful here than grouping it with the rest of "control logic." The
partitioner has no signal for this -- `role` and `function` are static labels
on a `RungSpec`, not something derived from how tightly a rung's tags couple
back to another page. A real implementation needs a heuristic like "if a
rung's only cross-references point to a single other page, weight it toward
that page" (essentially a min-cut/community-detection signal on the tag-link
graph) or a manual override hook (`page: str | None` explicit pin on
`RungSpec`, applied before the automatic rules run). Rule-based grouping
alone can't see this; it needs either better heuristics or an escape hatch.

**3. A single shared bus reused by several pages would over-trigger the
naive arrow rule.** The 24V bus (`X4`) is reused by three control rungs in
the synthetic system, not just one. Only one of those (the e-stop rung) was
wired as a genuine severed-wire `TagLink` for this prototype; the other two
reuse the same terminal id with no `TagLink` at all, and render as a
silently-repeated `X4` terminal symbol -- which is exactly how real terminal
strips work (the terminal itself is the cross-reference; no arrow needed).
This was a deliberate modeling choice made *after* discovering that
`ref()`'s single port can't represent a wire fanning out to N pages anyway
(it's a chain terminus, not a branch point) -- so "one arrow per consumer"
isn't just visually redundant, it's not mechanically renderable with the
existing symbol as a single rung's chain. A production rule needs to
recognize "this crossing point is a physical terminal, already
self-documenting" and skip the arrow -- which the source conversation's rule
text doesn't distinguish from a bare internal signal net.

**4. Column/page-internal layout is explicitly out of scope here, and it
shows.** `render_pages.py`'s per-rung horizontal offset is a flat
per-pole-count constant (`COLUMN_SPACING_1P`/`_3P`), tuned by trial and error
against this one synthetic system until nothing overlapped. It is not a real
placement engine and would need re-tuning for a system with different
component mixes. That's fine for this track's job (page membership), but a
real `Project.partition()` feature would need to hand each page's rungs to
`grid-astar-router`'s placement engine rather than reusing this constant.

## Integration effort as a real `Project` feature

Moderate, and cleanly layered on top of existing `Project` machinery --
nothing here required changing `src/schematika/`:

- `Project` already treats "a page" as a list of circuit keys
  (`Project.page(title, circuit_keys)`) merged via `merge_build_results` at
  build time (`src/schematika/project.py:_render_multi_circuit_pages`). A
  `Project.partition(rungs, tag_links)` entry point could sit directly on top
  of this: run the partitioner, call `add_circuit`/`page` for each computed
  page exactly as `render_pages.py` does here, in place of a user manually
  writing dozens of `project.circuit(...)`/`project.page(...)` calls.
  `add_pcb()` (`project.py:424`) is the closest existing precedent -- it
  already auto-partitions PCB connector blocks across generated pages the
  same shape as this prototype does, just from a different data source.
- The `ref()` symbol needs no changes; it needs a caller. That caller is the
  render bridge, ~40 lines here (`_add_marker` + the start/end splice points
  in `_build_rung`).
- Tag-echo reuse (`reuse_tags`) needs no changes either -- only a topological
  build-order helper, which is generic enough to live in `electrical/` if
  this graduates (it doesn't depend on anything page-specific).
- The real cost is the two findings above: the owner/user boundary
  classification on `TagLink` needs a *good default* (most cross-references
  in a real cabinet are tag echoes, not severed wires -- see Finding 3), and
  the "straddling function" problem (Finding 2) needs either a heuristic or
  a manual override before this is usable on a real, less-curated system.
  Both are solvable, but they are the actual research risk, not the paging
  rules themselves (which are already correct and cheap).

## Pros / cons

**Pros**

- The core partitioning rules (power first, control by function, terminals
  dedicated) match human drafting convention well, cheaply, with no
  new symbol library work.
- The off-page connector rendering primitive already exists in Schematika,
  fully built and tested, just unused. Zero-cost integration for that half.
- Tag-echo cross-references need no new rendering at all -- today's
  `reuse_tags` mechanism is already page-agnostic.
- Rung-granularity partitioning matches Schematika's actual construction
  unit (`CircuitBuilder` chain) exactly -- no impedance mismatch to bridge.

**Cons**

- The rule set alone can't detect the "straddling function" case (Finding 2)
  -- needs either a real graph heuristic (added complexity) or a manual
  override (back to some manual work, just less of it).
- Getting the severed-wire-vs-tag-echo distinction wrong produces misleading
  drawings (arrows implying a broken wire where none exists), and the source
  research conversation's rule text doesn't make this distinction --
  an implementer following it literally would get this wrong without
  building and looking at real output, as this spike did.
- Column placement within a page is not solved here and isn't this track's
  job; a real feature needs `grid-astar-router` (or equivalent) underneath
  it, so "pursue" for this track implies also pursuing that one.

## Reproduction

```bash
cd research/layout/pagination-partitioner
uv run python run.py        # prints the partition summary, writes output/synthetic_cabinet.pdf
uv run python _svg_to_png.py output/<page>.svg   # for visual review of an individual page
```
