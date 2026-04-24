# Schematika Codebase Audit

**Date:** 2026-04-24
**Branch when audited:** `branch1` @ `4b79cd4` (five PCB commits have landed since — some PCB findings below may already be resolved; verify with `git diff 4b79cd4..HEAD -- src/schematika/pcb/`)
**Scope:** quality, simplicity, architecture, API consistency, purity, testing, docs, AI-agent friction, tooling
**Method:** 1 recon + 1 Zyncis/codesight probe + 7 domain-specific review subagents, coordinated by a purpose-built reviewer skill (`reviewing-ai-generated-python`) derived from web research on AI-code pitfalls
**Status:** read-only audit; no source files were edited

---

## 1. Verdict

**Schematika is cleaner than typical AI-authored code, but the documentation has rotted faster than the code.** Almost every negative surprise below is a case where the repo's actual state has drifted from what `CLAUDE.md` / `README.md` / `llms.txt` claim.

### Clean signals (above baseline for AI-authored Python)

- 0 `typing.Any` / 0 bare `except` / 0 TODO|FIXME|XXX|HACK / 0 unraised exception classes
- Consistent PEP 604: 280 `| None` vs 0 `Optional[`
- 100% of `# type: ignore` entries carry specific error codes
- Zero runtime dependencies (as advertised)
- `core/` is genuinely I/O-free — 0 `open`/`subprocess`/`datetime.now` (sole clock read lives in `electrical/builder.py:1316`)
- ~65% of `src/` is already effectively pure; `deal` adoption is tractable
- 8-hook pre-commit already running (ruff, ty, complexipy, bandit, vulture, radon-cc, radon-mi)
- No commented-out code graveyards; last 20 commits show no drive-by creep

### Concentrated problem areas

- Hotspots: `project.py` **1,702 LoC** (CLAUDE.md says ~820), `electrical/builder.py` **1,421 LoC / cyclomatic 165**, `electrical/__init__.py` exports **127 names**
- Documentation drift: test count (1,233 → actual 1,456), coverage (90% → 83%), exception module, `PlcMapper` (phantom), `~54 ty diagnostics` (actually 3 real + 42 optional-dep noise)
- One true **import cycle** (`electrical/__init__.py:80` ↔ `project.py`) that the "one-way dep" invariant forbids
- **Phantom features**: `snapshot_svg` fixture defined & documented but never called by any test; 3 currently failing tests; empty `pcb/__init__.py` despite the module being complete (likely fixed by recent PCB commit); ~6 phantom parameters on `CircuitBuilder`
- Test quality: predicted mutant-kill rate **55–65%** (below the 80% threshold for behaviorally-driven tests); structural `isinstance` / `len >= N` dominate
- Architecture: 5 shim files in `electrical/utils/`, electrical-specific helpers leaking into `core/parts.py`, 4 ordering-sensitive `__init__.py` files (CLAUDE.md names 2)
- **API consistency**: 5 distinct "top-level verb" shapes, mixed `add_*`/bare-verb method naming, parameter-name drift (`label`/`name`/`tag`/`ref`, `x,y`/`Point`, `spacing`/`gap`/`offset`), 40% of sampled docstrings are paraphrase (see §5 for style guide)

---

## 2. HIGH-severity findings

