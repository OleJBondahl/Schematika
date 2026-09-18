# `llm-dsl-pipeline`: LLM-generated declarative placement scripts

Question: could an LLM translate a circuit/netlist description into a
declarative, relative-placement DSL — a schemdraw-style `.right()/.down()/.at()`
wrapper, but layered on Schematika's own `Point`/`Symbol`/port model — that
Schematika already knows how to execute and render, and would that reduce
manual placement work versus today's `position: Point` calls?

**Verdict: drop the new-module idea; the underlying "LLM writes declarative
code instead of raw coordinates" concept already works today, for free,
because `CircuitBuilder` and `PIDBuilder` already are that DSL.**

## Central finding: the DSL already exists, and it isn't schemdraw-shaped

The seed conversation (`Optimizing Code-Generated Electrical Schematic
Layouts.md`, Option 3 / Option A) assumes the gap is "LLM emits raw
coordinates" vs. "LLM emits a schemdraw-style relative script that a cursor
object turns into coordinates." Reading `src/schematika/electrical/builder.py`
and `src/schematika/pid/builder.py` shows that gap is already closed on
Schematika's own terms, without schemdraw:

- `CircuitBuilder.add_symbol` / `add_terminal` take a `placement:
  PlacementOptions | None`, whose `position` field is
  `Literal["below", "above", "left", "right"]` (`src/schematika/electrical/model/constants.py:10`),
  not a `Point`. `PlacementOptions.relative_to` takes a `ComponentRef` or
  `PortRef` (`src/schematika/core/options.py:27-33`). Omit `placement`
  entirely and the component chains below the previous one automatically
  (`src/schematika/electrical/builder.py:391-392`).
- `PIDBuilder.add_equipment` takes an `EquipmentPlacement` with the same
  shape: `relative_to` (an anchor name) + `from_port`/`to_port` + `offset:
  Vector`, or an absolute `position`/`x`/`y` only for placement roots
  (`src/schematika/pid/builder.py:144-213`).

In other words: `relative_to=coil_ref.pin("A1"), position="above"` **is**
`.at(coil_ref.pin("A1")).up()` in schemdraw's vocabulary. Grepping the
example suite confirms this isn't theoretical — `examples/02_dol_starter.py`
through `examples/07_showcase_cabinet.py` contain **zero** `Point(...)`
constructor calls for symbol placement. Every symbol in every example is
placed either by the default vertical chain or by `relative_to=<a named
ref>` + a literal direction string. The only raw coordinates that appear
anywhere are the single `set_layout(x=..., y=...)` origin per independent
sub-circuit column (`examples/03_coil_contact_pair.py:56,71`,
`examples/05_multi_builder.py:62,83,138`) — one scalar pair per page/column,
not per symbol.

This reframes the whole spike question. The premise "today's direct `Point`
calls" barely describes `electrical` as it exists now. Manual coordinate
math survives in exactly one place: `pid.PIDBuilder`'s absolute-root
equipment (`abs_position`, `src/schematika/pid/builder.py:97,208,398-400`),
because P&ID equipment doesn't chain the way ladder rungs do — there's no
"previous rung" to hang the first pump or vessel off of.

## Investigation

### 1. What a minimal relative DSL needs to wrap

Read: `src/schematika/core/geometry.py` (`Point`, `Vector` — frozen,
`Point + Vector -> Point`, `Point - Point -> Vector`), `src/schematika/core/symbol.py`
(`Port(id, position, direction)`, `Symbol(elements, ports, label)`),
`src/schematika/core/bbox.py` (`compute_bounding_box`), and
`CircuitBuilder`/`PIDBuilder` as above.

