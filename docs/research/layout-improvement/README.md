# Layout Improvement Research Spike

Branch: `layout-improvment`. This is a **spike**, not a design doc: the goal is
answers and throwaway prototypes, not production code. Nothing here gets wired
into `src/schematika/` during this phase. We clean up and design properly once
we know what's promising.

## Problem

Schematika's `electrical`, `pcb`, and `pid` (still pre-consumer) modules
require a lot of manual `position: Point` placement today. We want a much
more automated layout path — ideally one engine usable across `electrical`
(cabinet schematics with strict IEC 60617 / relay-ladder conventions),
`pcb` (SKiDL-sourced schematic review, not board layout), `pid` (ISO 14617 /
ISA 5.1 process diagrams), and `overview` (the existing Cytoscape-based
interactive graph) — while accepting that a single engine may not fit all
four, in which case a couple of specialized engines is fine.

Runtime speed is not a constraint: diagrams are generated locally and rarely,
so a layout pass taking minutes is acceptable. Visual quality and minimal
manual placement are what matter.

Context: `../../Optimizing Code-Generated Electrical Schematic Layouts.md`
(repo root) is a prior research conversation with Gemini. It's a reasonable
starting point but it has no knowledge of this codebase's actual data model
(frozen dataclasses, `core` is I/O-free, `catalog`/`electrical`/`pid`/`pcb`
layering, `Point`/port conventions) — every track here must ground its
prototype in the real code, not just repeat Gemini's generic advice.

Read first, for repo grounding: `docs/ARCHITECTURE.md`, `docs/API_STYLE.md`,
`CLAUDE.md`.

## Tracks

Each track gets its own git branch (`layout-improvment/<track>`) and worktree,
its own findings doc at `docs/research/layout-improvement/<track>.md`, and
(where applicable) a runnable prototype under `research/layout/<track>/`.

| Track | Question |
|---|---|
| `elk-bridge` | Can we drive Eclipse Layout Kernel (elkjs) from Python (subprocess/Node bridge) for port-aware orthogonal layout of `electrical` graphs, without adding a permanent second language to the *runtime* dependency graph? |
| `grid-astar-router` | A pure-Python deterministic zone/grid placement engine (power rail → protection → control → coils → terminals) plus an orthogonal A* wire router with turn/crossing penalties, grounded in Schematika's real symbol/port model. |
| `svg-geometry-linter` | A shapely-based geometric linter that scores/validates *any* generated layout (crooked wires, label/wire collisions, misaligned pins, redundant jogs) — useful as a quality gate or optimization objective regardless of which placement engine wins. |
| `constraint-solver` | Can z3-solver or OR-tools CP-SAT express cabinet placement rules (fuses above relays, terminals pinned to bottom rail, no overlap) and solve them fast enough to be worth the dependency? |
| `pcb-layout` | What layout options exist specifically for SKiDL-sourced schematic review diagrams (not board/copper layout) — can it share an engine with `electrical`, or does it need its own? |
| `symbol-standards` | What are the authoritative geometric definitions for IEC 60617 / ISO 14617 / ISA 5.1 symbol proportions and grid conventions, and what symbols is this library clearly missing? |
| `vlm-critic` | Feasibility/cost of a vision-LLM-in-the-loop aesthetic review pass (render → critique → nudge → re-render). Expected to rank below `svg-geometry-linter` since geometry analysis is deterministic and cheap — confirm or refute that. |
| `pagination-partitioner` | A rule-based partitioner that splits a full system into pages (power domains, functional blocks, terminal strips) with off-page connectors/cross-references, for both `electrical` cabinets and the `overview` module. |
| `pure-python-graph-layout` | Survey of pure-Python layered/Sugiyama graph layout (e.g. `grandalf`, `networkx` layouts, hand-rolled Sugiyama) as an ELK alternative that avoids a JVM/Node dependency entirely. |
| `pid-layout` | P&ID-specific layout conventions (equipment placement, pipe routing, instrument bubble stubs) distinct from `electrical`'s ladder conventions — does it need its own engine? |
| `overview-shared-engine` | Can the `overview` module's Cytoscape-based interactive layout share an abstraction with whatever wins for `electrical`/`pcb`/`pid`, or is it fundamentally a different problem (interactive graph vs. fixed-page schematic)? |
| `llm-dsl-pipeline` | Using an LLM to translate a circuit/netlist description into a *declarative placement script* using Schematika's own symbol classes (not generic schemdraw symbols) — code Schematika already knows how to render, reviewed/regenerated rather than hand-tweaked. |

## Deliverable per track

1. Read the relevant Schematika source (list depends on track; at minimum
   `docs/ARCHITECTURE.md`, `docs/API_STYLE.md`, and the domain package(s) the
   track touches).
2. Research external prior art (WebSearch/WebFetch as needed).
3. Build a minimal *runnable* prototype against a real or synthetic
   Schematika circuit, where applicable — under `research/layout/<track>/`.
4. Write findings to `docs/research/layout-improvement/<track>.md`: what it
   does, integration effort, fit with Schematika's invariants (frozen
   dataclasses, I/O-free `core`, one-way layer dependencies, zero *required*
   runtime deps in core), pros/cons, and a verdict (pursue / pursue with
   caveats / drop) with reasoning.
5. Commit to the track's own branch. Do not merge, do not touch
   `src/schematika/` production code, do not touch other tracks' files.
