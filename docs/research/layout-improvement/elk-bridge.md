# elk-bridge: driving Eclipse Layout Kernel from Schematika

Track: `elk-bridge`. Question: can `elk.layered` (via elkjs, run under Node)
give Schematika port-aware orthogonal layout, without permanently adding a
second language to the *runtime* dependency graph consumers depend on?

**Verdict: pursue with caveats.** The bridge works — a real Schematika
circuit round-trips through elkjs and back into repositioned `Symbol`s
today — but only as a **dev-time, opt-in layout regenerator**, never as
part of `schematika`'s importable runtime path. Two things need to happen
before this is worth more than a spike: (1) Schematika needs a public
`(tag, pin) -> real Port.id` resolver, because the mapping is currently
broken in a way that isn't ELK-specific (see Finding 2), and (2) someone
needs to decide whether the visual quality gain over the existing ladder
layout justifies a Node/npm toolchain requirement for anyone who wants to
regenerate layouts (not for anyone who just imports `schematika` and
renders an already-built diagram).

## What was built

`research/layout/elk-bridge/`:

- `to_elk.py` — converts a `CircuitBuilder.build()` `BuildResult` into an
  ELK JSON graph: one node per placed `Symbol` (size = its own bounding
  box via `core.bbox.compute_bounding_box`), one ELK port per real
  `Symbol.ports` entry (side inferred from `Port.direction`'s dominant
  axis, since Schematika ports carry an exit-vector, not an explicit
  side — the same information, different shape), one edge per
  `wire_connections` tuple.
- `elk_bridge.cjs` — a ~25-line Node script: reads an ELK JSON graph on
  stdin, runs `elk.layout()` (`elk.algorithm: layered`,
  `elk.edgeRouting: ORTHOGONAL`), writes the laid-out graph to stdout.
  Confirmed working standalone against a hand-written 2-node graph before
  wiring up the Python side.
- `run_layout.py` — end-to-end: builds the same 3-phase DOL motor-starter
  circuit as `examples/02_dol_starter.py` (terminal -> breaker -> contactor
  -> thermal overload -> motor -> terminal, real symbol factories, not
  mocks), converts it, shells out to `node elk_bridge.cjs` via
  `subprocess.run`, maps ELK's returned `(x, y)` back onto each `Symbol`
  via `core.transform.translate(symbol, dx, dy)` (a delta move — exactly
  what's needed since ELK returns absolute top-left node coordinates and
  Schematika symbols already have absolute in-page coordinates), draws
  ELK's own orthogonal edge-routing sections as `Line` elements, and
  renders the result with the existing `render_system()` — no changes to
  `src/schematika/` were needed to render ELK's output.
- `debug_pin_id_mismatch.py` — the script that pinned down Finding 2
  below.
- `output/` — `input_graph.json` (what Python sent), `elk_result.json`
  (what ELK returned), and both SVGs (`dol_starter_original_layout.svg` =
  Schematika's own ladder layout, `dol_starter_elk_layout.svg` = the same
  circuit repositioned by ELK) for comparison.

This ran successfully end to end:

```
Built circuit: 6 symbols, 15 wire connections
[to_elk] 3 wire_connections entries had no matching real Port and were dropped: [('M1', '2', 'source'), ('M1', '4', 'source'), ('M1', '6', 'source')]
Drew 28 ELK-routed wire segments
Rendered: .../output/dol_starter_elk_layout.svg
Rendered (original, for comparison): .../output/dol_starter_original_layout.svg
```

Both SVGs have sane, non-degenerate bounding boxes (original: 109mm x
300mm; ELK layout: 159mm x 302mm — wider because ELK's default
`nodeNodeBetweenLayers` spacing is generous compared to Schematika's
tight ladder spacing; tunable via `layoutOptions`). I did not do a full
PNG visual read (`cairosvg`/`playwright` aren't installed in this
worktree's venv and installing a Chromium download is disproportionate
for a feasibility spike); the SVG structure and coordinate ranges were
sanity-checked directly instead.

## Findings

**1. No native Python ELK binding exists in the form the seed research
assumed — but a real one appeared very recently, and it changes the
calculus.** The seed doc's "pyelk" claim doesn't hold up as stated:

