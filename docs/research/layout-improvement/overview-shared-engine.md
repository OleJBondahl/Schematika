# Track: overview-shared-engine

Question: could the layout engine that wins for `electrical`/`pcb` fixed-page
schematics also generate the `overview` module's node positions, or is
`overview` a fundamentally different problem?

## 1. What the overview module actually does today (correcting a wrong premise)

The track brief in `README.md` assumes `overview` "delegates positioning
entirely to Cytoscape.js's client-side layout algorithms (cose/dagre/
breadthfirst)". **That's not what the code does.**

- `src/schematika/overview/assets/app.js:348` calls Cytoscape with
  `layout: { name: "preset" }` — the one Cytoscape layout mode that does
  *nothing*: it renders nodes at whatever `position` was already set on them.
  There is no `cose`, `dagre`, or `fcose` anywhere in `app.js` or
  `assets/cytoscape.min.js`'s call sites.
- `src/schematika/overview/layout.py` (`compute_device_positions`) is a
  **deterministic zone/grid engine already written in Python**: it buckets
  `DeviceNode`s into columns by device-class family
  (`_INTERNAL_ORDER = ("PLC", "G", "PSU", "U", "K", "FT", "F", "Q", "CT")`,
  then `"X"` terminal blocks, then `"FIELD"`), and packs rows within each
  column (`_place_uniform`/`_place_terminals`/`_place_field`).
- `app.js:73-201` then does a **second, JS-side deterministic layout pass**:
  for each device it lays out its child connectors/pins on a fixed local grid,
  ordering connectors left-to-right by the mean direction of the external
  devices they wire to (`preferredDir`), so pins visually point toward their
  wiring partners. This is not force-directed either — it's a hand-rolled
  directional-affinity packing.
- Cytoscape's only jobs are: render, hit-test, pan/zoom, drag (after the
  preset layout places everything), and expand/collapse of compound nodes.

So the real comparison is not "fixed-page engine vs. force-directed graph" —
it's "fixed-page engine vs. an **already-existing**, independently-invented,
Python-side zone/grid engine that looks structurally similar to what
`grid-astar-router` is prototyping for `electrical` (zone → column → pack)."

## 2. Data model comparison

