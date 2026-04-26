# Feedback Loop for AI Iteration

How an AI agent iterates on Overview output without a human in the loop
on every cycle. Pattern modeled on the existing
`scripts/pid_review.py`.

## What "good" means — operationalized

| Property | SVG-parse | Raster | Human |
|---|---|---|---|
| Edge stroke color in palette per kind | yes | | |
| Edge count == input wire count | yes | | |
| Node count == leaf-unit count; cluster count == container count | yes | | |
| Cluster bbox contains its children's bboxes | yes | | |
| Ortho routing actually used (path segments H/V only) | yes | | |
| `<text>` bboxes don't overlap | yes | | |
| Page size bounded | yes | | |
| Title round-trip (every node/edge title parses back to input) | yes | | |
| Labels readable at target render size | | yes | |
| Crowding feels too dense | | partial | mostly |
| Color-coding is intuitive | | | yes |
| Layout tells the right story | | | yes |

~70% SVG-parseable, ~20% raster, ~10% subjective. The goal is to push
as much as possible into Tier 1.

## Tier 1: SVG-level checks (cheap, deterministic)

Stdlib `xml.etree.ElementTree` is enough — no new deps. Reuse
`core/validation.py:ValidationResult` (`passed`, `warnings`, `errors`)
and helpers like `boxes_overlap()` and `check_text_overlap()` rather
than redefining them — the P&ID validator already uses them.

Concrete checks for v0:

