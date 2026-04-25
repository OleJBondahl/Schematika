# Vision and Scope

## Why this exists

R&D needs a single view of the entire electrical system to reason about
it. Production drawings are intentionally fragmented (each shop floor
sees only its slice). The Overview module fills that gap by
auto-generating a system-wide diagram from the same source data the
production drawings use.

## Principles (locked in)

1. **Auto-generation only.** No manual layout. Light hints (port
   ordering, signal-kind classification) are OK; per-diagram positioning
   is not. Regenerates cleanly on every source-data change.
2. **Complement, don't replace, production drawings.** R&D context only.
3. **Readability over prettiness.** Engineer-readable beats aesthetically
   polished.
4. **Wire-level detail, not bundle-level.** Every individual signal wire
   is shown. Cable bundling is the wrong abstraction here — collapsing
   wires into bundles removes the information R&D needs.
5. **Nested containment is required.** Cabinet → PCB → sub-PCB. The
   visualization must show this with wires crossing container
   boundaries.

## In scope (v0)

- Reads a `Project` after `project.build_circuits()` has run.
- Accepts a containment dict declared by the consumer at the top of
  their build script.
- Emits a single SVG via Graphviz (`dot` engine, `splines="ortho"`).
- Color-codes edges by signal kind. v0 ships with two kinds —
  **`power`** and **`signal`** — and the palette grows on demand. See
  [`07-open-questions.md`](07-open-questions.md) for the resolved
  decision.
- HTML-table node labels with named ports for pin-level edge
  attachment. Confirmed by user.

## Out of scope (v0)

- **No HTML hyperlinks** in the output SVG. No `URL=` / `HREF=` /
  `target=` on nodes, edges, or cells. Pure-SVG output is fine;
  click-through to production drawings is deferred.
- **No replacement of `src/block_diagram.py` in `auxillary_cabinet_v3`.**
  That file is a throwaway trial, not a target to subsume.
- **No use of `schematika.block`.** The block module is a trial, not
  in production, and not part of the Overview data flow. Ignore it
  entirely.
- **No layered views** (power-only, CAN-only). Ship the unified view
  first.
- **No interactive filtering.** Defer until the base view is validated.
- **No physically-accurate port placement** (connectors on the side of
  the box they're really on). Graphviz fundamentally can't do this. If
  R&D demands it after seeing v0, that's the trigger to migrate to ELK,
  not before.
- **No new repo-per-domain pattern.** Going forward each system is one
  repo with cabinet + PCBs + cables in it. We do not plan to support
  multi-repo composition.

## Definition of done (v0)

- Single Python module (`src/schematika/overview/`) that consumes a
  built `Project` and a containment dict, emits `system.svg`.
- All individual signal wires shown as separate edges, color-coded by
  kind (`power` / `signal`).
- Containment renders correctly on `auxillary_cabinet_v3` (one
  cabinet, no nesting) and on a synthetic
  cabinet-containing-PCB-containing-sub-PCB fixture. The synthetic
  fixture is the only nested-containment exercise at v0 — see
  `07-open-questions.md` "v0 testing honesty."
- Validator (`scripts/system_diagram_review.py`) runs SVG-level
  structural checks and exits non-zero on regressions.
- Import-linter contract added: nothing in `core/` or other domain
  packages may import from `overview/`.
- Reviewed against the real consumer use case before extending scope.
