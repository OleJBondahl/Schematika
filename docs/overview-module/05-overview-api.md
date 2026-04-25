# Overview API

Proposed shape for the new `src/schematika/overview/` package. Optimized
for the consumer pattern in
[`03-consumer-pattern.md`](03-consumer-pattern.md).

## Public entry point

```python
# src/schematika/overview/__init__.py
def build(
    project: Project,
    containment: dict[str, ContainerSpec],
    output_path: str | Path,
    *,
    palette: dict[str, str] | None = None,
    signal_kind: Callable[[Wire], str] | None = None,
) -> None:
    """Render a Graphviz system diagram from a built Project."""
```

Standalone function in a new `overview/` package. **Not** a method on
`Project`.

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
  __init__.py        # public build() function
  model.py           # frozen dataclasses: Unit, Wire, Container, ContainerSpec
  extractor.py       # walks project._results + project._external_connections, returns model
  emitter.py         # turns model into DOT, shells out to `dot -Tsvg`
  validate.py        # SVG-level structural checks (consumed by scripts/system_diagram_review.py)
```

## Data model (Overview-local, not shared)

```python
@dataclass(frozen=True)
class Unit:
    id: str
    label: str
    parent: str | None
    is_container: bool       # True → renders as cluster, not as node
    ports: tuple[str, ...]   # render order
    kind: str                # cabinet | pcb | device | terminal | ...

@dataclass(frozen=True)
class Wire:
    from_unit: str
    from_port: str
    to_unit: str
    to_port: str
    kind: str                # power | can | safety | signal | ...
```

These types live inside `overview/`. They are deliberately **not**
promoted to a shared `core/datamodel/` module. If a second consumer
pattern emerges that doesn't use `Project` as the single orchestrator,
*that's* the trigger to lift them. Designing the shared shapes against
one example is premature.

## Containment input

The consumer declares containment at the top of their build script:

```python
CONTAINMENT = {
    "Auxiliary Cabinet": {
        "kind": "cabinet",
        "circuits": ["power_switching", "psu", "pumps", "fans", ...],
    },
    "BMU PCB": {
        "kind": "pcb",
        "parent": "Juicebox PCB",
        "circuits": ["bmu_logic"],
    },
    "Juicebox PCB": {
        "kind": "pcb",
        "parent": "Auxiliary Cabinet",
        "circuits": ["juicebox"],
    },
}
```

Schema lives in `overview/model.py:ContainerSpec`. Validation rules:

- Every circuit key listed must exist in `project._results`.
- Every `parent` must reference a defined container.
- Cycles in the containment graph fail loudly with a clear message.
- Unreferenced circuits (in `project._results` but in no container)
  default to a synthetic root container `"<system>"` so they're visible.

## Ordering rule

**Overview must be called after `project.build_circuits()`.** Reading
`project._results` before circuits are built returns an incomplete
graph.

v0 documents this rule and asserts it. If `_results` is empty when
`build()` is called, raise with a clear message pointing at this doc.

User has accepted that v0 may call `project.build_circuits()` from
inside Overview itself (or require the consumer to call it first), as
long as it's documented. Streamlining (e.g. `project.has_built_circuits()`
predicate or `project.ensure_built()` idempotent call) is deferred.

## Signal-kind classification

v0 accepts an optional `signal_kind: Callable[[Wire], str]` and a
palette dict. Defaults:

- Default classifier: name-pattern based. E.g. tag/pin name contains
  `"PWR"` / `"VCC"` / `"+24V"` → `"power"`; `"CAN"` → `"can"`;
  `"ESTOP"` / `"SAFETY"` → `"safety"`; everything else → `"signal"`.
- Default palette: TBD (see
  [`07-open-questions.md`](07-open-questions.md)).

The classifier is consumer-overridable because naming conventions vary
across projects.

## What Overview does NOT do

- No mutation of `Project` state.
- No new fields on `BuildResult` / `PCBBuildResult` / `CableDrawing`.
- No HTML hyperlinks (`URL` / `HREF` / `target`).
- No PDF compilation. SVG only.
- No replacement for `block_diagram.py` in any consumer. The block
  module is dead code; Overview is independent.
- No multi-repo composition.

## Consumer integration sketch

```python
# In auxillary_cabinet_v3/src/overview.py (new file)
from cabinet import setup_project
from schematika import overview

CONTAINMENT = {
    "Auxiliary Cabinet": {
        "kind": "cabinet",
        "circuits": ["power_switching", "psu", "distribution",
                     "pumps", "pump_controll", "pump_feedback",
                     "fans", "fan_controll", "fan_feedback",
                     "valve_control", "plc_power"],
    },
    # field devices auto-placed at top level via containment defaulting
}

if __name__ == "__main__":
    project = setup_project()
    project.build_circuits()
    overview.build(project, CONTAINMENT, "src/system.svg")
```

Same shape as `cables.py`: import shared setup, run, hand off to a
domain-specific entry point.
