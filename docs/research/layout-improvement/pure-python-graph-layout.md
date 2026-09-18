# Pure-Python graph layout: survey + prototype

Track: `pure-python-graph-layout`. Question: are there pure-Python
layered/Sugiyama graph layout libraries mature enough to be Schematika's core
layout engine, or close enough that a thin wrapper gets there, without a
JVM/Node dependency (the explicit alternative to the `elk-bridge` track)?

## Verdict: pursue with caveats — as a node-placement pre-pass only, not a layout engine

No pure-Python library does what Schematika actually needs end-to-end: a
layered layout engine that is also port-aware and produces orthogonal
routing. `grandalf` is real, genuinely pure-Python, and its Sugiyama
crossing-minimization pass works and is worth having. But it only solves
"which layer, which column" for a node's *center point*. It has no concept of
a port, a side, or a wire; everything downstream — attaching wires to the
correct side of a symbol, keeping wires orthogonal, drawing shared bus rails
— is work Schematika still has to do itself, which is squarely
`grid-astar-router`'s job, not a library's. Net effect: `grandalf` could
replace the *column/row assignment* part of a hand-rolled Sugiyama
implementation and save maybe a day of engineering (cycle-breaking + median
heuristic + crossing reduction), at the cost of a GPLv2/EPLv1-dual license
dependency that hasn't been released since January 2023. That trade is
marginal enough that it does not change the overall plan: Schematika still
needs a custom, port-aware placement + orthogonal-routing engine
(`grid-astar-router`'s territory); `grandalf` is at best an optional
internal building block for the "assign columns within a layer" sub-step,
never the engine itself.

## What a Schematika graph actually looks like

Grounded in `src/schematika/core/symbol.py`, `src/schematika/core/parts.py`,
`src/schematika/electrical/builder.py`:

- A **node** is a `Symbol` (`core/symbol.py:29`): a frozen dataclass with
  `elements: list[Element]`, `ports: dict[str, Port]`, and `label`. Every
  symbol factory (`fuse`, `coil`, `no_contact`, `nc_contact`, ...) builds one
  at the origin; ports carry an absolute `Point` *and* a `Vector` direction —
  e.g. `breakers.py:63-64` puts port `"1"` at `(0, -h/2)` with direction
  `(0, -1)` (up) and `"2"` at `(0, +h/2)` with direction `(0, 1)` (down).
  Direction is the side constraint: a wire leaving a port must leave in that
  direction, not just terminate at a point.
- An **edge** is a manual or pin-based connection
  (`CircuitBuilder.add_connection`, `builder.py:942`): `(comp_idx_a,
  pole_idx_a, comp_idx_b, pole_idx_b, side_a, side_b)`. `side_a`/`side_b`
  default to `"bottom"`/`"top"` — i.e. today's ladder layout is already
  hand-coded as strictly top-to-bottom, one layer per rung position, laid out
  by `create_horizontal_layout` (`electrical/layout/layout.py`) with a fixed
  `spacing`/`symbol_spacing`, not by any graph algorithm.
- `Point`/`Vector` (`core/geometry.py`) are the coordinate system layout
  output has to land in; symbols are repositioned with the pure function
  `schematika.core.transform.translate(symbol, dx, dy)` (ports move with the
  body, since `Symbol` is frozen and `translate` returns a new one).

So the real target shape for any layout engine is: **nodes with fixed-size
bounding boxes and 1+ directional ports on specific sides, edges that must
attach to a specific port (not just "the node"), output as `Point`s fed back
into `translate`**. That is a strictly harder problem than "lay out a
directed graph," and it's the yardstick every candidate below is measured
against.

## Candidate survey

| Library | Pure Python? | Maintenance | License | Port-awareness | Orthogonal routing |
|---|---|---|---|---|---|
| [`grandalf`](https://github.com/bdcht/grandalf) 0.8 | Yes | Stale: last PyPI release Jan 2023, no commits/PR activity in the past 12 months; 269 stars, 11 open issues | **Dual GPLv2 / EPLv1** — copyleft, not MIT-compatible without a licensing decision | None. Vertices need only `.view.w`/`.view.h`; edges terminate at node centers, no side/port concept at all | None. `route_with_lines`/`route_with_splines` connect layer-to-layer through dummy nodes with straight/bezier segments, not axis-aligned jogs |
| `networkx` (`multipartite_layout`, `spring_layout`, `kamada_kawai_layout`, `topological_generations`) | No — pulls in `numpy` (compiled) for these layout functions | Very actively maintained, BSD-3 | BSD-3 | None whatsoever | None — force-directed/generation layouts return centers only; `multipartite_layout` doesn't even minimize crossings, just places nodes by insertion order within a layer (proven below) |
| `fast-sugiyama` (PyPI) | Claims pure Python | Found during this survey but not evaluated further — no meaningful download/star signal, looked like a thin experimental wrapper around the same Sugiyama steps `grandalf` already implements, not independently vetted | Unverified | Unverified | Unverified |
| `dagua` (GitHub, PyTorch-based "pure Python" Dagre port) | No — requires PyTorch, explicitly pre-alpha | Pre-alpha, active but early | Unverified | Not documented | Not documented |
| `graph-layout` (shakfu/graph-layout) | Pure Python w/ optional Cython | Small, low visibility; not independently vetted for this spike | Unverified | Not documented (claims force-directed/hierarchical/orthogonal/planar modes, but this is a general CS-drawing library, not schematic-aware) | Claims support but unverified here |
| Hand-rolled Sugiyama (no dependency) | Yes | N/A | N/A (own code) | Full — you build exactly what's needed | Full — you build exactly what's needed |

No pure-Python candidate found in this survey (grandalf included) models a
port or a side constraint, and none does orthogonal edge routing out of the
box. This matches the spike brief's expectation for `networkx` and turned
out to be equally true for `grandalf`, which is the more surprising finding
since it specifically brands itself as a "graph *drawing* algorithms
framework."

## Prototype

Code: `research/layout/pure-python-graph-layout/`.

- `circuit_graph.py` — builds a synthetic but realistic forward/reverse
  contactor interlock ladder (`-F1`/`-F2` fuses, `-S1`/`-S2` start contacts,
  `-K1`/`-K2` coils with `-K1`/`-K2` NC interlock aux contacts) using the
  **real** Schematika symbol factories (`fuse`, `no_contact`, `nc_contact`,
  `coil` from `schematika.electrical.symbols`), each placed at the origin the
  way the library actually builds them, with real IEC port IDs (`"13"/"14"`
  for NO, `"11"/"12"` for NC, `"A1"/"A2"` for coils). The fuse-to-contact
  feeds are deliberately swapped (F1 feeds S2's rung, F2 feeds S1's rung) to
  force an edge crossing that a naive layer-order algorithm cannot avoid.
- `run_grandalf_layout.py` — builds a `grandalf` graph sized from each
  symbol's real bounding box (`core.renderer.calculate_bounds`), runs
  `SugiyamaLayout`, reads back `view.xy`, maps to `Point`s, `translate()`s
  the real `Symbol`s there, draws straight lines port-to-port, and renders
  through Schematika's actual `rendering.svg.render_to_svg` — i.e. the
  prototype output is a genuine Schematika-renderer SVG, not a mock.
- `run_networkx_layout.py` — same graph, laid out with
  `topological_generations` + `multipartite_layout` (`networkx`'s closest
  built-in recipe to a layered DAG layout), for direct comparison.
- `render_png.py` — rasterizes the SVG via PyMuPDF for visual review.

### Result: grandalf (`output_grandalf.svg`)

Crossing minimization worked: it reordered `S1`/`S2` and `K1_NC`/`K2_NC`
within their layers so the deliberately-swapped `F1→S2`/`F2→S1` feeds render
as two clean parallel vertical rungs with **zero** crossings — a real,
correctly-computed result, not a coincidence of the input order. Visual
review (rendered PNG, read back) confirms: labels are legible, no overlaps,
the two rungs are symmetric. The only diagonal lines left are the
unavoidable ones — the shared `L1`/`N` bus dot fanning out to two rungs,
which is exactly the "no bus-bar rendering, no orthogonal jog" gap: a real
ladder diagram draws `L1` as a horizontal rail with vertical drops at 90°,
and grandalf has no concept of that; it gave us a single point and two
straight diagonal lines to it. 4 of 10 edges are non-vertical for that
reason alone.

### Result: networkx (`output_networkx.svg`)

Confirms the predicted gap directly: with no crossing-minimization pass,
`multipartite_layout` places nodes by insertion order within a layer, so the
deliberately-swapped feeds render as a visible **X crossing** between the
`K1_NC`/`K2_NC` and `S1`/`S2` layers — 6 of 10 edges non-vertical, including
a real, uncorrected crossing that a human would immediately want to fix by
hand. This is the concrete cost of NetworkX's layout functions not
including a Sugiyama-style ordering pass: they place, they do not optimize.

### What neither prototype does

- Neither respects port **sides**. Both scripts had to reach into
  `node.top_port`/`node.bottom_port` by convention (hand-picked per
  component) because grandalf and networkx have no side/direction concept at
  all — if a real component needed a left/right port instead of top/bottom
  (motors' `U`/`V`/`W`, SPDT's composite `1_com`/`1_nc`/`1_no`), nothing in
  either library would know or care; that logic has to live entirely outside
  the layout call.
- Neither produces routed wires. Every wire in both outputs is a single
  straight `Line` from one port's absolute position to another's. Any
  orthogonal jogging, bus-bar rendering, or crossing-avoidance *for wires*
  (as opposed to node crossing) is 100% Schematika's own responsibility.

## Comparison framing vs. sibling tracks

- **vs. `elk-bridge`**: ELK is a mature, port-aware, orthogonal-routing
  layout engine out of the box — it solves the actual problem this survey
  shows `grandalf`/`networkx` do not. The cost is a JVM/Node subprocess
  dependency. `grandalf` gets you free layer/column assignment with zero
  runtime language dependency, but forces you to build the port-attachment
  and orthogonal-routing layers yourself regardless — which is most of the
  hard part. If `grid-astar-router` (below) is viable, it already has to
  solve port attachment and routing; at that point grandalf's crossing
  minimization is a nice-to-have input to that engine's column ordering, not
  a reason to avoid it.
- **vs. `grid-astar-router`**: that track's zone/grid placement (power rail
  → protection → control → coils → terminals) plus A* orthogonal routing is
  effectively hand-building the two things this survey found missing from
  every pure-Python candidate: port-side awareness and orthogonal routing.
  `grandalf`'s only potential contribution to that track is replacing its
  crossing-minimization heuristic for ordering components *within* a zone —
  a minor optimization, not a foundation.

## Recommendation

Do not adopt `grandalf` (or any surveyed pure-Python graph library) as
Schematika's layout engine. If `grid-astar-router` needs a crossing-reducing
ordering heuristic within a layer/zone and doesn't want to write one,
`grandalf`'s `SugiyamaLayout` ordering step could be vendored or called
narrowly for that sub-problem — but note the GPLv2/EPLv1 dual license means
this needs an explicit call before it becomes a real dependency, not an
`uv add` during implementation. Building the port-aware placement +
orthogonal router by hand (`grid-astar-router` track) remains the right
path; nothing here is mature enough to shortcut it.
