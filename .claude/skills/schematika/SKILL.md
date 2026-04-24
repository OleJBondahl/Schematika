---
name: schematika
description: Use when writing or editing code inside the Schematika repo (src/schematika/**), especially the new schematika.pcb module that bridges SKiDL to Schematika, or adding symbol factories under electrical/symbols/. Covers repo layout, the data-returning module convention, Project integration, frozen-dataclass style, and pre-commit/ty/pytest tooling.
---

# Schematika Conventions

Reference for implementation subagents working in `C:/Users/OleJohanBondahl/Documents/GitHub_ZEN/Schematika/`.

**Authoritative design spec for the `pcb/` module:** `Schematika/docs/superpowers/specs/2026-04-24-schematika-pcb-design.md`. Read it before editing `pcb/` — do not duplicate its content here.

## Repo layout

`src/schematika/` holds one package per diagram domain. New `pcb/` is a peer to these, not a child.

| Module | Responsibility |
|---|---|
| `core/` | Geometry primitives (`Point`, `Vector`, `Circle`, `Line`, `Text`), `Symbol` + `Port` dataclasses, `transform.rotate` singledispatch. Backend-agnostic. |
| `electrical/` | `CircuitBuilder`, `Circuit`, `BuildResult`, IEC 60617 symbol factories under `symbols/`. The `pcb/` output feeds back into this via `CircuitBuilder`. |
| `pid/` | P&ID diagrams (ISO 14617). Returns `PIDBuildResult`. Pattern reference for a self-contained domain module. |
| `block/` | Block diagrams. V2 `BlockDiagram` renders itself. |
| `cable/` | WireViz-backed harness drawings. Returns `list[CableDrawing]`. Single-file `renderer.py` is the only place wireviz is imported. |
| `pcb/` *(new)* | SKiDL → Schematika bridge. See spec. |
| `project.py` | `Project` class: top-level mutable builder that owns pages, circuits, and PDF compile. |

Per-module file roles (when present):

- `model.py` — frozen dataclasses (IR + result types). Pure data.
- `builder.py` — algorithm. No backend imports.
- `renderer.py` — the only file importing a foreign dep (wireviz today; `skidl` lives in `pcb/adapter.py` for the new module).
- `__init__.py` — public API exports.

## Dominant convention: modules return data, not `Project`

**Every domain module returns a dataclass or build-result; the caller assembles it into `Project`.** Follow this for `pcb/`.

| Module | Return type | Source |
|---|---|---|
| `cable` | `list[CableDrawing]` | `cable/builder.py` → `build_cable_drawings` |
| `pid` | `PIDBuildResult` (frozen) | `pid/builder.py:107` |
| `electrical` | `BuildResult` (dataclass) | `electrical/builder_models.py:175` |
| `pcb` | `PCBBuildResult` (frozen) | new, per spec |

A module that returns `Project` is wrong — rewrite it.

## `project.Project` integration

Used at `src/schematika/project.py`. Three call points matter for `pcb/`:

```python
project.add_circuit(key, builder_fn, count=1, **kwargs)  # project.py:288
project.page(title, circuit_key | list[str])             # project.py:632
project.build(output, temp_dir="temp", ...)              # project.py:820
```

`builder_fn` is **deferred** — called later with `(state, **kwargs)`, must return `BuildResult`. For `pcb/`, call `project.add_pcb(result)` — it handles the loop + default-arg closure for you:

```python
result = pcb.build(circuit, mapping, page_size=A3_LANDSCAPE)
project.add_pcb(result)
```

The import direction is `project → pcb.model` (for `PCBBuildResult`), never the reverse. `pcb/` must not import from `schematika.project`.

See references/project-integration.md for `project.add_pcb` internals and `BuildResult` fields.

## `CircuitBuilder` essential API

From `electrical/builder.py`:

```python
from schematika.electrical import CircuitBuilder

b = CircuitBuilder(state)
b.set_layout(x=0, y=0, spacing=150, symbol_spacing=50)   # line 90
b.add_terminal("X1", poles=1)                             # line 118
b.add_symbol(fuse, "F", pins=("1","2"))                   # line 355
b.add_connection(src_ref, src_port, dst_ref, dst_port)    # line 1000
result = b.build()                                        # line 1144  -> BuildResult
```

Rotation: **not a `Symbol` method.** Use the singledispatch free function `rotate(symbol, 180)` from `schematika.core.transform` (see `core/transform.py:192`; handlers exist for `Point`, `Port`, `Symbol`, etc.). The spec's informal "`Symbol.rotate(180)`" means this call.

## Symbol factory conventions

Template to copy: `src/schematika/electrical/symbols/terminals.py`.

A factory is a function that returns a `Symbol(elements=[...], ports={...}, label=...)`. The `Symbol` dataclass lives at `src/schematika/core/symbol.py:24`; `Port` at line 7.

Minimal shape:

```python
from schematika.electrical.model.core import Port, Symbol, Vector
from schematika.core.geometry import Point
from schematika.electrical.model.primitives import Text  # or core.primitives.{Circle, Line, Text}

def connector_pin(label: str = "", pin_label: str | None = None,
                  label_pos: str = "left") -> Symbol:
    elements = [...]                                     # Rect or 4 Lines, ~2x terminal box
    ports = {"1": Port("1", Point(0, 0), Vector(0, 1))}  # one port, faces inward
    return Symbol(elements=elements, ports=ports, label=label)
```

Rules for the new `electrical/symbols/connector_pins.py`:

- Signature mirrors `terminal()` (see `terminals.py:153`): `label`, `pin_label`, `label_pos`.
- Reuse text-offset constants from `terminals.py` / `model/constants.py` (e.g. `PIN_LABEL_OFFSET_X`, `TEXT_SIZE_PIN`, `TEXT_FONT_FAMILY_AUX`) — import, do not redefine.
- Export from `electrical/symbols/__init__.py` alongside `terminal`.
- Exactly one port on the inner side (opposite label). Validation in `SymbolMapping.__post_init__` enforces this.

## Frozen-dataclass style

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SymbolSlice:
    symbol: SymbolFactory
    pin_map: Mapping[str, str]

    def __post_init__(self) -> None:
        if len(self.pin_map) != 2:
            raise MultiPinSliceError(
                f"SymbolSlice.pin_map has {len(self.pin_map)} entries; "
                f"v1 requires exactly 2. Split into multiple slices."
            )
```

Principles:

- `@dataclass(frozen=True)` for every public data type.
- `__post_init__` validates at construction (fail-fast, agent-safe). Raise typed exceptions from `pcb/errors.py` (all subclass `PCBBuildError`).
- Error messages name the offending ref and state the concrete fix. The spec §Validation lists the 9 rules for `SymbolMapping`.
- No mutable state in public dataclasses. The four repo-wide mutable builders are `Circuit`, `Project`, `CircuitBuilder`, `PlcMapper`; do not add a fifth.

## Import discipline

- `src/schematika/pcb/adapter.py` is the only file in `pcb/` that imports `skidl`. Other files in `pcb/` use the IR produced by the adapter.
- Do not add `skidl` imports to any existing module.
- Do not reorder `__init__.py` imports — `electrical/__init__.py` and `electrical/model/__init__.py` have deliberate ordering with `# noqa: E402`/`# noqa: I001` comments (see root `CLAUDE.md`).
- `skidl` becomes a runtime dep in the top-level `[project].dependencies` of `pyproject.toml` (alongside additions like `wireviz`). Today `dependencies = []` — add `skidl` there.

## Testing conventions

- Unit: `tests/unit/pcb/test_*.py`. Integration: `tests/integration/pcb/test_*.py` (create the directory if absent; existing `tests/` has only `unit/`).
- Fixtures in `conftest.py` (root `tests/conftest.py` exists).
- **Do not import consumer projects** (e.g. `juicebox_skidl`). Fabricate a minimal SKiDL `Circuit` inside fixtures. Schematika repo stays independent.
- Full test list for `pcb/` lives in the spec §Testing (14 unit + 1 integration).

## Tooling

From `Schematika/pyproject.toml` and `.pre-commit-config.yaml`:

```bash
uv sync                        # install
uv run pytest                  # tests (--verbose --cov=src, 1233 tests baseline)
uv run ruff check              # lint
uv run ruff format             # format
uv run ty check                # type check (~54 diagnostics baseline)
pre-commit run --all-files     # full suite — run before every commit
```

Python 3.12+ required. Line length 88. Run `pytest` from the repo root.

## The carved-out exception for PCB work

One file outside `pcb/` is allowed: `src/schematika/electrical/symbols/connector_pins.py` — a square, ~2× terminal-size single-pin connector glyph. Follow the `terminals.py` template exactly (see §Symbol factory conventions).

This is the only addition to an existing Schematika module permitted by the spec.

## Red flags — stop and re-read the spec

- A `pcb/` function returns a `Project`. Fix: return `PCBBuildResult`; let the caller assemble.
- `skidl` imported outside `pcb/adapter.py`. Fix: move the import.
- A new primitive added under `core/` or `electrical/model/`. Fix: reuse `Circle`, `Rect`, `Line`, `Text`, `Port`.
- A new mutable builder class. The repo has exactly four (`Circuit`, `Project`, `CircuitBuilder`, `PlcMapper`) and the spec forbids adding more.
- `symbol.rotate(180)`. There is no such method. Use `rotate(symbol, 180)` from `schematika.core.transform`.
- Committing without running `pre-commit run --all-files` first.
