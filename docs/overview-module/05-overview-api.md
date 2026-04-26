# Overview API

Proposed shape for the new `src/schematika/overview/` package. Optimized
for the consumer pattern in
[`03-consumer-pattern.md`](03-consumer-pattern.md).

## Public entry point

```python
# src/schematika/overview/__init__.py
def build(project: Project, *, options: OverviewOptions | None = None) -> None:
    """Render a Graphviz system diagram from a built Project.

    Auto-calls ``project.build_circuits()`` if ``project._results`` is
    empty.
    """
```

One positional argument (the project, the identity) followed by a
single keyword-only `options` bundle. Mirrors
`CircuitBuilder.build(*, options: BuildOptions | None = None)`
(`src/schematika/electrical/builder.py:1045`), the post-C2d-2
prevailing style: every `*Options` is a frozen, slotted, kw-only
dataclass declared in `schematika.core.options` (the wave bundled
`add_terminal`, `add_symbol`, `add_spdt`, `add_reference`,
`add_equipment`, and `build` to comply with `max-args = 8`).

```python
# src/schematika/overview/options.py
@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewOptions:
    """Options for :func:`schematika.overview.build`."""

    containment: Mapping[str, ContainerSpec]   # required
    output_path: str | Path                    # required
    palette: Mapping[str, str] | None = None
    signal_kind: Callable[[ConnectionKey], str] | None = None
```

`OverviewOptions` lives in `schematika.overview.options`, **not** in
`schematika.core.options`. The `BuildOptions`/`SymbolConfig`/etc. bundles
are co-located in `core/options.py` because the types they reference
(`BuildResult`, `InternalDevice`, `Side`, …) are themselves in
`schematika.electrical.*`, and grimp/import-linter sees those
TYPE_CHECKING imports as a real edge from `core` to `electrical`. The
`overview-leaf` contract forbids the inverse — `electrical|pcb|cable|
pid|core` may not import `overview` at any depth — so a
`core.options.OverviewOptions` referencing `overview.model.ContainerSpec`
would break the contract transitively (`electrical → core.options →
overview.model`). Keeping `OverviewOptions` inside the overview package
keeps the leaf contract clean. Two fields are required (no defaults):
`containment` and `output_path`. `palette` and `signal_kind` default to
`None` (the emitter falls back to the default palette + name-pattern
classifier).

`ConnectionKey` is a small frozen dataclass defined in
`overview/model.py` with fields `from_unit`, `from_port`, `to_unit`,
`to_port` (all `str`). The classifier sees the raw connection identity
and returns a kind string; the extractor attaches the result to the
emitted `Wire`. This avoids the chicken-and-egg of a callback that
takes a `Wire` whose `kind` field is what we're trying to compute.

### Call-site shape

```python
from schematika import overview
from schematika.overview import ContainerSpec, OverviewOptions

overview.build(
    project,
    options=OverviewOptions(
        containment=CONTAINMENT,
        output_path="src/system.svg",
    ),
)
```

`OverviewOptions` is re-exported from `schematika.overview` so consumers
need only one import path.

`overview.build(project)` (no `options=`) raises `TypeError` because
`containment` and `output_path` are required fields on
`OverviewOptions`. No back-compat shim — same hard-break stance as
C2d-2.

Why standalone, not on `Project`:

- Mirrors the existing `setup_project()` reuse idiom
  (`auxillary_cabinet_v3/src/cables.py` imports and calls
  `cabinet.py:setup_project`). A new `src/overview.py` script in the
  consumer fits the same pattern.
- Decouples from `Project`'s mutable builder interface — Overview is
  read-only analysis.
- Makes the data-model boundary explicit: Overview consumes a `Project`
  and a containment dict, produces an SVG. Nothing else.

## Internal package layout

```
src/schematika/overview/
  __init__.py        # re-exports build, OverviewOptions, ContainerSpec, errors
  errors.py          # OverviewError(ValueError) base + 3 subclasses
  model.py           # frozen dataclasses: Unit, Wire, ContainerSpec, ConnectionKey
  options.py         # OverviewOptions (frozen, slots, kw_only) — see "Public entry point"
  extractor.py       # walks project._results + project._external_connections, returns model
  emitter.py         # turns model into DOT, shells out to `dot -Tsvg`
  validate.py        # SVG-level structural checks (consumed by scripts/system_diagram_review.py)
```