A cursor wrapper needs: (a) a "current anchor" (`ComponentRef | PortRef`),
(b) a "current heading" (one of the four `Position` literals), (c) methods
that resolve `(anchor, heading, spacing)` into a `PlacementOptions` and call
the existing `add_symbol`/`add_terminal`/`add_equipment`. That's the entire
design — see `research/layout/llm-dsl-pipeline/layout_dsl_sketch.py`
(`Cursor` class, ~70 lines) for a working prototype built directly against
this repo's real `CircuitBuilder`, `ComponentRef`, `PortRef`, `SymbolConfig`,
and `PlacementOptions` (not schemdraw's own element classes).

### 2. Side-by-side comparison

`research/layout/llm-dsl-pipeline/a_today_direct.py` (today's API) and
`research/layout/llm-dsl-pipeline/b_relative_dsl_version.py` (the Cursor
sketch) both build the same rung — `X1 -> F1 (breaker, stands in for a fuse)
-> S1 (nc_contact, E-stop) -> K1 (coil) -> X2` — and both run under `uv run
python`. Their rendered SVGs are **byte-identical**
(`research/layout/llm-dsl-pipeline/output/{a_today_direct,b_relative_dsl_version}.svg`,
verified with `diff`).

Direct API (5 statements, no `Point`):

```python
builder.add_terminal("X1", config=TerminalConfig(poles=1))
builder.add_symbol(breaker, config=SymbolConfig(tag_prefix="F"))
builder.add_symbol(nc_contact, config=SymbolConfig(tag_prefix="S"))
builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
builder.add_terminal("X2", config=TerminalConfig(poles=1))
```

Cursor DSL (chained, schemdraw-flavored):

```python
cursor.terminal("X1").down(breaker, tag="F").down(nc_contact, tag="S") \
      .down(coil, tag="K").terminal("X2")
```

For a linear chain the DSL saves essentially nothing: it is a rename of
`add_symbol(factory, config=SymbolConfig(tag_prefix=...))` to
`.down(factory, tag=...)`, and it produces the identical `PlacementOptions`
call under the hood. Line count and token count are comparable; the direct
version is arguably *more* explicit about what's happening (SymbolConfig,
PlacementOptions are named, greppable types), which matters more for an
LLM's output than for a human's.

For the *non-chain* case — the `examples/04_spdt_positioning.py` /
`examples/05_multi_builder.py` pattern (branches, parallel contacts,
cross-builder references) — the comparison gets worse for the DSL, not
better. Today's explicit form is:

```python
builder.add_terminal(
    "X1",
    placement=PlacementOptions(relative_to=spdt.pin("12"), position="above", spacing=gap),
)
```

The cursor's equivalent is `.at(spdt.pin("12"), heading="above").terminal("X1")`
— but `.at()` still requires the caller (human or LLM) to have kept the
`spdt` Python variable around, exactly as the direct call does. The cursor
adds nothing here except an extra method name to remember, *and* it
introduces new implicit state that the direct form doesn't have: after
`.at(x)`, the cursor's "current heading" persists until the next `.at()` or
direction call. A long generated script that loses track of which `.at()`
call is still "active" silently wires the next component to the wrong
anchor. Named `relative_to=<ref>` calls can't have this bug — every call
states its anchor explicitly, so there's no persistent cursor state to lose
track of.

### 3. What an LLM needs as input, and where it hallucinates

Required input: (a) a netlist/BOM (component instances + types + tags), (b)
circuit intent (rung grouping, branch topology — which pins connect to
which), (c) the port-ID convention for every symbol type used, which
`CLAUDE.md` states plainly is **not standardized across the library** (per
IEC, per component type — numeric, IEC non-sequential, semantic, or
composite pin IDs, documented per symbol factory). This last point is the
real risk surface, DSL or no DSL: an LLM has no way to derive `nc_contact`'s
pin IDs (`"1"`, `"2"`) or the SPDT's (`"11"/"12"/"14"`) from general IEC
knowledge or from the symbol's *name* — it must be fed `docs/LLM_REFERENCE.md`
(the port-ID catalog CLAUDE.md points to) or the exact factory docstring
verbatim, every time.

Compared to raw coordinate/SVG generation (the seed conversation's known
failure mode — floating-point drift, off-grid misalignment, spatial
hallucination with no error signal), generating Schematika builder calls
*is* meaningfully safer, but the DSL wrapper contributes nothing to that
safety — the safety comes entirely from Schematika's own typed, validated
API surface that already exists:

- A hallucinated factory name, tag-prefix rule, or nonexistent port ID
  raises immediately (`AttributeError`/`KeyError`/`CircuitValidationError`)
  at `build()` time, before any SVG is written. This is a loud, catchable
  failure — exactly the kind a generate → run → feed-traceback-back →
  regenerate loop handles well, and the spike's problem statement
  explicitly says runtime cost is not a constraint, so that loop is cheap
  to run.
- A **wrong-but-valid** topology (branch attached to the wrong pin,
  wrong `position` direction) does not raise. It produces a rendered
  diagram that is geometrically fine and electrically wrong — a semantic
  error, not a coordinate error. This failure mode is identical whether the
  LLM writes direct `CircuitBuilder` calls or Cursor-DSL calls; it is not
  something either form can catch automatically without a
  netlist-equivalence check (out of scope here; see `svg-geometry-linter`
  and `constraint-solver` tracks for the layout-quality side of this, and
  note that a *topology* diff against the source netlist — not a geometry
  lint — is what would actually catch it).
- Wire-label-count mismatches (`WireLabelMismatchError`, per
  `examples/02_dol_starter.py:35-36`) are a Schematika-specific hazard
  independent of DSL choice: the exact number of vertical wire segments is
  a rendering detail not visible from the builder calls themselves, so an
  LLM (or a human) can only get this right by building once and reading the
  error/render, not by reasoning about the script text.

So: not a different failure mode from raw-coordinate generation so much as
a *narrower* one — floating-point/visual hallucination is eliminated
because there are no floats to hallucinate in the common case, but
topology-level hallucination (wrong pin, wrong branch) remains and is
undetectable except by rendering and reviewing, same as today.

### 4. Would a new `schematika.layout_dsl` module be worth it?

No, as designed. It would re-implement, under new method names, exactly the
`relative_to` + `position` + `spacing` primitives `CircuitBuilder` and
`PIDBuilder` already expose, for a benefit that the byte-identical-output
experiment above shows is roughly zero for the case (linear chains) where
Schematika's existing API is already terse, and *negative* for the case
(branches, cross-builder refs) where the cursor's own hidden state is a new
place to go wrong that named refs aren't.

It would also sit awkwardly against `docs/API_STYLE.md`'s verb rules
(`add_<noun>` / `set_<noun>` / `build` / `render` / `write` / `compile` —
no bare `.right()`/`.down()` fluent verbs), meaning a real implementation
would either violate the style guide or need to be scoped as
explicitly-not-a-public-API surface, adding a maintenance category with no
matching payoff.

**What is worth pursuing** (not a new module, no engineering cost): treat
direct `CircuitBuilder`/`PIDBuilder` calls, using the `relative_to`/
`position`/`offset` kwargs that already exist, as the LLM's target
language. That needs a curated prompt package (symbol factory list +
`docs/LLM_REFERENCE.md` port-ID table + a couple of worked examples from
`examples/`), not new source under `src/schematika/`. The generate → `uv
run` → catch exception → feed traceback back → regenerate loop is cheap
here specifically because the spike's own problem statement rules out
runtime cost as a concern. This is a prompting/tooling exercise, not a
`layout_dsl` module — and it still can't validate topology correctness, only
syntactic/referential correctness, so a rendered-diagram review step stays
mandatory regardless.

## Files

- `research/layout/llm-dsl-pipeline/layout_dsl_sketch.py` — the `Cursor`
  prototype (real Schematika types, not schemdraw's).
- `research/layout/llm-dsl-pipeline/a_today_direct.py` — today's direct API,
  runnable.
- `research/layout/llm-dsl-pipeline/b_relative_dsl_version.py` — same rung
  via the Cursor sketch, runnable; output is byte-identical to (a).
- `research/layout/llm-dsl-pipeline/output/` — rendered SVGs from both,
  gitignored by the repo-wide `*.svg` rule (`.gitignore:7`); not committed.
  Regenerate with `uv run python research/layout/llm-dsl-pipeline/a_today_direct.py`
  and `..._b_relative_dsl_version.py`, then `diff` the two SVGs to reproduce
  the byte-identical result cited above.
