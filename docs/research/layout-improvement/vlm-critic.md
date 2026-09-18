# vlm-critic — feasibility/cost of a VLM-in-the-loop aesthetic critic

**Verdict: defer.** Don't build the automated render→VLM→JSON-nudge→re-render
loop now. Every concrete "visual balance" defect I could actually find by
eye in real Schematika output reduces to a computable geometric statistic
that `svg-geometry-linter` can implement more cheaply, deterministically, and
testably. Cost and latency turned out *not* to be the blocker (both are
comfortably within this project's stated tolerances) — the blocker is that
I couldn't find a defect class a VLM would catch that geometry can't, other
than "the SVG generator itself has a rendering-fidelity bug," which the
project already handles with the ad hoc render→PNG→look workflow documented
in this repo's `CLAUDE.md` ("P&ID visual review loop"). This confirms the
README's working hypothesis for this track.

## What I did

1. Rendered three real, tracked Schematika fixtures (`examples/output/*.svg`)
   to PNG and looked at them: `01_single_relay.svg` (67x150mm, minimal),
   `02_dol_starter.svg` (109x300mm, dense 3-phase motor starter),
   `05_multi_builder.svg` (three independent circuit fragments on one page).
   Artifacts and a rendering-tooling gotcha are in
   `research/layout/vlm-critic/` (see `notes.md` there).
2. Read the seed conversation's VLM-in-the-loop sections in full (pipeline
   architecture, prompt design, model recommendations, ZBook feasibility,
   and its own later pivot to "just analyze the SVG directly").
3. Estimated cost/latency for an API critic loop and for local Qwen2.5-VL on
   the user's HP ZBook.
4. No live paid VLM API calls were made, per the task's cost constraint —
   the visual judgment below is mine (Claude, with vision), used as a proxy
   for "what would a VLM plausibly see," not a live model's output.

## The visual assessment

### `01_single_relay.png` — a 2-node circuit in a tall, mostly-empty column

The rendered page is almost entirely whitespace: one relay coil (`K1`)
between two terminal points (`X1`/`X2`), with the coil symbol occupying a
sliver of the vertical run. This is exactly the "tiny sensor loop forced
into the same column footprint as a dense circuit" problem the seed
conversation raises.

**But this is a geometry problem, not a vision problem.** The information
needed to detect it — "occupied ink area is a small fraction of the page
bounding box" — is already in the SVG's own coordinates. A geometry linter
can compute an *occupancy ratio* (sum of component/wire bounding-box area
divided by page bounding-box area) or a *max-gap-between-elements* metric
directly from the same `shapely` geometry `svg-geometry-linter` is already
building for collision/alignment checks. No pixel rendering required.

### `05_multi_builder.png` — three sibling fragments, visibly unbalanced

Three independent circuit fragments share a page: a short K1-coil fragment
(ends ~40% down the page), a PLC-driven K1 fragment, and a K1-contact
fragment (both run much taller, ending near the bottom). The left column's
bottom edge sits well above the other two, leaving a visibly lopsided block
of empty space under it — a real "this doesn't look balanced" reaction.

**Also a geometry problem.** "Sibling fragments' bounding-box heights vary
by more than N%" or "bottom-edge y-coordinates of sibling columns differ by
more than N mm" is a direct min/max comparison over bounding boxes the
linter already has. It requires knowing which elements are "siblings" (a
grouping/zone concept the placement engine already tracks), not scene
understanding.

### `02_dol_starter.png` — the dense case, for contrast

By contrast, the dense 3-phase starter circuit (fuses → contactor → thermal
overload → motor) reads as reasonably well-proportioned: little wasted
space, consistent column widths. Nothing jumped out as a defect a human
reviewer would flag that isn't also a candidate geometry rule (alignment,
spacing consistency, label collision).

### Where a VLM's information advantage over the linter is real but narrow

The one class of defect that genuinely differs between "read the declared
SVG coordinates" and "look at the rendered pixels": bugs in the *renderer*
itself — e.g. a symbol factory emitting a malformed path that happens not to
trip a coordinate-level overlap check, but which renders as a visibly wrong
shape once stroke width and anti-aliasing are applied, or a font-metric
mismatch that makes a label collide with a wire in the rendered image even
though the linter's estimated text bounding box (via `fontTools`, per the
seed doc) didn't overlap. A VLM looking at the actual PNG could catch this;
a geometry linter working from the same coordinates the renderer used cannot
by construction (garbage in, garbage out on the same data).

This is real, but it's an occasional rendering-QA concern, not a per-page
layout-quality gate. It's already served by this repo's existing informal
loop (`CLAUDE.md`'s "P&ID visual review loop": render → PNG →
`pid_review.py`/Claude looks → fix) — which is cheap, on-demand, and doesn't
need an automated JSON-nudge/re-render loop wrapped around it.

## Cost and latency estimate (API-based critic)