`options.py` is intentionally a separate module rather than co-located
in `core/options.py` — see the rationale under "Public entry point"
above.

## Package layer

`overview/` sits next to the other domain packages (`electrical/`,
`pcb/`, `cable/`, `pid/`), not inside `core/`:

- It calls `subprocess.run(['dot', ...])` — a violation of CLAUDE.md
  invariant 1, which forbids I/O in `core/`.
- It imports from domain packages and from `project.py` — a violation
  of CLAUDE.md invariant 2, which forbids `core/` from importing from
  domain packages.

Therefore `overview/` is **a new domain package**. The import-linter
contract should be extended to forbid the inverse: no domain package
(`electrical`, `pcb`, `cable`, `pid`) and no module under `core/` may
import from `overview`. Add a clause to `.importlinter`:

```ini
[importlinter:contract:overview-leaf]
name = overview is a leaf — nothing imports from it
type = forbidden
source_modules =
    schematika.core
    schematika.electrical
    schematika.pcb
    schematika.cable
    schematika.pid
forbidden_modules =
    schematika.overview
```

`overview` may consume `project.py`. That's allowed because Overview's
job is precisely to compose all the domain results held by `Project`.

## Exceptions

All errors raised by Overview inherit from `OverviewError(ValueError)`
defined in `overview/errors.py`. Mirror the existing pattern in
`pid/errors.py`:

```python
class OverviewError(ValueError):
    """Base exception for the schematika.overview module."""

class OverviewContainmentError(OverviewError):
    """Containment input is malformed or inconsistent."""

class OverviewExtractionError(OverviewError):
    """Project state could not be turned into a valid Unit/Wire graph."""

class OverviewRenderError(OverviewError):
    """Graphviz invocation failed or produced unexpected output."""
```

Per CLAUDE.md red flags, no new bare `ValueError` for domain validation
— always one of these.

## Data model (Overview-local, not shared)

```python
@dataclass(frozen=True)
class Unit:
    id: str                       # stable identity, used as DOT node id
    label: str                    # display name (may differ from id)
    parent: str | None            # id of containing Unit, or None for top
    is_container: bool            # True → renders as cluster, not as node
    ports: tuple[str, ...]        # render order; empty when is_container
    kind: str                     # cabinet | terminal | field_device | ...

@dataclass(frozen=True)
class Wire:
    from_unit: str
    from_port: str
    to_unit: str
    to_port: str
    kind: str                     # "power" | "signal" (extensible)

@dataclass(frozen=True)
class ConnectionKey:
    """Identity of a wire before classification — passed to signal_kind callbacks."""
    from_unit: str
    from_port: str
    to_unit: str
    to_port: str
```

`ports` on a container `Unit` is always empty: clusters can't carry
ports in Graphviz (see `04-graphviz-reference.md` cluster section).
The extractor enforces this at validation time.

These types live inside `overview/`. They are deliberately **not**
promoted to a shared `core/datamodel/` module. If a second consumer
pattern emerges that doesn't use `Project` as the single orchestrator,
*that's* the trigger to lift them. Designing the shared shapes against
one example is premature.

The `R&D_overview.md` data sketch had `drawing: "path/to/pdf"` fields
on both units and wires for SVG hyperlinks. v0 drops those fields per
the no-hyperlinks decision in `01-vision-and-scope.md`. If hyperlinks
are reinstated later, both fields become optional `str | None` and the
emitter adds `URL` / `HREF` accordingly.

## Containment input

The consumer declares containment at the top of their build script:

```python
CONTAINMENT = {
    "cabinet_aux": ContainerSpec(label="Auxiliary Cabinet", kind="cabinet"),
}
```

`ContainerSpec` is a frozen dataclass in `overview/model.py` with three
fields: `label`, `kind`, and optional `parent`. Keys are **stable ids**;
`label` is the human-readable display name; `parent` references another
id. Decoupling id from label means renaming a label doesn't break parent
refs.

The container with `kind="cabinet"` is special: every terminal that has
a row in `project._external_connections` lands inside it. Field devices
(the non-cabinet side of every row) sit at the top level outside any
cluster. Cabinet-internal wires are not consumed — only the boundary
crossings render.

Validation rules (raise `OverviewContainmentError`):

- Every `parent` must reference a defined container id.
- Cycles in the containment graph fail with the cycle path in the
  message.