- PyPI `elkjs` (0.1.0) is an unrelated novelty package ("Draw beautiful
  ASCII and SVG pine trees") that happens to squat the name — a real trap
  for `uv add elkjs`.
- PyPI `pyelk` (0.3.0, `depetrol/pyelk`, uploaded 2026-02-20) **is** a
  genuine pure-Python port of ELK's layered/stress/force/mrtree/radial
  algorithms, consuming the same ELK JSON format, EPL-2.0 licensed, zero
  JS/Node/JVM dependency. A smoke test (`claude-tools/pyelk_smoke_test.py`,
  gitignored scratch, not part of the deliverable) against the same
  2-node/1-edge graph used to first validate `elk_bridge.cjs` produced
  layered+orthogonal coordinates essentially matching elkjs's own output
  (node spacing differed slightly — 40mm vs 44mm gap — but topology,
  port-side handling, and edge-section geometry all matched). **But**: 5
  GitHub stars, 5 commits, no CI badge, no test suite visible, unvalidated
  against elk.layered's full option surface or larger graphs. This is a
  genuinely relevant data point (it would eliminate the Node dependency
  entirely) but not something to build on without real validation --
  that validation is `pure-python-graph-layout`'s job, not this track's;
  flagging it here because it's the direct answer to "does a native
  binding exist" and it changes what "pursue with caveats" should mean six
  months from now.

**2. `BuildResult.wire_connections` pin strings are not `Symbol.ports`
keys, for any component — this is a real, confirmed, pre-existing gap in
Schematika, not something ELK introduced.** `Symbol.ports` is always keyed
positionally (`"1".."N"`), regardless of a symbol factory's declared
semantic pin names. `contactor()` documents this itself in its own
doctest, `src/schematika/electrical/symbols/assemblies.py:47`:

```python
>>> sym = contactor(label="K1")
>>> sorted(sym.ports.keys())
['1', '2', '3', '4', '5', '6']
```

even though `contact_pins` defaults to `CONTACTOR_3P_PINS = ("L1", "T1",
"L2", "T2", "L3", "T3")`. Those semantic names only ever reach
`BuildResult.wire_connections` (via `_infer_default_pins` /
`_resolve_pin`'s pins-list branch in `builder_utils.py`) and the on-diagram
text labels — they never become real port identifiers. So converting
`wire_connections` tuples directly into `"{tag}.{pin}"` ELK port ids
fails immediately (`JsonImportException: Referenced shape does not exist:
Q1.L1`). `to_elk.build_pin_resolver()` works around this by rebuilding the
missing mapping heuristically (up-facing vs. down-facing port pools per
tag, sorted left-to-right, assigned to semantic labels in first-seen
order) — the same geometry order `_resolve_pin`'s own fallback branch
already uses internally, just not exposed. It works for 12 of 15 edges in
the DOL starter.

**3. The 3 edges that don't resolve are a second, independent bug: `motor`
exposes 4 real ports but the builder auto-generates 6 candidate pin labels
for `poles=3`.** `add_symbol()`'s fallback
(`pins = [str(i) for i in range(1, poles * 2 + 1)]` when a factory has no
usable `pins`/`*_pins` default) assumes every multi-pole component has
`2 * poles` ports. `motor` doesn't follow that convention (4 real ports:
U/V/W/PE-style, all up-facing, no pass-through side) — so
`wire_connections` claims a connection to `"M1.5"` / `"M1.6"`, a port
`M1` doesn't have. This wasn't found by inspection; it fell out of running
the actual conversion and printing what a resolver couldn't match — a
concrete case where a mechanised check surfaced something code review
wouldn't have. **This is a Schematika correctness gap independent of ELK**:
any port-aware consumer of `wire_connections` (a layout engine, a
DRC/netlist exporter, a future test) hits the same wall. Worth a follow-up
issue regardless of which layout track wins: either `BuildResult` should
expose a `resolve_port(tag, pin) -> Port | None` that's actually correct
for every factory, or `wire_connections` should log real `Port.id`s
directly instead of semantic labels.

**4. Node.js/npm are available in this environment** (`node v24.12.0`,
`npm 11.7.0`), and `elkjs@0.12.0` installs and runs cleanly via
`npm install` in `research/layout/elk-bridge/` (7.8MB `node_modules`,
gitignored). The subprocess bridge itself (`subprocess.run(["node",
"elk_bridge.cjs"], input=..., capture_output=True)`) is ~10 lines of
Python and has no failure modes beyond "Node isn't installed" / "the JSON
graph is malformed" — both loud, neither silent-corrupting.

**5. Licensing: ELK (both the Java original and elkjs) is EPL-2.0.**
`pyelk` is also EPL-2.0. EPL-2.0 is copyleft only for modifications to the
covered work itself, not for programs that merely invoke it as a separate
process (this bridge) or as a separate library — it's compatible with
Schematika staying unlicensed-or-whatever-it-is for its own code as long
as ELK/elkjs/pyelk aren't vendored-and-modified. Not a blocker either way.

## Fit with Schematika's invariants

| Invariant | Fit |
|---|---|
| `core/` is I/O-free (no subprocess/open) | **Respected as designed**: the subprocess call lives in `run_layout.py` (a spike/tooling script), not in `core/` or any domain package. A production version would need a new, explicitly-I/O `layout` shell package (like `rendering.typst`), never inside `core`. |
| Domain packages return frozen `*BuildResult` | Not violated — this spike consumes an existing `BuildResult` and produces a new `Circuit` (already a mutable accumulator by design, per `ARCHITECTURE.md`); it doesn't touch a builder's return type. |
| Zero *required* runtime deps in `core` | **Preserved**: Node/npm/elkjs would be a dependency of a `layout`-regeneration tool that a maintainer runs occasionally (like `kicad-cli` for `pcb.kicad_export`, already an accepted precedent in this repo — external binary, optional, dev/build-time only), never something `import schematika` pulls in for an end consumer who just renders an already-built diagram. |
| One-way dependency rule | A production integration would sit above `electrical`/`pid` (it needs their model classes) and below `project` — same shape as `rendering.typst`: optional, imports domain packages, no domain package imports it. |

## Integration effort estimate (if pursued past spike)

- **Small**: the Python->ELK->Python round trip (`to_elk.py` + subprocess
  call) is done and works; wiring it behind an opt-in
  `layout.elk_layout(result) -> Circuit` function is maybe a day, *given*
  the resolver in Finding 2 is fixed properly (not heuristically) first.
- **Medium**: fixing Finding 2/3 properly means either (a) adding a real
  `(tag, pin) -> Port` resolver to `BuildResult` — useful independent of
  ELK — or (b) changing `wire_connections` to log real `Port.id`s, which
  is a breaking change to a public field several other things
  (`plc_report.py`, `terminal_emit.py`) already consume. (a) is safer.
  Estimate: 2-3 days including tests, since it touches
  `builder_utils.py`'s two resolver functions and needs the `motor`-style
  port-count mismatch (Finding 3) fixed too, not just papered over.
- **Open design question, not yet effort-estimated**: ELK's `layered`
  algorithm is a general DAG layout, not IEC-ladder-aware. It doesn't know
  "terminals belong at the bottom rail" or "coils/contacts pair via a
  dashed linkage that must stay adjacent" — those are Schematika-specific
  placement rules currently encoded procedurally in `builder_phases.py`.
  Getting IEC-idiomatic results out of ELK would mean either (a) heavy use
  of `elk.layered.crossingMinimization`/`layering` options plus manual
  post-constraints, or (b) using ELK only for the parts of a diagram that
  *are* a general graph (e.g. `pid`'s pipe/equipment topology, or the
  `overview` module's interactive graph) and keeping the procedural ladder
  builder for `electrical`. This wasn't prototyped here — it's a real
  unknown that the visual-quality comparison in `output/` only partially
  answers (both SVGs exist, but "is the ELK one actually *better* for a
  ladder diagram" wasn't scored, since ELK doesn't know it's a ladder).

## Pros

- Confirmed working, not theoretical: a real Schematika circuit
  round-trips through ELK today.
- Orthogonal port-aware routing is a capability the current
  `builder_phases.py` procedural layout doesn't have as a general
  primitive — genuinely useful for `pid`/`overview`, where the graph
  shape is closer to what ELK is built for than `electrical`'s ladder
  convention.
- Dev-time-only Node dependency is a real, low-cost pattern this repo
  already accepts elsewhere (`kicad-cli` for `pcb`).
- ELK is mature, well-documented, and actively maintained (unlike the
  brand-new `pyelk` port).

## Cons

- Two real bugs (Findings 2 and 3) had to be worked around, not fixed, to
  get this far — they're Schematika bugs, not ELK integration friction,
  but they mean "just feed `wire_connections` to a layout engine" doesn't
  actually work today for *any* port-aware engine, ELK included.
- `elk.layered` has no concept of IEC ladder conventions; a naive
  application produces a technically-valid but not obviously
  IEC-idiomatic layout for `electrical` specifically (untested how bad —
  see the open question above).
- Requires Node/npm as a second toolchain for whoever regenerates
  layouts, even if it's excluded from the consumer runtime path.
- The one Python-native alternative (`pyelk`) is too immature to trust
  yet (5 commits).

## Verdict

**Pursue with caveats**, specifically:

1. Fix Finding 2/3 first (a real `resolve_port` on `BuildResult`) —
   independent of ELK, and blocking for any future port-aware tooling, not
   just this track.
2. Don't apply ELK to `electrical`'s ladder layout as the primary engine;
   its DAG-layout model doesn't know IEC conventions, and
   `grid-astar-router`'s zone-based approach is a better structural fit
   for that specific domain (see that track's findings).
3. Do consider ELK for `pid` (equipment/pipe topology is a more
   general graph) and `overview` (already graph-shaped, arguably the best
   fit of the four) — cross-reference `pid-layout` and
   `overview-shared-engine`'s findings before committing.
4. Re-check `pyelk`'s maturity in 6-12 months; if it stabilizes, it
   removes the Node dependency entirely and this verdict gets easier, not
   harder.
