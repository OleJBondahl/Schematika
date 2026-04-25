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
- Color-codes edges by signal kind (power, CAN, safety, signal — palette
  in [`07-open-questions.md`](07-open-questions.md)).
- HTML-table node labels with named ports for pin-level edge attachment.
  (Confirm with user — see open questions.)

## Out of scope (v0)

- **No HTML hyperlinks** in the output SVG. No `URL=` / `HREF=` /
  `target=` on nodes, edges, or cells. Pure-SVG output is fine;
  click-through to production drawings is deferred.
- **No replacement of `src/block_diagram.py` in `auxillary_cabinet_v3`.**
  That file is a throwaway trial, not a target to subsume.
- **No use of `schematika.block`.** The block module is not in
  production and is not part of the data flow. Ignore it entirely.
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

- Single Python module that consumes a built `Project` and a
  containment dict, emits `system.svg`.
- All individual signal wires shown as separate edges, color-coded by
  kind.
- Nested containment renders correctly (verified on
  `auxillary_cabinet_v3` plus a synthetic PCB-inside-cabinet test
  fixture, since `auxillary_cabinet_v3` has no PCB today).
- Validator (`scripts/system_diagram_review.py`) runs SVG-level
  structural checks and exits non-zero on regressions.
- Reviewed against the consumer use case before extending scope.