- At most one container may have `kind="cabinet"`. Multi-cabinet support
  is a v0.5+ concern.

There is no list of circuits per container. The consumer no longer has
to enumerate which circuits live where; the extractor walks
`project._external_connections` and groups by terminal id.

## Ordering rule

**`project.build_circuits()` must have run before Overview emits.**
Reading `project._results` before circuits are built returns an
incomplete graph.

v0 picks one of two implementations and sticks with it:

- **Option 1 (preferred):** `overview.build()` calls
  `project.build_circuits()` itself if results are empty, then proceeds.
  This is what the user accepted as "good enough for now."
- **Option 2:** `overview.build()` requires the consumer to have
  already called `build_circuits()`, and raises `OverviewError` with a
  pointer to the docs if results are empty.

Pick Option 1 for v0 implementation; document the auto-call clearly
in the function's docstring. Streamlining (e.g. a public
`project.has_built_circuits()` predicate, or an idempotent
`project.ensure_built()`) is deferred — see `07-open-questions.md`.

## Reading `project._results` is a tight coupling

Overview reads private attributes of `Project` (`_results`,
`_external_connections`, `_terminals`). This is intentional for v0
(no public accessor exists) but creates a fragile contract: any
refactor of `Project`'s internal state shape breaks Overview silently.

Mitigations baked into v0:
- Every read goes through one tiny adapter in `extractor.py` —
  `_get_results(project)`, `_get_external_connections(project)`,
  `_get_terminals(project)`. If the storage shape ever changes, only
  three call sites need updating.
- The extractor asserts the shape it expects (`isinstance` checks on
  the read values) and raises `OverviewExtractionError` with a
  pointer to the docs if it changes shape.

Long-term mitigation (see `07-open-questions.md`): add public
accessors on `Project` and migrate Overview to use them.

## Signal-kind classification

v0 ships two kinds: `power` and `signal`. The classifier and palette
are extension points — adding `can`, `safety`, etc. later means
extending the palette dict and the classifier rules, not the API
shape.

Default classifier (name-pattern based):
- Names matching `+24V`, `+12V`, `VCC`, `PWR`, `L1` / `L2` / `L3`, `N`,
  `PE`, `GND` → `power`.
- Everything else → `signal`.

The classifier is consumer-overridable via
`OverviewOptions.signal_kind` because naming conventions vary across
projects. Default palette: pick two accessible, distinguishable colors
during implementation; record them as constants in
`overview/__init__.py`.

## What Overview does NOT do

- No mutation of `Project` state.
- No new fields on `BuildResult` / `PCBBuildResult` / `CableDrawing`.
- No HTML hyperlinks (`URL` / `HREF` / `target`).
- No PDF compilation. SVG only.
- No replacement for `block_diagram.py` in any consumer. The block
  module is out of scope per design (see `02-data-sources.md`);
  Overview is independent.
- No multi-repo composition.

## Consumer integration sketch

```python
# In auxillary_cabinet_v3/src/overview.py (new file)
from cabinet import setup_project
from schematika import overview
from schematika.overview import ContainerSpec, OverviewOptions

CONTAINMENT = {
    "cabinet_aux": ContainerSpec(
        label="Auxiliary Cabinet",
        kind="cabinet",
        circuits=(
            "power_switching", "psu", "distribution",
            "pumps", "pump_controll", "pump_feedback",
            "fans", "fan_controll", "fan_feedback",
            "valve_control", "plc_power",
        ),
    ),
    # Field devices land in the synthetic "<system>" container by
    # default. Override here if explicit grouping is wanted.
}

if __name__ == "__main__":
    project = setup_project()
    overview.build(
        project,
        options=OverviewOptions(
            containment=CONTAINMENT,
            output_path="src/system.svg",
        ),
    )
```

Same shape as `cables.py`: import shared setup, run, hand off to a
domain-specific entry point. Overview auto-calls `build_circuits()` if
results are empty.

Validator sidecar: the emitter writes
`src/system.svg.expected.json` next to the SVG, holding the canonical
counts and structural summary the validator checks against. The
sidecar is the **emitter's record of what it intended to produce**;
the validator compares the rendered SVG to it. The expected counts in
the sidecar are derived from the in-memory `(units, wires)` model,
not re-extracted from `project._results`, so the comparison cannot be
tautological. If the model and the SVG disagree, the rendered SVG is
the side that's wrong.
