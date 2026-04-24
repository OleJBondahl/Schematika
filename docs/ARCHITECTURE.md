# Architecture

One row per top-level package. The layering rule (below the table) is the contract; the file-role convention (`model.py` / `builder.py` / `renderer.py`) is the aspiration.

## Packages

| Package | Purpose | Entry point | Returns | External deps | Layer |
|---|---|---|---|---|---|
| `core` | Geometry, SVG primitives, bounding boxes, exceptions, state threading | `Point`, `Element`, `CircuitValidationError` | pure values | none | 0 |
| `catalog` | Device and cable catalog data | `DeviceCatalog`, `CableRegistry` | frozen dataclasses | none | 1 |
| `electrical` | IEC 60617 schematic builder | `CircuitBuilder.build()` | `BuildResult` | `core`, `catalog` | 2 |
| `pid` | ISO 14617 / ISA 5.1 P&ID builder | `PIDBuilder.build()` | `PIDBuildResult` | `core` | 2 |
| `pcb` | SKiDL circuit to Schematika connector schematic | `build(circuit, mapping)` | `PCBBuildResult` | `core`, `electrical`; `skidl` optional | 2 |
| `cable` | Cable harness drawing builder | `build_cable_drawings()` | `list[CableDrawing]` (to be `CableBuildResult`) | `core`, `catalog` | 2 |
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

Every domain builder returns a frozen `*BuildResult` dataclass. Not `None`, not a bare `list`, not `Project`. The two current exceptions (`cable/builder.py` returning `list[CableDrawing]`, `block/BlockDiagram.render` returning `None`) are tracked as API debt and will be normalized.

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

Four places are allowed to hold mutable state. Everything else is frozen.

- `CircuitBuilder` (`electrical/builder.py`)
- `PIDBuilder` (`pid/builder.py`)
- `BlockDiagram` (`block/model.py`)
- `Project` (`project.py`)

The audit found eleven more mutable dataclasses that should be frozen (tracked as tech debt, not invariants).