Grounding numbers (Sep 2026 pricing, via web search — not live-verified
against a real call, per the task's cost constraint):

- Gemini 2.5 Flash: **$0.30/M input tokens, $2.50/M output tokens**
  ([Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)).
  Gemini 2.5 Pro is roughly 4x Flash's input/output rate, per the same
  pricing page family — the seed doc recommends Pro/3.5-Flash specifically
  for the higher-res spatial reasoning this task wants.
- A schematic page rendered high-res enough to read tiny pin labels (the
  seed doc's own stated reason to prefer Gemini) tiles into several
  ~258-token image tiles — call it **1,500–2,500 image tokens/page** at the
  resolution this task needs, plus a ~300–800 token component-state JSON
  and ~300 token system prompt, plus a ~200–600 token JSON nudge response.
  **Total: roughly 2,500–4,000 tokens per critic call.**

At Flash rates that's **~$0.001–0.002 per call**; at Pro rates, roughly
**~$0.01–0.02 per call**. With the seed doc's own suggested cap of ~2
refinement iterations per page, and a real multi-page cabinet run (this
project's consumer, `auxillary_cabinet_v3`, generates cabinets with dozens
of pages), a full run lands around **$0.05–$1.20 total** depending on model
tier. That is genuinely cheap — cost is not the objection.

Latency: 2–8s per API call is typical for these model classes; 30 pages x 2
iterations is a few minutes of added wall-clock time. The project's own
README states runtime speed is explicitly not a constraint ("a layout pass
taking minutes is acceptable"), so **latency is not the objection either**.

## Local hardware feasibility (HP ZBook, quantized Qwen2.5-VL)

Per the seed conversation's own numbers: Qwen2.5-VL-7B (Q4_K_M, ~6GB) needs
a discrete GPU with 8GB+ VRAM to hit 30–50 tok/s; without that (integrated
graphics, or a <8GB discrete GPU — common on ZBook trims), it falls back to
CPU/RAM at 2–6 tok/s. A ~300–600 token JSON critique at CPU speed is
1–3 minutes *per call*; across 30 pages x 2 iterations that's 1–3 **hours**,
which blows past even this project's generous latency tolerance. The
smaller 3B model needed for speed on weaker hardware also has materially
worse spatial-grounding/OCR accuracy than 7B/72B or the API models — the
exact capability this task needs most.

I did not confirm this ZBook's actual GPU/VRAM as part of this spike (that
would need to happen before anyone seriously attempts local 7B inference).
Given the API cost estimate above is already close to negligible, verifying
that hardware to chase a *free* local alternative isn't worth the effort:
**local inference is a dead end for this use case** — not because it's
impossible, but because the cheap API option is strictly better on both
cost and quality unless air-gapping is a hard requirement (it isn't stated
as one anywhere in this repo).

## Verdict

**Defer**, not drop entirely, not pursue now:

- Every concrete visual-balance defect I found by eye in real fixtures
  (occupancy/whitespace ratio, sibling-column height imbalance) is a
  geometric statistic `svg-geometry-linter` can compute from data it
  already has — cheaper, deterministic, and unit-testable, unlike a VLM's
  output.
- The VLM pipeline the seed doc describes doesn't replace geometry checks —
  its own design re-validates every proposed nudge with the deterministic
  router/geometry pass anyway ("do not let the LLM rewrite wire routing").
  So it's a slower, costlier, non-deterministic *addition* on top of a
  geometry linter that has to exist regardless, not an alternative to it.
- Cost (~$0.05–$1.20/run) and latency (a few minutes) are not disqualifying
  given this project's stated "minutes are fine" tolerance — so this isn't
  a "too expensive" verdict, it's a "no identified defect class it uniquely
  catches, for a real ongoing dependency/determinism/testability cost" one.
- The one real information advantage (catching renderer-fidelity bugs
  invisible to coordinate-level analysis) is already covered by this repo's
  existing ad hoc visual-review workflow and doesn't justify an automated
  loop.
- Introducing a non-deterministic external API call anywhere near the
  generation pipeline conflicts with this project's SVG snapshot-testing
  approach and its "zero required runtime deps" ethos — even as an opt-in
  side tool, it's an ongoing maintenance cost (API keys, rate limits, flaky
  CI if ever wired into checks) for an unproven benefit.

**What would change my mind:** once `svg-geometry-linter` ships and gets run
against a meaningful volume of real cabinets from `auxillary_cabinet_v3`/
`juicebox`, if a *recurring* category of human-flagged layout complaint
during real review sessions resists formalization as a geometric rule after
a few genuine attempts — e.g., a true page-level "does this read as a
coherent, professionally-drafted sheet" gestalt judgment that isn't just
bounding-box variance — that's the concrete signal to revisit this track.
Until then, extend the geometry linter's rule set; don't add a VLM loop on
top of it speculatively.