| | `overview` | `electrical` |
|---|---|---|
| Node granularity | Whole devices (`DeviceNode`), with nested connector/relay/fuse/pin child nodes for local layout only | Individual `Symbol`s with typed `Port`s at exact mm coordinates |
| Position units | Arbitrary pixels (`_COL_GAP = 760`, `_ROW_GAP = 640`) — no relationship to real-world scale | Millimetres, tied to IEC 60617 grid pitch and symbol footprints |
| Edge representation | Abstract pin-to-pin `Edge`/aggregated `MetaEdge` (bundle between two devices); rendered as straight/bezier Cytoscape edges, no routing | `Line` primitives requiring orthogonal routing, port-direction alignment (`draw_wire`'s `_PORT_DIRECTION_TOLERANCE`, X-alignment matching) |
| Precision requirement | None — connectivity + rough proximity is enough; overlap is acceptable since users pan/zoom | Strict — misaligned ports or crossing wires are defects on a printed page |
| Post-layout mutability | User drags nodes live in the browser; layout is a one-time seed, not the final word | Fixed once rendered to SVG/PDF; there's no "drag to fix" step |
| Zone/ordering source of truth | Consumer's cabinet-tag naming convention (string prefix/suffix rules: `PLC`, `X`, `-CX` location suffix) | Symbol semantics + explicit domain placement rules (fuses above relays, terminals at bottom rail) |

`overview`'s `Pin`/`ConnectorNode`/`RelayNode`/`FuseNode` do exist at
sub-device granularity, but they're **only ever positioned client-side in
JS**, purely for visual grouping inside an expanded device — they never
carry real geometry, never get routed, and aren't part of the Python
`Layout` seam at all. The Python-side layout contract
(`Layout = Callable[[OverviewGraph], OverviewGraph]`, `overview/layout.py:18`)
only ever touches `DeviceNode.x/y`.

## 3. Prototype: generic layered layout vs. the existing zone engine

`research/layout/overview-shared-engine/compare_layouts.py` builds a
synthetic-but-representative cabinet graph (PLC, PSU, two relays, a breaker,
one terminal block, four field devices in two physical locations) through
the real `schematika.overview.model.build_graph`, then runs it through:

1. The existing `compute_device_positions` (domain zone engine).
2. A from-scratch generic layered layout (BFS rank-from-highest-degree-node +
   one barycenter ordering sweep — the same *shape* of algorithm an
   ELK-layered or hand-rolled Sugiyama engine would produce for `electrical`).

Actual output (`research/layout/overview-shared-engine/comparison_output.txt`):

```
Domain zone engine:
  col x=0:    ['PLC1']
  col x=760:  ['PSU1']
  col x=1520: ['K1', 'K2']
  col x=2280: ['Q1']
  col x=3040: ['X1']
  col x=3800: ['FIELD1-CX', 'FIELD2-CX', 'FIELD3-CY', 'FIELD4-CY']

Generic layered engine:
  col x=0:    ['X1']
  col x=760:  ['FIELD1-CX', 'FIELD2-CX', 'FIELD3-CY', 'FIELD4-CY', 'K2', 'Q1']
  col x=1520: ['K1', 'PLC1']
  col x=2280: ['PSU1']
```

The generic engine picks its root by raw degree, so the terminal block `X1`
(the highest-degree node, since every field wire and downstream device
passes through it) becomes column 0, and `PSU1` — the actual power source —
lands at the far right, inverting the power-flow-left-to-right convention
the zone engine encodes on purpose via `_INTERNAL_ORDER`. It also collapses
`K2`/`Q1`/all four `FIELD` devices into a single rank, because "hop count
from the highest-degree node" can't see that `FIELD1-CX`/`FIELD2-CX` and
`FIELD3-CY`/`FIELD4-CY` are different physical panel locations that should
group separately — that grouping comes from parsing a `-CX`/`-CY` suffix off
the device id (`overview/layout.py:_location`), a naming convention, not a
graph fact.

This mirrors exactly the kind of domain rule `electrical`/`pcb` layout
tracks are grappling with (fuses above relays, terminals at the bottom rail):
**no generic graph-layering algorithm — BFS ranking, ELK layered, Sugiyama —
can recover cabinet-engineering conventions from connectivity alone.** Both
domains need a hand-written zone-assignment/ordering rule; only the packing
*within* a zone is generic.

## 4. Would a shared abstraction be worth building?

A `schematika.layout` package with a common `GraphModel -> Positions`
interface is technically pluggable — `overview` already exposes exactly this
seam (`Layout` in `overview/layout.py:18`, threaded through
`render_overview(..., layout=...)`). But sharing the *engine underneath* the
seam buys little, because the two consumers disagree on the load-bearing
part of "layout":

- **What must be shared for it to be worth it:** the domain zone-assignment
  logic (which is hand-written and cabinet-specific either way) and the
  precision/routing requirements (mm-exact ports vs. arbitrary pixels) are
  incompatible. A shared engine would have to support both "give me exact
  orthogonal port-aligned coordinates for print" and "give me rough
  proximity for an interactive canvas the user will drag anyway" — two very
  different contracts wearing one interface.
- **What actually could be shared, and is small:** a generic "assign nodes to
  ranked bands via a caller-supplied classifier function, then pack each band
  with a caller-supplied ordering key" utility (~30-40 lines — literally what
  `compute_device_positions`'s `_place_uniform`/`_place_terminals`/
  `_place_field` already do, generalized). If `grid-astar-router` or another
  winning `electrical` engine ends up wanting a "zone → column, pack rows"
  primitive too, it could reuse that packer. But this is a small shared
  *utility function*, not a shared *engine*, and the zone-assignment rule
  (the actual hard, valuable part) stays domain-specific in both places.
- The `pagination-partitioner` track (splitting a system into pages: power
  domains, functional blocks, terminal strips) is a closer conceptual sibling
  to `overview`'s zone engine than any fixed-page symbol-placement engine is
  — both are about *grouping/ordering domain objects into bands*, not about
  routing wires between exact port coordinates.

## Verdict: **drop** (no shared *engine*; a small shared *utility* is optional, low-priority)

- `overview`'s layout is not delegated to a force-directed/client-side
  algorithm — it's already a bespoke, working, deterministic zone/grid
  engine, conceptually adjacent to (not needing) whatever wins for
  `electrical`/`pcb`.
- The two domains fundamentally disagree on precision (mm-exact orthogonal
  ports vs. arbitrary interactive-canvas pixels) and on what "done" means
  (final printed artifact vs. one-time seed for a user-draggable graph).
- The prototype confirms that a generic graph-layering algorithm — the kind
  `elk-bridge`/`pure-python-graph-layout`/`grid-astar-router` are evaluating
  — cannot recover `overview`'s domain zone/grouping rules from connectivity
  alone, so pointing a shared "winning" engine at `overview`'s graph would
  either need `overview`'s exact domain rule re-implemented inside it (no
  savings) or would produce worse layouts than what exists today (as shown
  above).
- If a track produces a generic "rank into bands, pack within band" helper
  as a byproduct, it's fine for `overview/layout.py` to import it later —
  but that's an opportunistic code-reuse note, not a reason to build a
  unifying `schematika.layout` package now.