1. **Palette.** Every `<g class="edge"> path/@stroke` is in the allowed
   palette set (read from the emitter's sidecar).
2. **Counts.** Node, edge, and cluster counts in the rendered SVG
   match the **emitter's sidecar** — see "source of truth" below.
   Catches "agent deleted nodes to fix overlap."
3. **Cluster containment.** Compute axis-aligned bbox from each child's
   `<polygon>` / `<path>`. Assert child bbox ⊆ cluster bbox + small
   tolerance.
4. **Ortho routing.** For every edge `<path d>`, walk path commands;
   each segment after the initial port stub must be axis-aligned.
   Allow up to two short diagonal stubs at endpoints (documented
   Graphviz behavior).
5. **Text overlap.** For every `<text>`, compute bbox from `x`, `y`,
   `font-size`, estimated glyph width (≈ 0.6 × font-size × len).
   Pairwise-test using `core.validation.boxes_overlap()`; skip pairs
   sharing a parent `<g class="node">` (port labels in the same HTML
   table cell are allowed to abut).
6. **Page size.** Root `<svg>` width/height ≤ configured maximum. Stops
   `dot` from blowing up the canvas to escape overlap pressure.
7. **Title round-trip.** Every node `<title>` parses as a known unit
   id; every edge `<title>` parses as `{src}:{srcport}->{dst}:{dstport}`
   and matches a wire in the input.

Each check is dozens of lines. Total runtime under a second.

### Source of truth for counts

`overview.build()` writes a sidecar `<output>.expected.json` next to
the SVG. The sidecar is **derived from the in-memory `(units, wires)`
model** — that is, the data structure handed to the emitter — not
re-extracted from `project._results`. The validator compares the
rendered SVG to the sidecar:

- If the model and the SVG agree → green.
- If the model and the SVG disagree → SVG is wrong (emitter or
  Graphviz bug); validator flags it, agent investigates.
- If the model and the source data (`project._results`) disagree —
  that's an extractor bug, caught by separate unit tests on the
  extractor, not by this validator.

This makes the SVG-side check non-tautological while keeping the
validator entry point single-input (just the SVG path).

## Tier 2: render-and-look (visual review)

Reuse the SVG→PNG helper from `scripts/pid_review.py`. The exact
function is `svg_to_png(svg_path: str, dpi: int = 300) -> str`
(`scripts/pid_review.py:12`).

- Extract that function into `scripts/_render.py` (shared by both
  reviewers).
- It already tries `cairosvg` first and falls back to Playwright
  Chromium on `ImportError` / `OSError` — the standard pattern on
  Windows where Cairo libs are often missing.
- Render at three scales:
  - **Full-fit** (≈ 1600×1000) — global structure: are clusters nested?
    is the signal-color story coherent?
  - **1:1 at 96 dpi** — label legibility.
  - **Quadrant crops at 2×** — top-left, top-right, bottom-left,
    bottom-right, center — catches local crowding invisible at scale.
- Agent prompt during the visual pass: *"List every label you cannot
  read, every wire you cannot trace from source to destination, every
  cluster whose boundary is unclear. Do not comment on aesthetics."*

## Tier 3: snapshot regression

Two-tier snapshot:

- **Structural** (default): canonicalized JSON-ish summary —
  sorted `(node_id, cluster_path)` list, sorted edge list with
  color/style, cluster tree. Bbox coordinates and font metrics are
  **excluded** because they shift across `dot` patch versions; only
  topological facts go in. This is what makes the snapshot stable
  across patch upgrades.
- **Geometric** (env-flag-gated): full SVG. Includes coordinates;
  fragile across `dot` upgrades. Useful locally for debugging layout
  drift, noisy in CI.

Wire as `tests/unit/test_overview_snapshot.py`. Mirror the existing
`PYTEST_UPDATE_SNAPSHOTS=1` idiom that the rest of Schematika uses.

Render command: always plain `-Tsvg`, never `-Tsvg:cairo`. The Cairo
SVG exporter rearranges the class hierarchy and breaks the
class-name-based parsing the validator depends on.

## Validator output format

`scripts/system_diagram_review.py` prints one line per finding,
summary at the end, agent-parseable:

```
[FAIL ortho]       edge BMU:CAN_H -> X1:1 has 3 diagonal segments
[WARN overlap]     text "VCC" and text "+24V" overlap by 4px
[PASS edge_count]  132/132
[PASS palette]     all edges in {power, signal} palette
```

Exit codes:

- `0` — pass
- `2` — structural fail
- `3` — snapshot diff
- `4` — render error

The agent decides ship vs. tweak vs. restructure off the failing tags,
not the prose.

## End-to-end loop

```
edit code
  └─ uv run python src/overview.py        (writes system.svg in consumer repo)
        └─ uv run python scripts/system_diagram_review.py system.svg
              ├─ structural checks  → exit 2 with "[FAIL ...]" lines
              ├─ rendering          → writes system.png and system.q{tl,tr,bl,br,c}.png
              ├─ snapshot diff      → exit 3, prints unified diff
              └─ on success: exit 0, prints "OK 47 nodes, 132 edges, 5 clusters"
        └─ agent reads each PNG, compares against vision goals
```

## Where AI agents fool themselves

| Failure mode | Structural mitigation |
|---|---|
| "Looks fine" without opening the PNG | Validator prints PNG SHA; agent must quote it |
| Fixates on one label, misses cluster collapse | Cluster-containment check runs first, fails loudly when a cluster has 0 children |
| Deletes nodes to "fix" overlap | Counts match against input; disappearance fails the run |
| Regenerates snapshots blindly | `PYTEST_UPDATE_SNAPSHOTS=1` requires a non-snapshot test also passing; commit message must reference the snapshot |
| Claims success without running validator | Validator never returns 0 if any FAIL line is printed; agent's report template requires quoting validator stdout |
| Tweaks `nodesep`/`ranksep` until canvas explodes | Page-size sanity check bounds the escape valve |

## v0 scope for the validator

Day-one `scripts/system_diagram_review.py`:

1. Palette check.
2. Node / edge / cluster count match against an `.expected.json`
   sidecar written by the emitter.
3. Cluster bbox contains children.
4. Render full-page PNG via shared `_render.svg_to_png()`.
5. Print summary, exit non-zero on any FAIL.

~150 lines, no new deps. Once in CI and used for a week: add ortho
check + structural snapshot. Then crops + text-overlap. Then
vision-model integration as Tier 2 matures.

## Reusing existing infrastructure

- `scripts/pid_review.py:12` `svg_to_png()` → extract to
  `scripts/_render.py`, share.
- `visual-review` skill → applies as-is, reference from
  `system_diagram_review.py` docstring.
- `src/schematika/core/validation.py` already provides
  `ValidationResult`, `boxes_overlap()`, `check_text_overlap()`,
  `collect_elements()`. Use these directly — do not redefine them in
  `overview/validate.py`.
- `src/schematika/pid/validation.py` is the shape to mirror: one
  module-level function per check, each returning a
  `ValidationResult` (or appending to a shared one).

## Tooling

No new deps required for v0:

- `cairosvg`, `playwright` are in
  `[project.optional-dependencies] dev` (`pyproject.toml:33`).
- `pymupdf` is in PEP 735 `[dependency-groups] dev`
  (`pyproject.toml:75`) — installed via `uv sync`, not via
  `--extra dev`.

`graphviz` (Python package) + `dot` (CLI) are the new direct deps when
Overview ships. They land as a separate top-level optional, e.g.
`overview = ["graphviz>=0.20"]`, mirroring how `cable = ["wireviz"]`
and `pcb = ["skidl..."]` are isolated. The `dot` binary remains a
system-level dependency (documented in the overview README, not
auto-installed).