| # | Location | Issue | Fix |
|---|---|---|---|
| H1 | `src/schematika/electrical/__init__.py:80` | Unconditional `from schematika.project import Project` creates an eager import cycle | Delete the import |
| H2 | `src/schematika/pcb/__init__.py` | Empty stub despite module being complete | Re-export `build`, `add_to_project`, `PCBBuildResult`, `SymbolMap`, `SymbolMapping`, `ConnectorMap`, `PowerNetMap`, `SymbolSlice`, errors. **(Likely already fixed by `67d3d22 feat(pcb): public API`.)** |
| H3 | `src/schematika/pcb/builder.py:202–211` | `_should_rotate()` catches bare `Exception`, silently returns `False` | Narrow to `(AttributeError, KeyError)` |
| H4 | `src/schematika/pcb/builder.py` | 3 unreachable helpers + 2 F841 dead locals | Delete. **(May be addressed by `b5512ff fix(pcb): address code-review findings`.)** |
| H5 | `src/schematika/pcb/builder.py:664` → `project.py` | `add_to_project(project, result)` inverts documented layering | Invert: `Project.add_pcb_result(result)` |
| H6 | `src/schematika/core/parts.py` | Leaks electrical-specific helpers (`terminal_circle`, `create_pin_labels`, `multipole`, `pad_pins`) | Move to `electrical/symbol_parts.py` |
| H7 | `src/schematika/core/state.py:28–32` | `GenerationState` frozen but holds plain `dict` fields — silent aliasing | Switch to `Mapping[...]` or `MappingProxyType` |
| H8 | `tests/conftest.py:8–58` | `snapshot_svg` fixture defined + documented but **never called** | Delete fixture + doc OR write real snapshot tests |
| H9 | `tests/unit/test_pcb_traverse_through_label.py` | 3 tests failing on clean run | Fix or xfail |
| H10 | `src/schematika/mcp/` | 0% coverage on shipped code | Add smoke test OR mark optional + `# pragma: no cover` |
| H11 | `llms.txt:15–17` | 3 example filenames don't match filesystem | Regenerate or delete |
| H12 | `CLAUDE.md` | Stale: `PlcMapper` (doesn't exist), exception module wrong, test count wrong, coverage wrong, project.py LoC wrong, ty diagnostic count wrong, 4-mutable-builder list wrong (11 exist) | Rewrite (see §7) |
| H13 | `src/schematika/pid/builder.py` | 14 raw `ValueError` sites; no `PIDError` hierarchy | Introduce `PIDError` mirroring `pcb/errors.py` |

---

## 3. MEDIUM-severity findings

### Structure & API

- `electrical/utils/` is a shim dir — `transform.py`, `renderer.py`, `model/core.py`, `model/parts.py`, `model/primitives.py` are pure re-exports. Delete, migrate callers.
- `electrical/__init__.py` exports **127 names** in `__all__`, many internal.
- `Project.compile_pdf()` duplicates `Project.build()` (~95% identical body at `project.py:820` vs `:1020`).
- `Project.field_devices()` vs `Project.add_field_devices()` — two methods, one feature, different semantics.
- `Project.circuit()` vs `Project.add_circuit()` — polymorphic split.
- `PIDBuilder.pipe()` / `signal_line()` violate the `add_*` convention (see §5).
- `cable/builder.py` returns `list[CableDrawing]` — only builder not returning a dataclass result.
- `BlockDiagram.render(filename)` conflates build + render + file I/O.
- 4 ordering-sensitive `__init__.py` files (CLAUDE.md names 2).
- Per-module file-role convention (`model.py` / `builder.py` / `renderer.py`) only cleanly matched by `cable/`.

### Purity / deal-readiness

- **11 mutable `@dataclass`** beyond the documented 4 builders: `_CircuitDef`, `_PageDef`, `_PIDDef`, `_BlockDiagramDef` (`project.py`); `CircuitSpec`, `PortRef`, `ComponentRef`, `BuildResult` (`electrical/builder_models.py`); `Circuit` (`electrical/system/system.py`); `PIDDiagram` (`pid/diagram.py`); `_EquipmentEntry` (`pid/builder.py`); `Block` (`block/model.py`); `TypstCompilerConfig`, `_Page` (`rendering/typst/compiler.py`); `ValidationResult` (`core/validation.py`); `ConnectionNode` (`electrical/system/system_analysis.py`).
- 1 `datetime.now()` (`electrical/builder.py:1316`) — parameterize.
- 4 `print()` in library code — replace with callback or delete.
- 2 module-level mutable containers (`mcp/server.py:20`; `block/model.py:61`) — freeze.

### Types & lint

- **8 identical `# type: ignore[arg-type]` on `relative_to`** in `electrical/builder.py` — widen once, delete all 8.
- **9 `cast()` in `core/transform.py`** silencing a TypeVar/dispatch issue — `@overload` or per-class method.
- **4 stacked `# type: ignore[union-attr]`** in `pcb/adapter.py` — skidl leakage via `SkidlCircuitLike` Protocol.
- `tools/` causes 42/45 ty diagnostics — exclude.
- Ruff `select` missing `UP`, `SIM`, `FA`.
- **44 ruff errors in `tests/`** — hook doesn't cover tests.
- `from __future__ import annotations` in 24/108 files — inconsistent.
- `typing.Union` still in `electrical/field_devices.py:41,65`.
- 10 files fail `ruff format --check`.

### Tests

- Structural `isinstance` (208×) + `len(...) >= N` dominate. Predicted mutant-kill rate **55–65%**.
- Zero `hypothesis` usage. Natural targets: `rotate_point`, `translate`, `_pack_pages`.
- `tests/unit/test_project.py` mocks heavily — `Project` is pure.
- 12+ duplicated test helpers — consolidate into `tests/unit/_factories.py`.

### Dead / phantom

- `apply_start_indices` (`electrical/utils/utils.py:78`) — zero call sites.
- `SkidlPartLike(Protocol)` in `pcb/model.py:18` — zero annotation uses.
- Phantom params on `CircuitBuilder.add_reference` (`y_increment`, `connect_to_next`), `add_terminal(connection_side=...)`, `add_symbol(wire_labels_above=...)`, `add_spdt(wire_labels_above=...)`.
- `_apply_rotation_if_needed` + `_circuit_to_build_result` in `pcb/builder.py` — 3-line single-use wrappers.
- `core/traversal.py` — one function used once; inline.
- `merge_terminals` — 1-line wrapper called once.

---

## 4. LOW-severity

- 2 commented-out imports in `core/__init__.py:6–7`.
- `coils.py` has module docstring **after** imports (agents will mimic).
- `mcp/server.py:20` — make `Final[tuple[str, ...]]`.
- `block/__init__.py` sorts `__all__` alphabetically vs `electrical` groups by category.
- Trivial 10-line files (`pid/styles.py`, `cable/constants.py`, `electrical/exceptions.py`) — inline.
- `ref()` / `ref_symbol` aliasing — confusing.

---

## 5. API & docstring consistency — proposed style guide

This section addresses the user question: **how consistent are names, functionality, parameters, and docstrings — and how do we enforce consistency going forward?**

### 5.1 Current inconsistencies (evidence)

**Top-level verb drift (5 distinct shapes):**

| Module | Entry | Return |
|---|---|---|
| `electrical` | `CircuitBuilder.build()` / `build_from_descriptors()` | `BuildResult` |
| `pid` | `PIDBuilder.build()` | `PIDBuildResult` |
| `pcb` | free `build(circuit, mapping)` | `PCBBuildResult` |
| `cable` | free `build_cable_drawings()` | `list[CableDrawing]` |
| `block` | `BlockDiagram.render(filename)` | `None` (side-effect) |
| `project` | `Project.build()` **and** `Project.compile_pdf()` | `None` |

**Method-name drift:** `PIDBuilder.pipe()`, `signal_line()` (no `add_`); `BlockDiagram.block()`, `cable()` (no `add_`); `Project.circuit()` vs `add_circuit()` (both exist, different semantics); `Project.field_devices()` vs `add_field_devices()` (both exist); `Project.compile_pdf()` duplicates `Project.build()`.

**Parameter-name drift (same concept, different names):**
- `label` / `name` / `tag` / `ref` — four names for component identity-adjacent things, no glossary
- `x, y` (scalar pairs) vs `point: Point` — repo has both, `Point` type exists in `core/geometry.py` but public APIs don't accept it
- `spacing` (181 hits / 27 files) / `gap` (`BLOCK_GAP`, `PID_MIN_EQUIPMENT_GAP`) / `offset` — all three mean "distance between things," no rule

**Docstring drift:**
- 10-sample audit: 40% informative / 50% paraphrase / 10% missing
- `CircuitBuilder.__init__` has 15-line docstring; `PIDBuilder.__init__` has **no** docstring for the same role
- No declared style (Google? NumPy? reST?) — samples contain all three shapes
- No enforced sections (Args / Returns / Raises / Examples)
- No signature↔docstring consistency check (params can silently diverge)

### 5.2 Proposed API style guide

Adopt these rules — concrete, enforceable, few enough to remember.

**Verbs (canonical list, one per concept):**

| Verb | Meaning | Example |
|---|---|---|
| `add_<noun>` | Register a new component on a mutable builder | `builder.add_terminal`, `project.add_circuit` |
| `set_<noun>` | Configure a single-valued property on a builder | `builder.set_layout` |
| `build()` | Produce a frozen `*BuildResult` from a builder | `CircuitBuilder.build()` |
| `render(target)` | Produce output bytes/string, no I/O | `renderer.render(diagram) -> str` |
| `write(path)` | Shell operation that calls `render` then writes to disk | `project.write(Path("out.pdf"))` |
| `compile(project, path)` | Reserved for end-to-end pipeline runs (currently used correctly by `TypstCompiler.compile`) | — |

Banned aliases: any verb pair like `get_`/`fetch_`/`load_`/`retrieve_` for the same operation; free-function `build_<noun>s(...)` when a builder already exists for that domain.

**Method-name conventions:**

1. Every mutable builder method that *registers* a thing is `add_<noun>` — never `pipe()`, `cable()`, `circuit()`, `block()`, `field_devices()`.
2. Every mutable builder method that *configures* is `set_<property>`.
3. Every builder produces a `*BuildResult` frozen dataclass via `build() -> *BuildResult`. No builder returns a bare list, `None`, or a `Project`.
4. `Project` methods that register are `add_<domain>`; methods that act are `write` / `compile` / `export_<format>`.
5. One method per concept. `Project.circuit` + `add_circuit`, `Project.field_devices` + `add_field_devices`, `Project.build` + `compile_pdf` — pick one each, delete the other.

**Parameter glossary (canonical names):**

| Name | Type | Meaning |
|---|---|---|
| `name` | `str` | User-supplied lookup key (e.g., dict key on `Project`) |
| `label` | `str` | Rendered text shown on the diagram |
| `tag` | `str` | Autonumbered reference (`"K1"`, `"F2"`) — generated, not user-provided |
| `ref` | `ComponentRef` | Structural reference object returned from `add_*` for later use |
| `position` | `Point \| None` | Diagram coordinates; `None` means auto-layout |
| `spacing` | `float` (mm) | Layout-axis distance between adjacent items |
| `gap` | `float` (mm) | Minimum clearance required between items |
| `offset` | `Vector` | Vector displacement |
| `port_id` | `str` | Port identifier on a symbol (convention varies per symbol type — document at symbol factory) |
| `now` | `datetime \| None` | Clock read — passed in, never called from inside |
| `state` | `GenerationState` | Functional-state thread; first arg of any state-reading fn |

Ban `x, y` as separate scalar kwargs on public APIs — always `position: Point | None`. Internal helpers can still take scalars.

**Parameter ordering (public APIs):**

```
def add_thing(
    self,                       # builder instance
    name: str,                  # primary identity (required, positional)
    /,                          # positional-only boundary
    *,                          # keyword-only from here
    label: str | None = None,   # rendered text
    position: Point | None = None,
    pins: tuple[str, ...] = (),
    ...
) -> ComponentRef: ...
```

Rule: **one positional arg (`name`/identity); every other parameter is keyword-only via `*`**. This makes call sites self-documenting and future-proofs parameter additions (adding a new kwarg never breaks positional callers).

**Return types:**

- Every domain builder returns a dedicated frozen `*BuildResult` dataclass. Never `list[...]`, never `None`, never `Project`. Fix `cable/builder.py` accordingly (introduce `CableBuildResult`).
- Free functions return a value or raise; never return `None` on failure (use the exception hierarchy instead).

**Exception hierarchy (one rule per module):**

- Each domain has one base error: `CircuitValidationError`, `PIDError`, `PCBBuildError`, `CableError`.
- All module-local errors inherit from the base.
- `ValueError` is reserved for programmer errors on stdlib boundaries — never raised for domain validation.

### 5.3 Proposed docstring convention

**Style: Google (compact, scannable, parseable by `pdoc` + `darglint` + ruff `D`).**

Required shape for every public function/method/class on the API surface:

```python
def add_terminal(
    self,
    name: str,
    /,
    *,
    poles: int = 1,
    position: Point | None = None,
) -> TerminalRef:
    """Register a terminal on the circuit.

    Args:
        name: Lookup key used by callers and exported on the terminal strip.
        poles: Number of poles (1 for single, 2+ for multi-pole blocks).
        position: Explicit coordinates; `None` triggers auto-layout.

    Returns:
        `TerminalRef` that can be used in subsequent `add_connection` calls.

    Raises:
        TerminalReuseError: If a terminal with `name` is already registered.
    """
```

Rules:

1. **First line:** imperative mood, <80 chars, period at end. ("Register a terminal on the circuit.")
2. **Blank line**, then optional prose paragraph for non-obvious WHY (invariants, units, coordinate convention).
3. **Args:** block if the function has args; every parameter listed in function signature order.
4. **Returns:** block if the function has a non-None return; describes the *meaning* of the value, not its type (the signature has the type).
5. **Raises:** block if the function raises; one line per exception class with the triggering condition.
6. **No:** `Examples:` (use `pytest-examples` on markdown instead), `Note:` (use inline prose), multi-paragraph Args entries (a parameter docstring >2 lines is a signal that the parameter is doing too much).
7. **No paraphrase.** If the docstring only restates the signature, delete it. The signature + type already communicate that.

Private functions (`_`-prefixed): one-line docstring if non-obvious; otherwise nothing. Don't write docstrings to prove a function exists.

### 5.4 Enforcement (wire into pre-commit + ruff)

All of the above can be enforced automatically. Add to `pyproject.toml`:

```toml
[tool.ruff.lint]
# existing: select = ["E", "W", "F", "I", "C", "B"]
extend-select = [
    "UP",     # pyupgrade — legacy typing
    "SIM",    # simplify
    "FA",     # flake8-future-annotations — enforces one __future__ rule
    "N",      # pep8-naming — catches class/function/variable name drift
    "D",      # pydocstyle — docstring rules
    "PT",     # pytest style
    "RET",    # flake8-return
    "ARG",    # flake8-unused-arguments — catches phantom params
    "PLR",    # pylint refactor — too-many-args etc.
]

[tool.ruff.lint.pydocstyle]
convention = "google"     # enforces Google-style Args/Returns/Raises blocks

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D", "ARG"]           # tests don't need docstrings
"src/schematika/**/__init__.py" = ["D104"]  # allow empty package docstrings on re-export-only __init__s

[tool.ruff.lint.pep8-naming]
classmethod-decorators = ["classmethod", "pydantic.validator"]
```

**Additional hooks (pre-commit):**

| Tool | Enforces |
|---|---|
| **`interrogate`** (already in chosen stack) | Docstring *coverage* — fails if <80% of public symbols have any docstring |
| **`darglint`** | Docstring/signature *consistency* — fails if the Args block lists params that don't exist or omits params that do. Catches docstring rot automatically |
| **`ruff` with `D` rules** | Docstring *style* (Google format, imperative first line, periods, etc.) |
| **`docformatter`** (optional) | Auto-fix docstring wrapping/style on commit |
| **Custom `claude-tools/api_style_gate.py`** | AST gate that fails pre-commit if: (a) any public `add_*`/`set_*` method takes more than one positional-only arg; (b) any public method has `x: float, y: float` without a `position: Point` alternative; (c) any public builder returns `None`/`list`/`Project` from a method literally named `build` |

The custom AST gate is the only tool that directly encodes *Schematika's* API rules; the rest are off-the-shelf lint.

**One-time migration cost** (rough estimate from sample counts):
- Ruff `D` rollout: probably ~300 findings on current code — most autofixable with `ruff check --fix` and `docformatter`. Manual work: rewrite the ~50% paraphrase docstrings as informative or delete.
- Ruff `N` rollout: few findings expected (naming mostly consistent).
- Darglint rollout: probably ~50 findings — signatures and docstrings have drifted.
- Builder-rename PR: `PIDBuilder.pipe → add_pipe`, `signal_line → add_signal_line`, `BlockDiagram.block → add_block`, `BlockDiagram.cable → add_cable`, collapse `Project.circuit`/`add_circuit`, collapse `Project.field_devices`/`add_field_devices`, delete `Project.compile_pdf`.
- Parameter-glossary PR: rename `label`/`name` occurrences to match the glossary, add `position: Point | None` to signatures that currently take `x, y`.

Both renames are breaking changes — acceptable per the "alpha, no back-compat" ground rule. Do them once, early, before more consumer code appears.

### 5.5 Documenting the style

Create `docs/API_STYLE.md` with the glossary and rules, and add one line to `CLAUDE.md`: *"Before designing a new public API, read `docs/API_STYLE.md`. The ruff + darglint hooks enforce most of it; the custom AST gate enforces the rest."* This is the single highest-leverage doc addition — it turns a rotting convention into a checked contract.

---

## 6. Chosen tool stack (per user selection)

### Per-commit hooks

| Tool | Purpose | Wiring |
|---|---|---|
| **import-linter** | Declarative layering rules — kills the `electrical → project` cycle permanently | `.importlinter` contract forbidding `electrical → project`, `pcb → project` |
| **interrogate** | Docstring coverage gate | pre-commit hook; fail < 80% on `src/` |
| **ruff `select += UP, SIM, FA`** + docstring rules (§5.4) | Auto-fix legacy typing, simplifiable code, enforce one `__future__` rule, enforce Google-style docstrings | pyproject.toml edit |
| **Extend ruff hook to `tests/`** | Clears 44 existing lint errors | Update hook `files` pattern |
| **codesight** (`npx codesight --wiki`) | AST-based AI-context map | Pre-commit local hook; output to gitignored `.codesight/` |
| **fp-purity-gate** (`claude-tools/fp_purity_gate.py`) | Fails commit if any `def` inside `src/schematika/core/**.py` lacks `@deal.pure` | Custom AST hook; modeled on python-coding-and-tooling skill |
| **api-style-gate** (`claude-tools/api_style_gate.py`) | Enforces Schematika-specific rules from §5.2 | Custom AST hook |
| **darglint** | Signature↔docstring consistency | pre-commit hook on `src/schematika/**` |

### Per-push / periodic

| Tool | Purpose | Wiring |
|---|---|---|
| **repomix** | Whole-repo LLM-ready markdown dump | Pre-push or `just context` |
| **vulture `--min-confidence 60`** | Manual dead-code sweep | `just dead-code` (not a hook) |
| **mutmut** | Mutation testing (suite runs in 11.24s — fast enough) | `just mutate`; weekly |

### Purity & contracts

| Tool | Purpose |
|---|---|
| **deal** | `@deal.pure` on `core/` first (2,060 LoC, zero code changes); then `pcb/`, `catalog/`, `cable/`, most of `electrical/` non-builder files |

### Docs & staleness

| Tool | Purpose |
|---|---|
| **pytest-examples** | Executes Python code blocks in `.md` files against the live API — README / `llms.txt` / CLAUDE.md can't drift undetected |
| **pdoc** | Auto-generated API reference from docstrings |
| **`just stats`** | Prints live test count, coverage, ty count, src LoC — CLAUDE.md links to it instead of hardcoding |

### Runner

| Tool | Purpose |
|---|---|
| **justfile** | One-screen task runner for manual/weekly commands |

---

## 7. CLAUDE.md rewrite principles

1. **No live numbers.** Replace test count / coverage / LoC / diagnostic count with `see just stats`.
2. **Fix exception module** — exceptions live in `core/exceptions.py`, not `electrical/exceptions.py`.
3. **Drop `PlcMapper`** from the 4-builder list; settle the real mutable-builder count after the §3 audit.
4. **Promote the PCB skill's "Red Flags"** to global scope: `symbol.rotate(180)` doesn't exist (use `rotate(symbol, 180)`); modules return data, not `Project`; `Terminal` vs `TerminalSymbol`; 4 ordering-sensitive files.
5. **Point agents at `.codesight/` first**: "Before exploring source, read `.codesight/wiki/index.md`."
6. **Link to `docs/API_STYLE.md`** (§5.5).
7. **Add `docs/ARCHITECTURE.md`** — 1 page, table-form, one row per top-level package.

---

## 8. Action plan

**PR 1** — Delete dead code (~150 LoC, zero behavior change): unreachable helpers in `pcb/builder.py`, `apply_start_indices`, `merge_terminals`, `_apply_rotation_if_needed`, `_circuit_to_build_result`, `SkidlPartLike`, phantom params on `CircuitBuilder`, `core/traversal.py`, stale comments in `core/__init__.py:6–7`.

**PR 2** — Fix docs + failing tests: fix/xfail 3 failing tests, regenerate `llms.txt`, CLAUDE.md rewrite, add `docs/ARCHITECTURE.md` + `docs/API_STYLE.md`, decide fate of `snapshot_svg`.

**PR 3** — Fix architecture: remove `electrical/__init__.py:80` import; invert `pcb/builder.py:add_to_project`; delete `electrical/utils/` shims; move electrical helpers out of `core/parts.py`.

**PR 4** — Fix types & lint: widen `relative_to`, refactor `core/transform.py` with `@overload`, exclude `tools/` from ty, enable ruff `UP, SIM, FA, N, D, ARG, PLR, PT, RET`, enforce ruff on `tests/`, replace `typing.Union`.

**PR 5** — Error hierarchy: introduce `PIDError`, migrate 14 `ValueError` sites, narrow `except Exception` in `pcb/builder.py:210`.

**PR 6** — Freeze the 11 stray mutable dataclasses (or document as intentional builders).

**PR 7** — API renames (breaking): `PIDBuilder.pipe → add_pipe`, `signal_line → add_signal_line`, `BlockDiagram.block → add_block`, `cable → add_cable`, collapse `Project.circuit`/`add_circuit`, collapse `field_devices`/`add_field_devices`, delete `compile_pdf`, introduce `CableBuildResult`. Add `docs/API_STYLE.md`.

**PR 8** — Docstring rollout: enable ruff `D` rules with Google convention, run `docformatter`, add `interrogate` + `darglint`, rewrite the ~50% paraphrase docstrings.

**PR 9** — Tooling install: `import-linter`, `interrogate`, `pytest-examples`, `pdoc`, `deal`, `repomix`, `codesight`; pre-commit hooks; `claude-tools/fp_purity_gate.py` + `api_style_gate.py`; `justfile`; `.gitignore` entries.

**PR 10** — `deal` on `core/` (decorator-only, 2,060 LoC, zero code changes); fp-purity-gate hook enforces.

**PR 11** — Testing quality: `mutmut` (≥80% kill gate per module), 3 `hypothesis` targets, consolidate test fixtures, stop mocking pure code in `test_project.py`.

**PR 12 (future)** — Split `project.py` (1,702 LoC) + `DiagramKind` registry replacing the `page_type` switch.

---

## 9. Artifacts

- Reviewer-playbook skill: `~/.claude/skills/reviewing-ai-generated-python/SKILL.md` (12-category audit playbook with signals to grep, confirmation tests, suggested fixes)
- This audit: `CODEBASE_AUDIT.md` (repo root)

No Schematika source files were modified.

---

## 10. Research sources

- [thoughtbot — How to review AI-generated PRs](https://thoughtbot.com/blog/how-to-review-ai-generated-prs)
- [Simon Willison — Hallucinations in code](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/)
- [Martin Fowler — Patterns for Reducing Friction in AI-Assisted Development](https://martinfowler.com/articles/reduce-friction-ai/)
- [CodeRabbit — State of AI vs Human Code Generation](https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report)
- [arXiv — Importing Phantoms: LLM Package Hallucination](https://arxiv.org/html/2501.19012v1)
- [arXiv — Are Coding Agents Generating Over-Mocked Tests](https://arxiv.org/pdf/2602.00409)
- [Aviator — How to Avoid AI Code Slop](https://www.aviator.co/blog/how-to-avoid-ai-code-slop/)
- [Adventures in Claude — Two Weeks of Stomping Slop](https://adventuresinclaude.ai/posts/two-weeks-of-stomping-slop/)
- [Mutmut vs Cosmic-Ray vs Mutatest — 2025 benchmarks](https://johal.in/mutation-testing-with-mutmut-python-for-code-reliability-2026/)
- [Codesight — GitHub (Houseofmvps)](https://github.com/Houseofmvps/codesight)
- [Repomix](https://repomix.com/)
- [Google docstring convention (pydocstyle)](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [darglint — docstring/signature consistency](https://github.com/terrencepreilly/darglint)
