# Architecture

One row per top-level package. The layering rule (below the table) is the contract; the file-role convention (`model.py` / `builder.py` / `renderer.py`) is the aspiration.

## Packages

| Package | Purpose | Entry point | Returns | External deps | Layer |
|---|---|---|---|---|---|
| `core` | Geometry, SVG primitives, bounding boxes, exceptions, state threading | `Point`, `Element`, `CircuitValidationError` | pure values | none | 0 |
| `catalog` | Layer-1 identity: typed IDs, refs, frozen specs, `Wire`, `BOMRow`, `ResolvedCatalog`, `Catalog` builder. `Route` + `route_to_wires` provide the reusable multi-point-signal primitive (a signal through N concrete pins) that decomposes into 2-point `Wire`s; `PinRef.connector` is optional so an endpoint may be a connector pin, a terminal-block pin, or a PLC channel. | `Catalog` (unified mutable builder for devices + cable instances; `DeviceCatalog`/`CableInstanceRegistry` are deprecated subclasses) | frozen dataclasses | none | 1 |
| `electrical` | IEC 60617 schematic builder | `CircuitBuilder.build()` | `BuildResult` | `core`, `catalog` | 2 |
| `pid` | ISO 14617 / ISA 5.1 P&ID builder | `PIDBuilder.build()` | `PIDBuildResult` | `core` | 2 |
| `pcb` | SKiDL circuit to Schematika connector schematic | `build(circuit, mapping)` | `PCBBuildResult` | `core`, `electrical`; `skidl` optional | 2 |
| `cable` | Cable harness drawing builder. `CableBuilder` (catalog-driven) produces a frozen `CableBuildResult`; `result_to_drawing` bridges it to the WireViz renderer, propagating per-wire color and length. The legacy `build_cable_drawings` free-function path remains until Phase 2b's cutover. | `build_cable_drawings()` / `CableBuilder.build()` | `list[CableDrawing]` / `CableBuildResult` | `core`, `catalog` | 2 |
| `block` | Block diagram builder | `BlockDiagram.render(path)` (to split into `build`+`write`) | `None` (side-effect; to be fixed) | `core` | 2 |
| `rendering.typst` | Optional PDF compilation via Typst | `TypstCompiler.compile` | writes PDF | `typst` optional | 3 |
| `mcp` | Optional MCP server wrapper | `run_server()` | side-effect | `mcp` optional | 3 |
| `project` (single file) | Multi-page project container, consumes everything | `Project.build()` / `Project.write(path)` | writes artefacts | all above | 4 |

Layer 0 is purest (no siblings, no deps). Layer 4 is the shell.

## One-way dependency rule

- A package at layer N may import from layers 0 to N-1, never sideways and never upward.
- `core` never imports from any other schematika package.
- Domain packages (`electrical`, `pid`, `pcb`, `cable`, `block`) never import from each other and never from `project`.
- Only `project.py` imports from domain packages. No domain package imports from `project.py`.
- `rendering.typst` and `mcp` are optional shells. They are allowed to import domain packages but no domain package imports them.

The import-linter contract in `pyproject.toml` enforces this. Adding a cross-package import will fail pre-commit.

## Return-type rule

Every domain builder returns a frozen `*BuildResult` dataclass. Not `None`, not a bare `list`, not `Project`. The one remaining exception (`block/BlockDiagram.render` returning `None`) is tracked as API debt and will be normalized. (`cable/builder.py` now returns `CableBuildResult`; the legacy `build_cable_drawings` free function returns `list[CableDrawing]` and will be removed in Phase 2b.)

See [API_STYLE.md](API_STYLE.md) for method naming, parameter glossary, and docstring format.

## File-role convention (aspirational)

Each domain package should contain:

- `model.py` — frozen dataclasses that describe the domain.
- `builder.py` — the mutable builder and its `build()` method.
- `renderer.py` — pure functions that turn `*BuildResult` into SVG elements.
- `validation.py` — post-build consistency checks (overlap, boundary, label mismatch).
- `errors.py` — the domain's exception hierarchy.

`cable/` currently matches this shape. `electrical/` and `pid/` do not (electrical has `system.system`, `utils/`, `layout/`; pid has `symbols/`, `connections`, `constants`). Convergence is a goal, not a current invariant.

## Mutable state

Seven places are allowed to hold mutable state. Everything else is frozen.

- `Catalog` (`catalog/registry.py`) — unified device + cable-instance builder; `DeviceCatalog` and `CableInstanceRegistry` are deprecated subclasses.
- `CircuitBuilder` (`electrical/builder.py`)
- `Harness` (`electrical/harness.py`) — Layer-2 multi-point `route()` collector that batch-allocates PLC channels at `build()`.
- `PIDBuilder` (`pid/builder.py`)
- `CableBuilder` (`cable/builder.py`)
- `BlockDiagram` (`block/model.py`)
- `Project` (`project.py`)

The audit found eleven more mutable dataclasses that should be frozen (tracked as tech debt, not invariants).

`Harness` (mutable builder, Layer 2) collects multi-point `route()` declarations — concrete pins plus unallocated `Plc(signal_type, suffix)` channel requests — and at `build()` batch-allocates PLC channels against a rack, decomposing each route into 2-point `Wire`s (via `route_to_wires`) and emitting `PlcAssignment` records. It is built alongside the legacy `ConnectionRow`/`resolve_plc_references` pipeline (retired in a later sub-phase). `Harness.add_field_devices` expands `FieldDevice`s into routes, delegating terminal-pin numbering to the existing `generate_field_connections` allocator and deriving PLC channel requests from each pin's `PLC:` reference, running alongside the legacy `ConnectionRow` pipeline (retired in a later sub-phase). `plc_csv_rows` renders the PLC connection report directly from a `HarnessBuildResult` — it adapts `PlcAssignment`s into synthetic `ConnectionRow`s and delegates to `generate_plc_report_rows`; the terminal-strip CSV port is deferred to the cutover because it also needs terminal metadata and the panel-side registry.

`Project` (Layer 4) exposes two additive chaining methods that delegate to an owned `Harness`: `route(*waypoints, net=...)` buffers a multi-point connection declaration and `add_wires(wires)` buffers pre-built `Wire`s. Both are resolved at build time via `_resolve_harness()` into a `HarnessBuildResult`. This path runs alongside the existing legacy `ConnectionRow` pipeline, which will be retired in a later sub-phase.
