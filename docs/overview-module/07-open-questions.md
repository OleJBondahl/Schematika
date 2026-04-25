# Open Questions

Items deliberately deferred or unresolved. Revisit before/during
implementation.

## HTML-table labels — confirm scope

User said "no html stuff." Two interpretations:

- **(A)** No HTML hyperlinks (`URL` / `HREF` / `target`), but
  HTML-table labels for multi-port nodes are fine. They are a Graphviz
  authoring feature (used inside DOT to describe multi-port nodes), not
  output HTML.
- **(B)** No HTML *anywhere*, including HTML-table labels. Use `record`
  shape instead (`label="<f0> VCC | <f1> GND"`).

Current docs assume **(A)**. HTML-table labels give per-cell coloring
useful for grouping signal kinds, multi-row cells, per-cell alignment.
`record` shape supports ports too but is less flexible.

**Action:** confirm with user before implementation. If (B), switch
emitter to `record` and drop the HTML-related sections of
`04-graphviz-reference.md`.

**User Choice** A

## Containment schema details

Working sketch in `05-overview-api.md`:

```python
CONTAINMENT = {
    "Auxiliary Cabinet": {"kind": "cabinet", "circuits": [...]},
    "BMU PCB":           {"kind": "pcb", "parent": "Juicebox PCB",
                          "circuits": [...]},
}
```

Open: a frozen dataclass (`ContainerSpec`) instead of a raw dict?
Probably yes for v0.5+; raw dict is fine for v0 prototyping.

Open: how do field devices appear in containment? Default to a
synthetic top-level "Field" container, or list them explicitly? v0
proposal: synthetic default, overridable.

## Signal-kind palette

Lock in:

- Standard kinds. Initial set: `power`, `can`, `safety`, `signal`.
  Anything else now (Ethernet, RS-485, analog 4–20 mA)? Or grow on
  demand?
- Colors. Need accessible / distinguishable palette. Default TBD.
- Default classifier rules (name-pattern matchers).

## Port ordering hints

Skipped in v0. R&D_overview.md flags this as the one place per-unit
human input genuinely helps (group ports by destination to reduce wire
crossings). Defer; revisit after seeing v0 output.

## Where the consumer's build hooks Overview

Two possibilities:

- A 3rd entry-point script (`src/overview.py`) in the consumer that
  imports `setup_project()` and calls `schematika.overview.build(...)`.
  Mirrors `cabinet.py` / `cables.py`.
- Inline at the end of `cabinet.py:main()`.

Both are fine. v0 lets the consumer choose; pick one for
`auxillary_cabinet_v3` when prototyping and document the choice.

## PCB consumer for testing

`auxillary_cabinet_v3` has no PCBs. The PCB code path will need a
synthetic test fixture (in `tests/fixtures/` or similar) until a real
consumer with PCBs exists.

## Streamlining `build_circuits()` ordering

User accepted v0 calling `project.build_circuits()` from inside
Overview (or requiring the consumer to call it first), as long as
documented. Streamline later by:

- Adding an explicit `project.has_built_circuits()` predicate, or
- A `project.ensure_built()` idempotent call.

Defer until the rough edge actually bites. Don't pre-build for it.

## When to migrate to ELK

R&D_overview.md flags this: if R&D requires physically-accurate port
placement after seeing v0, that's the trigger to migrate. The data
model in `overview/model.py` is compatible with ELK input — migration
would mean writing a new emitter, not redoing extraction.

Defer the decision. Don't pre-build for ELK.

## Shared data module across domains

Tabled. Re-evaluate after the first end-to-end v0 lands and the
canonical shapes have been validated by use against
`auxillary_cabinet_v3` plus a synthetic PCB fixture. Trigger to lift
into `core/datamodel/`: a second consumer pattern emerges that doesn't
use `Project` as the single orchestrator.
