# Open Questions and Resolved Decisions

Items deliberately deferred, plus user-resolved decisions captured here
so other docs can be kept in sync.

## Resolved decisions

### HTML-table labels — kept

`label=<<TABLE>...</TABLE>>` HTML-table labels for multi-port nodes
are in scope. They are a Graphviz authoring feature (used inside DOT
to describe multi-port nodes), not output HTML; they don't conflict
with the no-hyperlinks rule. The `record` shape alternative is not
adopted.

### Containment schema — frozen dataclass

`ContainerSpec` is a frozen dataclass in `overview/model.py`, not a
raw dict. Keys in the containment dict are stable ids; `ContainerSpec`
carries `label`, `kind`, `parent`, `circuits`. See `05-overview-api.md`
for the resolved shape.

### Signal-kind palette — power and signal, grow on demand

v0 defines two kinds: **`power`** and **`signal`**. Other kinds (CAN,
safety, ethernet, RS-485, 4–20 mA, …) are deferred — added to the
palette only when a consumer actually needs them. Default classifier
matches power-pattern names (e.g. `+24V`, `VCC`, `PWR`, `L1/L2/L3`,
`PE`, `N`) → `power`; everything else → `signal`. Colors: pick two
accessible, distinguishable values during v0 implementation; record
them in `overview/__init__.py` constants.

## Still open

### Field-device default container

Field devices land in a synthetic top-level `"<system>"` container by
default; the consumer can override by adding a `ContainerSpec` for
"Field" and listing field-device ids. Confirm naming during v0
implementation (`<system>` vs `<root>` vs an empty-string id).

### Containment declaration site

The consumer lists every circuit key twice — once at
`project.add_circuit("key", ...)` and once in
`ContainerSpec.circuits`. The two lists drift silently if a circuit
is added to one and not the other; the extractor's
"every-circuit-must-be-in-exactly-one-container" check catches drift
at Overview-build time, not at registration.

Cleaner alternative for v1+: extend `Project.add_circuit(...)` with a
`container: str | None = None` keyword that records containment at
registration. Defer per user — "we can make it more streamlined later"
— and don't modify `Project` for v0.

### Public accessor for `Project` results

Overview reads `project._results`, `project._terminals` — all private.
Any internal refactor of `Project` breaks Overview without warning. v0
isolates the reads behind one adapter in `overview/extractor.py` so the
blast radius is two lines.

Trigger to revisit: the first time `Project`'s internal storage shape
needs to change. At that point either add public accessors and migrate
Overview, or freeze the private contract by giving `Project` a small
public read-only "results view."

### Port ordering hints

Skipped in v0. R&D_overview.md flags this as the one place per-unit
human input genuinely helps (group ports by destination to reduce wire
crossings). Defer; revisit after seeing v0 output. Likely lives as an
optional argument to `overview.build()` or a per-unit hint declared on
the consumer side.

### Where the consumer's build hooks Overview

Two possibilities:

- A 3rd entry-point script (`src/overview.py`) in the consumer that
  imports `setup_project()` and calls `schematika.overview.build(...)`.
  Mirrors `cabinet.py` / `cables.py`.
- Inline at the end of `cabinet.py:main()`.

Both are fine. v0 lets the consumer choose. Default recommendation: a
3rd entry-point script, since that's the existing idiom.

### v0 testing honesty — no real PCB consumer

`auxillary_cabinet_v3` has no PCBs and only one cabinet. The
nested-containment code path (cabinet → PCB → sub-PCB) is therefore
**only ever exercised against a synthetic fixture** at v0. The real
consumer exercises a degenerate case: one container, no nesting. This
falls short of R&D_overview.md's "first iteration" spec ("one cabinet
containing a Juicebox containing a BMU, with two or three peer
cabinets outside").

v0 plan: ship with the synthetic fixture, mark "verified against real
nested data" as a v0.5 gate, clearly note this in the implementation
PR. Update the v0 DoD in `01-vision-and-scope.md` to match what's
actually verifiable.

### Streamlining `build_circuits()` ordering

v0 picks Option 1 (`overview.build()` auto-calls
`project.build_circuits()` if results are empty). Streamline later by
adding `project.has_built_circuits()` or an idempotent
`project.ensure_built()`. Defer until the rough edge actually bites.

### Signal-tracing UX

R&D_overview.md (deferred section, line 124) proposes a signal-tracing
tool: "where does +24V_AUX go?" Same underlying graph, different UI.
Out of scope for v0; the data Overview produces is the right input for
it. No design needed yet — note it so it isn't forgotten.

### Performance / scale budget

R&D_overview.md doesn't specify a target diagram size:

- `auxillary_cabinet_v3` is ~11 circuits with low hundreds of wires —
  ortho routing handles this comfortably.
- A future system with multiple cabinets, several PCBs each, and many
  field devices could push to thousands of wires. Trapezoid-table
  overflow (Graphviz issue #1880) is a real concern at that scale.

v0 doesn't need a hard budget but the validator's page-size sanity
check should bound the SVG canvas so degeneracy is caught early.
Capture an actual measurement on the first real run and pin it as the
baseline.

### When to migrate to ELK

R&D_overview.md flags this: if R&D requires physically-accurate port
placement after seeing v0, that's the trigger to migrate. The data
model in `overview/model.py` is compatible with ELK input — migration
would mean writing a new emitter, not redoing extraction.

Defer the decision. Don't pre-build for ELK.

### Shared data module across domains

Tabled. Re-evaluate after the first end-to-end v0 lands and the
canonical shapes have been validated by use. Trigger to lift into
`core/datamodel/`: a second consumer pattern emerges that doesn't use
`Project` as the single orchestrator.
