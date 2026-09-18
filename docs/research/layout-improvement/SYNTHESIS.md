# Round 1 Synthesis + Round 2 Selection

All 12 tracks reported back. Verdicts:

| Track | Verdict | One-line reason |
|---|---|---|
| `grid-astar-router` | **Pursue w/ caveats** | Real zone allocator + A* router, output type matches existing renderer exactly, crossing-penalty verified working. Gap: no bridge yet from `CircuitBuilder`/`Harness` connection data to (port,port) pairs. |
| `svg-geometry-linter` | **Pursue w/ caveats** | Model-level linting (pre-render `Circuit.elements`, not rendered SVG) hit 0 false positives on real circuits after two real fixes; synthetic true/false-positive suite proves it isn't silently broken. Only tested on 2 hand-curated circuits so far. |
| `pagination-partitioner` | **Pursue w/ caveats** | Rule-based split (power → control-by-function → terminals) matches drafting convention; found an existing, fully-built, unused off-page-connector symbol (`electrical.symbols.references.ref()`) and that `reuse_tags` already solves the other cross-page case. Two open edge cases: ambiguous-role rungs (e.g. e-stop), shared-bus reused across >2 pages. |
| `pid-layout` | Pursue w/ caveats | Longest-path layered engine works well for equipment placement; branch/lane assignment needs a domain hint, not inferable from topology. `pid` is pre-production, lower urgency. |
| `elk-bridge` | Pursue w/ caveats, **not for `electrical`** | Full pipeline runs end-to-end via Node subprocess; no IEC-ladder awareness so wrong fit for `electrical`. Surfaced two real pre-existing bugs (see below). `pid`/`overview` don't need it either (see their own verdicts). |
| `pure-python-graph-layout` | Pursue narrowly | `grandalf`'s Sugiyama ordering eliminates crossings (verified), but is dual GPLv2/EPLv1 — a real license conflict for this MIT project — and no candidate models ports/orthogonal routing anyway. Useful only as an ordering-within-layer technique, not a placement/routing engine. |
| `symbol-standards` | Research complete | Schematika's own constants already out-cite free IEC/ISO/ISA sources. Gap: missing `indicator_light`, `transformer` (tag already reserved), `relief_valve`. Full geometry specs written, ready to implement directly — no further research needed. |
| `vlm-critic` | Defer | Real defects found (whitespace ratio, sibling-height variance) all reduce to bounding-box math the geometry linter already covers. Cost isn't the blocker ($0.05-$1.20/run); redundancy is. Revisit only if some defect category resists becoming a geometric rule. |
| `llm-dsl-pipeline` | Drop new module | Schematika already has a relative-placement API (`PlacementOptions(relative_to=...)` / `EquipmentPlacement`) — grepping every example found **zero** raw `Point()` calls for symbol placement already. A new schemdraw-style cursor DSL tested worse on branching topology (hidden state = new hallucination surface) and would violate `API_STYLE.md`'s verb rules. |
| `constraint-solver` | Drop | Placement rules reduce to a fixed total order; deterministic allocator solves in <0.1ms vs. z3/OR-tools' 100-11,000x slower solve times, plus heavy transitive deps (OR-tools: ~172MB). Revisit only if a real optimization objective without a fixed order appears. |
| `pcb-layout` | Drop | Premise was wrong — `pcb.build()` already has a deterministic, well-tested (44 test files) connector-anchored layout (`walk.py` + `pack_pages`). SKiDL carries zero spatial info; nothing surveyed (KiCad, netlistsvg, force-directed) does better. |
| `overview-shared-engine` | Drop | Premise was wrong — `overview` already does deterministic zone/grid placement (Python) + local-grid packing (JS), not Cytoscape force-directed. Data model (whole devices, draggable, no routing) doesn't transfer to `electrical`'s exact-mm/orthogonal-routing needs; tested and confirmed a generic layered layout inverts the power-flow convention. |

## Cross-cutting bugs found (independent of any layout decision)

Found incidentally while building prototypes — worth fixing regardless of which layout direction proceeds:

1. **`BuildResult.wire_connections` logs semantic pin names** (e.g. `"L1"`/`"T1"`) that are **not** `Symbol.ports` dict keys (always positional `"1".."N"`) — found by `elk-bridge`, confirmed via `contactor()`'s own doctest.
2. **`motor`'s port-count fallback assumes `poles*2=6`** but it only exposes 4 real ports — 3 of 15 wire_connections in the elk-bridge test circuit referenced nonexistent `M1.5`/`M1.6` — found by `elk-bridge`.
3. **`scripts/pid_review.py`'s Playwright fallback hardcodes an A3-landscape viewport**, silently cropping tall electrical-ladder SVGs instead of erroring — found by `vlm-critic`.
4. **`pid`'s `pipe_tee`/junction primitive is defined but never wired into `PIDBuilder.pipe()`** — two pipes converging on the same point render as exactly-coincident lines instead of a junction — found by `pid-layout`, caught by `validate_pid`'s duplicate-line check.
5. **`manhattan_route` has no obstacle avoidance** — a recycle pipe crossed instrument bounding boxes in both manual and auto-generated P&ID layouts — found by `pid-layout`.
6. **`StandardTags.TRANSFORMER = "T"` is reserved but has no backing symbol factory** — found by `symbol-standards`.

The recommended fix for (1)+(2) — a real `(tag, pin) -> Port` resolver on `BuildResult` — is a prerequisite for `grid-astar-router`'s round-2 deep dive below, since its topology-to-router bridge needs correct port resolution to work on real (not hand-authored) connection data.

## Round 2: three directions selected for deeper investigation

Selected for the combination of **strongest evidence in round 1** and **real production impact** (`electrical` is what actually ships to consumers via `auxillary_cabinet_v3`; `pid` does not yet):

1. **`grid-astar-router`** — the core placement + orthogonal-routing engine for `electrical` cabinets.
2. **`svg-geometry-linter`** — cross-cutting geometric QA gate / optimization objective, needed regardless of which placement engine ships.
3. **`pagination-partitioner`** — automatic multi-page splitting, directly answering the original ask ("I would prefer the engine to also split the entire system into pages").

Together these three form the natural full pipeline for a real cabinet: **partition into pages → place & route each page → geometry-lint the result.** Round 2 deepens each independently (larger, more realistic test circuits; the specific gaps each track's own doc flagged) and each agent is aware of the other two so the deliverables stay integration-compatible, without blocking on each other's completion.

Not selected for round 2: `elk-bridge` (explicitly wrong fit for `electrical`, no clear consumer among the remaining candidates), `pid-layout` (pre-production module), `pure-python-graph-layout` (narrow technique, licensing blocker), `symbol-standards` (research already complete — implementing the 3 missing symbols is a follow-up task, not more research).
