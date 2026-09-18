# Constraint solver (z3 / OR-tools CP-SAT) for cabinet placement

Track: `constraint-solver`. Branch: `layout-improvment-constraint-solver`.

## Question

Can z3-solver or OR-tools CP-SAT express rigid cabinet-schematic placement
rules (Y-zone pinning by component type, no-overlap, left-to-right column
ordering by circuit index) and solve them fast enough to be worth the
dependency, compared to a plain deterministic allocator?

## Grounding in the real model

Read `src/schematika/core/geometry.py` (`Point`, `Vector`, frozen), `core/symbol.py`
(`Symbol`/`Port`, ports carry absolute `Point` positions), `core/constants.py`
(`GRID_SIZE = 5.0` mm, `DEFAULT_POLE_SPACING = 10.0` mm), and the existing
deterministic layout helpers in `src/schematika/electrical/layout/layout.py`
(`layout_vertical_chain`, `layout_horizontal` — plain cumulative-offset
placement, no solver, already in production). There is no existing "zone" or
"no-overlap" concept in the codebase today; this spike had to invent a
plausible one grounded in the mm scale and `StandardTags` prefixes
(`electrical/model/constants.py:57-80`: `F` fuse/breaker, `Q` contactor,
`K` relay, `X`-prefixed terminals).

## Synthetic cabinet

`research/layout/constraint-solver/circuit.py` generates a ladder-diagram
cabinet: one incoming `MAIN` disconnect, then per circuit a fuse (`F`,
always), a contactor (`Q`, 45% of circuits), a relay (`K`, 65% of circuits),
and a terminal (`X`, always). Bounding boxes are illustrative but grid-scaled
(20-40mm wide protection/switching gear, 8mm terminal pitch). Zones are fixed
Y-bands by type (`MAIN`→0mm, `F`→60mm, `Q`→130mm, `K`→200mm, `X`→270mm) —
"zone pinning" is a lookup, not a decision variable, in all three approaches.
Sizes tested: 15/30/50/100 circuits → 51/100/163/324 components, covering and
exceeding the requested 50-100 range.

Three implementations of the same three rules, all producing
`{component_id: x_position}`, checked by a shared `verify.py`:

- `deterministic_allocator.py` — plain Python, ~20 lines.
- `solve_z3.py` — z3 `Optimize`, pairwise `Or()` disjunction for no-overlap.
- `solve_ortools.py` — CP-SAT, native `NewIntervalVar` + `AddNoOverlap`.

## Results

Wall-clock solve time (excludes cabinet generation), `uv run python benchmark.py`:

| Circuits | Components | Deterministic allocator | z3 | OR-tools CP-SAT |
|---|---|---|---|---|
| 15 | 51 | 0.045 ms | 12.5 ms | 23.3 ms |
| 30 | 100 | 0.045 ms | 42.8 ms | 16.3 ms |
| 50 | 163 | 0.057 ms | 145.4 ms | 42.7 ms |
| 100 | 324 | 0.109 ms | 1206.8 ms | 138.0 ms |

All three produced zero constraint violations at every size (`verify.py`
checks no-overlap, column ordering, and zone coverage independently of how
positions were derived).

Both solvers are "fast enough" in absolute terms — even z3's worst case
(1.2s at 324 components) is a non-issue given the repo's stated "runtime
speed is not a constraint" policy for this whole spike. But the *shape* of
the scaling is the interesting part: z3's pairwise `Or()` no-overlap
encoding is quadratic in per-zone component count (~100x slower at 6x the
components), while CP-SAT's native interval propagation scales much better
(~6x slower at 6x the components) but still costs three orders of magnitude
more than the allocator at every size. The deterministic allocator's cost is
immeasurable at cabinet scale — it doesn't matter which n you pick.

## Does this actually need a solver?

No. This is the key finding, and the spike's own framing predicted it.

"Column ordering by circuit index" is not an independent rule sitting
alongside "no-overlap" — it's the thing that removes the only real choice
no-overlap would otherwise require. No-overlap between two components is
normally a disjunctive decision ("A left of B, or B left of A — search for
which"). But once you require column X to be monotonically increasing in
circuit index, the direction is fixed for every pair: circuit *i* is left
of circuit *j* whenever *i* < *j*, full stop. What remains is a system of
difference constraints of the form `col_x[i+1] >= col_x[i] + width[i] + gap`,
which is a single-pass longest-path computation on a DAG — the textbook
polynomial case that SAT/CP solvers exist to avoid *needing* for harder
problems. Both z3 and CP-SAT rediscover this at solve time (that's why
they're fast in absolute terms), but they're paying propagation/search
machinery overhead to re-derive an answer the allocator already knows how
to write down directly.

This matches the deterministic layout code already in the repo
(`layout_vertical_chain`, `layout_horizontal` in
`src/schematika/electrical/layout/layout.py`): cumulative-offset placement
is exactly this kind of DAG-shaped problem, and it doesn't reach for a
solver either.

A solver would earn its keep the moment the rule set introduces a genuine
combinatorial choice with no fixed total order — e.g. 2D bin-packing
components across multiple physical panel pages (that's
`pagination-partitioner`'s territory, not this track's), minimizing wire
crossings by choosing component order within a zone (an actual optimization
objective, not just placement rules), or satisfying conflicting alignment
constraints where no ordering makes everyone happy and the solver has to
find the least-bad compromise. None of that is in the three rules this
track was asked to model.

## Ergonomics

- **Deterministic allocator**: 20 lines, one dict, one loop, no imports
  beyond the domain types. Reads as what it is: sort circuits, walk forward,
  stack widths. Anyone touching `electrical/layout/` could maintain this on
  day one.
- **CP-SAT**: clean for the no-overlap primitive specifically
  (`NewIntervalVar`/`AddNoOverlap` is a one-line-per-zone call, purpose-built
  for exactly this), but still requires understanding `IntVar`, model/solver
  separation, and status-code handling (`OPTIMAL`/`FEASIBLE`/`INFEASIBLE`) —
  a bigger conceptual surface than a for-loop for a repo where `core/` is
  I/O-free dataclasses and builders.
- **z3**: the most verbose of the three here because no-overlap has no
  native primitive — it's hand-written pairwise `Or()`, which is also what
  causes its quadratic blowup. z3 shines on problems shaped like "prove this
  is satisfiable/find a witness under arbitrary boolean combinations of
  arithmetic constraints"; a cabinet layout with a natural total order isn't
  that problem.
- Neither solver's model reads as clearly as the allocator to someone who
  doesn't already know CP/SMT modeling idioms (`IntVar`, `Optimize`,
  intervals). That's a real maintainability cost for a sole-author alpha
  library.

## Dependency weight

| | z3-solver | OR-tools |
|---|---|---|
| Installed size (this worktree's `.venv`) | ~22 MB | ~172 MB (ortools 81MB + pandas 45MB + numpy 45MB combined + protobuf) |
| Transitive deps pulled by `uv add` | none | `numpy`, `pandas`, `protobuf`, `absl-py`, `six`, `python-dateutil`, `tzdata`, `immutabledict` (10 packages total) |
| License | MIT | Apache-2.0 |
| Python 3.14 wheel available today (2026-09-18) | yes | yes |

Both are permissively licensed, so licensing isn't the differentiator the
question framed it as — dependency *weight* is. OR-tools drags in pandas and
numpy as transitive dependencies for a pure CP-SAT use case that needs
neither; that's a poor fit for a repo whose stated invariant is "zero
runtime deps in `core`" and generally dependency-conscious posture
(`pcb`/`rendering.typst`/`mcp` all keep their extras optional and narrow).
z3 is a single self-contained wheel with no transitive footprint, which
would be the better pick *if* a solver were ever justified — but per above,
one isn't, for this rule set.

## Verdict: drop

Neither dependency should be added for this feature. The three rules
(zone pinning, no-overlap, column ordering by circuit index) are a total
order in disguise, solvable by a ~20-line deterministic allocator running
in fractions of a millisecond at realistic cabinet scale, with code that
reads clearly to anyone maintaining `electrical/layout/`. Both z3 and
OR-tools solve the same problem correctly and "fast enough" in absolute
terms, but they add real dependency weight (OR-tools especially: 172MB and
8 transitive packages including pandas/numpy for a CP-only workload) and a
CP/SMT modeling vocabulary this repo doesn't otherwise need, to re-derive an
answer that direct code already computes for free.

**Caveat for future tracks**: if `pagination-partitioner` or another future
layout track introduces genuine bin-packing (page assignment) or a real
optimization objective (minimize crossings, minimize total wire length)
where no fixed total order exists, revisit this. If that happens, prefer
CP-SAT over z3 — its native scheduling/packing primitives
(`AddNoOverlap2D`, cumulative constraints, objective minimization) are a
better ergonomic fit for placement-shaped problems than z3's general-purpose
SMT machinery, and its solve-time scaling was measurably better here despite
starting from a less favorable (native-primitive) encoding. Budget for its
dependency weight if that day comes.

## Prototype

`research/layout/constraint-solver/`:

- `circuit.py` — synthetic cabinet generator (zones, sizes, `Component`).
- `deterministic_allocator.py` — the ~20-line direct-assignment allocator.
- `solve_z3.py` — z3 `Optimize` model.
- `solve_ortools.py` — OR-tools CP-SAT model.
- `verify.py` — shared correctness checker (no-overlap, column order, zone
  coverage) used against all three outputs.
- `benchmark.py` — runs all three at 15/30/50/100 circuits, prints timing
  and violation counts. Run with `uv run python benchmark.py` from this
  directory (files use plain top-level imports, not relative ones, since
  `constraint-solver` — with a hyphen — isn't a valid Python package name).

`z3-solver` and `ortools` were added via `uv add` to this worktree's
`pyproject.toml`/`uv.lock` only, as instructed — not to the main repo.
