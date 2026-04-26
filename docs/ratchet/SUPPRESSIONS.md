# Ratchet suppressions

Suppressions added during quality ratchet waves. Each entry includes the file, rule, wave, and justification.

## Wave R2a (RUF)

- `src/schematika/electrical/__init__.py:140` — `# noqa: RUF022` — Wave R2a — Why: `__all__` is grouped by category (Core, Symbol factories, Constants, Utilities, Devices, PLC, Exceptions) for readability. Sorting alphabetically would destroy the intentional grouping that helps users find exports.

- `src/schematika/pcb/__init__.py:28` — `# noqa: RUF022` — Wave R2a — Why: `__all__` is grouped by sub-module (builder, errors, model) for readability. Sorting alphabetically would mix the logical sections.

## Wave R5 (N-series naming)

- `tests/unit/test_pcb_adapter.py` — `[N806]` in per-file-ignores — Wave R5 — Why: tests use IEC fuse/terminal designators (F1, F2, F3, T1, _F1, _F2, _F3) as fixture identifiers; lowercasing would lose intent and misrepresent IEC naming conventions.

- `tests/unit/test_plc_resolver.py` — `[N806, N817]` in per-file-ignores — Wave R5 — Why: N806 covers `DI_MODULE_1CH` (PLC channel-count identifier, uppercase is conventional); N817 covers `PD`/`PMT`/`PR` import aliases for `PlcDesignation`/`PlcModuleType`/`PlcRack` (acronym aliases aid readability in dense PLC resolver tests).

- `tests/unit/test_terminal_type.py` — `[N817]` in per-file-ignores — Wave R5 — Why: `T` is the conventional single-letter alias for `Terminal` in IEC context test fixtures; renaming would reduce clarity.

## Wave R6 (BLE/RET/RSE/TRY)

- `TRY003` — globally ignored — Wave R6 — Why: Schematika already has a domain-exception hierarchy (CircuitValidationError, PIDError, PCBBuildError, with subclasses for specific failure modes — see `core/exceptions.py`, `pid/errors.py`, `pcb/errors.py`). TRY003's "every raise gets a custom subclass with the message hardcoded" rule would mean ~50+ new single-use subclasses for one-off validation messages. The architectural intent TRY003 nudges toward is already met by the base classes; per-message subclasses would be over-engineering.

- `src/schematika/mcp/server.py` — `[BLE001]` in per-file-ignores — Wave R6 — Why: `validate_circuit` and `render_circuit` are sandboxed user-code executors that intentionally convert any exception raised by arbitrary user Python into a structured error string. The broad `except Exception` is the correct narrowest catch for "anything user code can raise"; replacing it with narrower types would let errors escape the sandbox unformatted.

- `tests/unit/test_builder.py` — `[RET504]` in per-file-ignores — Wave R6 — Why: `mock_symbol` helper assigns the symbol to `s` before returning; fixing RET504 would require changing test fixture body logic, which is blocked per the wave R6 spec constraint on test bodies.

## Wave R7c (C901/PLR0912/PLR0915/PLR0911 complexity)

Threshold relaxations in `pyproject.toml` (all global, covering multiple sites):

- `max-complexity = 22` (mccabe, raised from default 10) — Wave R7c — Why: Dispatch-table functions (`translate`, `_render_element`, `_render_page`) and SVG path parsers (`_translate_path_d`, `_rotate_path_d`) have structural complexity that maps directly to the number of element types / SVG path commands in the standard. Introducing extraction or lookup tables would scatter the per-type logic across files. The build pipeline phase functions (`_phase1`–`_phase4`) each handle a fixed set of component kinds (terminal, symbol, reference) whose branches are inherently parallel and cannot be collapsed without losing the invariant that each kind produces exactly the right connection/rendering output.

- `max-returns = 10` (PLR0911, raised from default 6) — Wave R7c — Why: `core/transform.py:translate` is a singledispatch-like if-isinstance chain; each element type needs its own return. `rendering/typst/compiler.py:_render_page` dispatches on 8 page types, each returning immediately. Combining returns would require storing intermediate results in a variable that adds noise.

- `max-branches = 22` (PLR0912, raised from default 12) — Wave R7c — Why: SVG path parsers handle one branch per path command type (M/L/T, H, V, C/S/Q, Z, and the relative fallthrough). The build pipeline phases branch on component kind × connection direction combinations.

- `max-statements = 70` (PLR0915, raised from default 50) — Wave R7c — Why: `_rotate_path_d` in `core/transform.py` is an explicit state machine over SVG path tokens. The statement count reflects one case block per command, each with 4–6 statements (parse, rotate, emit). The count cannot be meaningfully reduced without a dispatch dict that would obscure the per-command geometry.

## Wave R8c (PTH — pathlib migration)

- All 262 sites migrated from `os.path.*` / `open()` to `pathlib.Path`. No suppressions required; the two `os.path.relpath()` calls that remain in `project.py` and `compiler.py` are not covered by any PTH rule (PTH does not flag `os.path.relpath`).

## Wave R8b (DTZ — datetimez)

- `src/schematika/electrical/builder.py:1337` — fixed `datetime.now()` → `datetime.now(tz=timezone.utc)` — Wave R8b — Why: log timestamps should always be UTC-aware; the inline fix is trivial and correct.

## Wave R8a (S — security/bandit)

- `tests/**` — `[S101, S108]` in per-file-ignores — Wave R8a — Why: S101 (assert) — pytest test bodies use `assert` as the assertion mechanism; this is not a security risk, it is pytest's intended protocol. S108 (hardcoded-temp-file) — tests use `/tmp/` paths as deliberate test fixture strings that are passed to mocked objects; no actual temp files are created.

- `src/schematika/mcp/server.py` — `[S102]` added to per-file-ignores — Wave R8a — Why: `exec()` is the explicit mechanism for executing user-submitted Python code in the MCP sandbox. There is no alternative to `exec` for dynamic code execution; the sandbox is intentional by design.

- `src/schematika/block/layout.py` — 3× `# noqa: S101` — Wave R8a — Why: precondition asserts used for type narrowing (`ref is not None`); the reference is guaranteed non-None by the dispatch logic that calls these helpers, and a None reference would be a programmer error, not a runtime/security event.

- `src/schematika/pid/builder.py:520` — `# noqa: S101` — Wave R8a — Why: `abs_pos is not None` is an invariant guaranteed by construction; the abs_position loop runs only after positions have been resolved.

- `src/schematika/project.py:1705` — `# noqa: S101` — Wave R8a — Why: `rack is not None` is a precondition; `_generate_plc_csv` is only called from a branch that checks `_plc_rack is not None`.

## Wave R8d (ERA — commented-out code)

- `tests/unit/test_symbols.py:179-181` — 3 comment lines deleted — Wave R8d — Why: ERA001 flagged these as commented-out code (variable name expressions like `# SPDT_POLE_SPACING = 40.0` and a list of symbol names). They provided no unique context beyond what the adjacent assertions already express; deleted.

- `tests/unit/test_transform.py:686-687` — 2 comment lines deleted — Wave R8d — Why: ERA001 flagged `# position = Point(...)` as commented-out code. The assertion on the next line already captures the expected value.

## Wave R8e (FBT — boolean trap → keyword-only)

- All 41 FBT violations fixed by adding `*` keyword-only separator before boolean params. No suppressions required. Affected files: `core/parts.py` (3 functions), `block/model.py` (`place()`), `block/rendering.py` (3 private functions), `electrical/builder.py` (`_resolve_placement`, `add_symbol`), `electrical/builder_utils.py` (`_resolve_pin`), `electrical/symbols/coils.py` (`coil`), `electrical/symbols/contacts.py` (`_spdt_contact_single_pole`, `spdt_contact`), `electrical/terminal.py` (`Terminal.__new__`), `pid/symbols/valves.py` (`_bowtie_polygons`), `project.py` (`cable_pages`, `build`, `compile_pdf`), `tests/unit/test_project.py` (`_mock_build`). Internal positional callers updated to use keyword form.

## Wave R8f (EM — extract exception messages)

- All 80 EM violations auto-fixed with `--unsafe-fixes`. Pattern: `raise X(f"...")` → `msg = f"..."; raise X(msg)`. No suppressions required; ruff's auto-fix was applied across 46 files.

## Wave R8g (TC — TYPE_CHECKING blocks)

- All 34 TC violations auto-fixed with `--unsafe-fixes`. TC001/TC003 moved type-only imports into `if TYPE_CHECKING:` blocks; TC006 added quotes to `typing.cast()` expressions. No suppressions required; applied across 18 files.

## Wave R8h (TID — lock-in)

- 0 violations. TID added to `select` in `pyproject.toml` for enforcement going forward.

## Wave T0 (ty noise reduction)

- `[tool.ty.src] exclude += ["scripts/vulture_whitelist.py"]` — Wave T0b — Why: `vulture_whitelist.py` exists only to silence vulture; it's a list of bare attribute references against fictitious classes and has no runtime semantics. ty type-checking it is pure noise (65 diagnostics from one file).

- `[tool.ty.src] exclude += ["scripts/pid_review.py"]` — Wave T0b — Why: P&ID visual review glue script that imports optional dev-extras (`cairosvg`, `playwright.sync_api`). These imports are guarded at runtime but ty (without those packages installed) flags them as `unresolved-import`. The script is not shipped infrastructure (cf. `api_style_gate.py` / `fp_purity_gate.py`, which stay typed); excluding silences 2 unresolved-import diagnostics.

- T0a (`unused-type-ignore-comment`) — no entries needed. The 22 warnings flagged by ty 0.0.21 in the baseline measurement do not reproduce under the lockfile-pinned ty 0.0.32 — the rule's behavior changed and ty no longer considers those comments unused. No `# type: ignore` comments were modified, narrowed, or introduced in T0. The 22 existing blanket `# type: ignore` directives across `src/` and `tests/` remain as-is.

## Wave T1 (ty unresolved-attr/import in src/)

### T1a — `signal.SIGALRM` / `signal.alarm` (mcp/server.py)

No `# type: ignore` introduced. Fixed structurally by lifting `_SIGALRM = getattr(signal, "SIGALRM", None)` and `_alarm = getattr(signal, "alarm", None)` to module level (`src/schematika/mcp/server.py:191-194`) and gating both call sites on `is not None`. ty narrows `is not None` reliably; it does not narrow `hasattr(signal, ...)` or `sys.platform == ...` checks. Eliminates 8 `unresolved-attribute` diagnostics with no suppression.

### T1b — optional-import suppressions

Each entry: file:line — rule — wave — Why.

- `src/schematika/cable/renderer.py:62-66` — `# ty: ignore[unresolved-import]` (on the `from wireviz.DataClasses import (...)` block) — Wave T1b — Why: `wireviz` is in `[project.optional-dependencies] cable`. The import is inside `_drawing_to_svg`, only reached when the user opted into the cable extra. ty resolves only installed packages in the current env, so this reads as unresolved unless `--extra cable` is synced.
- `src/schematika/cable/renderer.py:67` — `# ty: ignore[unresolved-import]` (`from wireviz.Harness import Harness`) — Wave T1b — Why: same as above; second wireviz submodule used in the same conditional path.
- `src/schematika/mcp/server.py:12` — `# ty: ignore[unresolved-import]` (`from mcp.server.fastmcp import FastMCP`) — Wave T1b — Why: `mcp>=1.0` is in `[project.optional-dependencies] mcp`. The whole `schematika.mcp.server` module is only imported by the optional `python -m schematika.mcp` entry point (`mcp/__main__.py`); a base install never reaches it. The top-level import is correct because the module is itself the gated surface.
- `src/schematika/project.py:1444` — `# ty: ignore[unresolved-import]` (`from openpyxl import Workbook`) — Wave T1b — Why: `openpyxl` is in `[project.optional-dependencies] excel`. The import lives inside `_export_bom_excel`, guarded by an early-return when no Excel BOM is configured, so users without the excel extra never execute the import.
- `src/schematika/project.py:1445-1449` — `# ty: ignore[unresolved-import]` (on the `from openpyxl.styles import (...)` block) — Wave T1b — Why: same as above; second openpyxl submodule used in the same conditional path. ruff I001 reformatted to multi-line parens; the comment attaches to the opening `import (`.
- `src/schematika/rendering/typst/compiler.py:152` — `# ty: ignore[unresolved-import]` (`import typst as typst_mod`) — Wave T1b — Why: `typst` is in `[project.optional-dependencies] pdf`. The import is wrapped in `try/except ImportError` that re-raises with an install hint pointing at `schematika[pdf]`.

No optional deps were added to runtime deps. Suppressions are the correct trade-off: structural fix would either force every install to drag in pdf/cable/excel/mcp extras or add dynamic-import boilerplate that buys nothing.

## Wave T2 (ty argument-type / assignment / call errors in src/)

ty 0.0.32 surfaces 39 errors in `src/` under three rules: `invalid-argument-type`, `invalid-assignment`, `call-non-callable`. Most were existing intentional mypy `# type: ignore[arg-type]` / `# type: ignore[assignment]` comments — mypy syntax is silently ignored by ty, so they became visible. The wave is largely a syntax migration with a few real fixes.

### T2a — `**kwargs: object` → `**kwargs: Any` (Block forwarders)

No `# ty: ignore` introduced. Fixed structurally:

- `src/schematika/block/diagram.py:59` — `BlockDiagram.block(label, **kwargs)` widened from `**kwargs: object` → `**kwargs: Any`. Removes 13 `invalid-argument-type` errors and one mypy `# type: ignore[arg-type]`.
- `src/schematika/block/model.py:163` — `Block.block(label, **kwargs)` widened identically. Removes 14 errors and one mypy ignore.

`Any` is the standard escape hatch for forwarding kwargs to a constructor whose param types vary. The function is a one-line forwarder; alternatives (TypedDict, explicit keyword params) would be over-engineering for a public-API ergonomic helper.

### T2b — `electrical/builder.py` `connect(relative_to, ...)` mypy → ty syntax

Eight sites where `connect(relative_to, ...)` passes `ComponentRef | PortRef | None` into a `PortRef`-typed parameter. Each site already had `# type: ignore[arg-type]` (mypy syntax, ineffective for ty). Converted to `# ty: ignore[invalid-argument-type]`.

- `src/schematika/electrical/builder.py:286` — Wave T2b — Why: chain-placement helper passes the resolved ref through to `connect`; widening `connect()`'s signature to accept `ComponentRef | PortRef` is a public-API change deferred to a separate refactor wave.
- `src/schematika/electrical/builder.py:294` — Wave T2b — Why: same path, opposite direction (below).
- `src/schematika/electrical/builder.py:523` — Wave T2b — Why: same pattern in non-chain placement (above).
- `src/schematika/electrical/builder.py:529` — Wave T2b — Why: same pattern (below).
- `src/schematika/electrical/builder.py:708` — Wave T2b — Why: same pattern, second non-chain helper (above).
- `src/schematika/electrical/builder.py:714` — Wave T2b — Why: same pattern (below).
- `src/schematika/electrical/builder.py:892` — Wave T2b — Why: `_connect_non_chain_placed_ref` helper (above).
- `src/schematika/electrical/builder.py:899` — Wave T2b — Why: same helper (below).

### T2c — singletons + core/

- `src/schematika/core/traversal.py:18` — no suppression. Real fix via `cast("list[Element]", root)`. Wave T2c — Why: ty 0.0.32 fails to narrow `for elem in root` to `Element` after `isinstance(root, list)` because `Element` is not declared `@final`, so ty keeps `Element & Top[list[Unknown]]` in the iteration type. `core/` is the architectural spine and is required to stay free of suppressions; cast is the minimum-noise fix.

- `src/schematika/cable/builder.py:200` — `# ty: ignore[invalid-assignment]` (converted from existing mypy `# type: ignore[assignment]`) — Wave T2c — Why: `field_device.cables: tuple[DeviceCable, ...] | None`. The local annotation narrows to non-None because `_build_multi_cable_drawings` is only entered when cables is non-None (caller-side guard, not visible to ty). A runtime `assert` would add `S101` noise; the existing mypy ignore documented the intent.

- `src/schematika/mcp/server.py:308` — `# ty: ignore[call-non-callable]` (newly introduced) — Wave T2c — Why: `original_render = g.get("render_system")` returns `object | None` because `dict.get` with no default returns `Optional[V]` and `g`'s value type is `object`. In practice the value is always the `render_system` callable populated by `_make_exec_globals()`; a structural fix (typing the globals dict) would require either a `TypedDict` for the exec globals or a cast that buys nothing.

- `src/schematika/pid/builder.py:540` — no suppression. Real fix: replaced the `dict[str, Placement | None]` comprehension (with `if ... is not None` filter) with an explicit typed-dict + for-loop that ty narrows correctly. Dropped the redundant mypy `# type: ignore[arg-type]`.

### Removed mypy `# type: ignore` comments

- T2a: 2 (one per Block forwarder).
- T2b: 8 (replaced with ty syntax).
- T2c: 2 (one converted, one dropped at `pid/builder.py:540`).
- Total: 12.

### New ty suppressions

- T2b: 8 × `# ty: ignore[invalid-argument-type]` in `electrical/builder.py`.
- T2c: 1 × `# ty: ignore[invalid-assignment]` (`cable/builder.py:200`), 1 × `# ty: ignore[call-non-callable]` (`mcp/server.py:308`).
- Total: 10.

ty diagnostics: 164 → 125 (-39). All `invalid-argument-type` / `invalid-assignment` / `call-non-callable` errors in `src/` are now resolved or suppressed in ty's native syntax.

## Wave T3 (ty zero across the repo)

T3 closes out ty diagnostics in `tests/` and `examples/`. Before: 125 (97 tests + 28 examples). After: 0.

### T3a — examples/ (28 → 0)

Two real bugs in user-facing examples plus mypy-syntax mismatch:

- All 6 `examples/*.py` called `builder.add_terminal(tm_id="X1", ...)` and `builder.add_spdt(tag_prefix="K", ...)`. Both `tm_id` and `tag_prefix` are positional-only (`/` after them in the signature). ty correctly flagged this as `positional-only-parameter-as-kwarg` / `missing-argument`. Real fix: convert all sites to positional. 25 `add_terminal` sites + 2 `add_spdt` sites changed across all 6 files.
- `examples/06_full_cabinet.py:35` imported `Project` from `schematika`, but `Project` is not re-exported there (`schematika/__init__.py` only does `from .electrical import *`, and `electrical` does not re-export `Project`). The example failed at runtime with `ImportError` before reaching any logic. Real fix: `from schematika.project import Project`. No suppression.

All 6 examples now run without error. No `# ty: ignore` introduced in examples.

### T3b — tests `unresolved-import` / `unresolved-attribute` (32 → 0)

Optional-dep imports + ty narrowing limits.

- 22 × `# ty: ignore[unresolved-import]` on `import skidl` / `from skidl import ...` across 11 `tests/unit/test_pcb_*.py` files — Wave T3b — Why: `skidl` is in `[project.optional-dependencies] pcb`. The `tests/unit/test_pcb_*.py` collection runs only when the user has synced with `--extra pcb`; under base sync these tests fail at collection by design (and pytest is configured with `--continue-on-collection-errors` for the same reason). Per-line ignore is preferred over a `tests/**` per-file-ignore here because it documents intent at every site and keeps the suppression footprint bounded to the actual import lines (≤2 lines per file).
- 1 × `# ty: ignore[unresolved-import]` on `from openpyxl import load_workbook` in `tests/unit/project/test_bom_export.py:15` — Wave T3b — Why: `openpyxl` is in `[project.optional-dependencies] excel`. Same rationale as skidl.
- 7 × `# ty: ignore[unresolved-attribute]` in `tests/unit/test_block_v2.py` — Wave T3b — Why: ty cannot narrow `Block.placement: Placement | None` to non-None across builder calls like `b.below(a)`, `b.right_of(a)`, `b.mirror(...)`. Each of these mutators sets `placement` internally but their return type / side-effect is not modelled in a way ty can use. Sites: lines 109 (`align`), 115 (`kind`), 121, 127, 228, 238, 539. Adding runtime `assert b.placement is not None` would add 7 lines of test-body churn for no value.
- 2 × `# ty: ignore[unresolved-attribute]` in `tests/unit/test_wire_labels.py:145-146` — Wave T3b — Why: `c_new.elements: tuple[Element, ...]` and the test indexes `[2]`/`[3]` then asserts `.content`. `.content` is on the `Text` subclass, not the `Element` base. ty does not narrow on the indexed value. The structural fix would require an `isinstance(elem, Text)` runtime narrow that the test doesn't otherwise need.

### T3c — tests `invalid-argument-type` / `invalid-assignment` / `call-non-callable` / `unsupported-operator` (65 → 0)

Two phases.

#### T3c-1: mypy → ty syntax conversion (mechanical)

55 sites across 24 test files where `# type: ignore[<rule>]` was inert under ty (mypy comment syntax). Converted to `# ty: ignore[<rule>]` using the rule-code mapping:

| mypy code | ty code |
| --- | --- |
| `misc` (frozen-dataclass assign) | `invalid-assignment` |
| `attr-defined` | `unresolved-attribute` |
| `arg-type` | `invalid-argument-type` |
| `assignment` | `invalid-assignment` |
| `unsupported-operator` | `unsupported-operator` |

11 of the conversions reduced ty's diagnostic count immediately; the remaining 44 covered errors that ty doesn't flag at the same site (e.g. `tool=skidl.SKIDL` — ty doesn't flag attribute access on an unresolved module, so the directive becomes `unused-ignore-comment`). T3c-2 handles those.

#### T3c-2: residual suppressions + stale-ignore prune

32 new per-line suppressions for residual ty diagnostics that have no mypy precedent (T2 already moved equivalent fixes in `src/` to ty syntax; ty 0.0.32 just surfaces more of the same patterns in tests). All sites are tests passing duck-typed mocks where the type mismatch is the *intent* of the test:

- `tests/unit/test_builder.py:190, 207, 219, 1112` — 4 × `invalid-argument-type` — Wave T3c-2 — Why: `ComponentSpec(func=lambda: None, ...)` uses a no-op stub for `func: ((...) -> Symbol) | None`. The lambda returns `None`, which doesn't satisfy the `Symbol` return type. The `func` is never invoked in these unit tests (they exercise sibling fields).
- `tests/unit/test_layout.py:748-749, 771-772, 875` — 5 × `invalid-argument-type` — Wave T3c-2 — Why: tag-generator merging tests pass `dict[str, str]` to a parameter typed `dict[str, (...) -> Unknown]` to verify dict-merge semantics independent of generator-call semantics. The tagged values are never invoked.
- `tests/unit/test_pcb_internal_invariants.py:184-185, 194, 288, 299, 309, 567` — 7 × `invalid-argument-type` — Wave T3c-2 — Why: tests construct `_other_pin` callers and pcb-internal helpers with `SimpleNamespace` doubles standing in for `NetRef` / `PinRef`. Same SimpleNamespace pattern as T1b's mock-style suppressions but in tests.
- `tests/unit/test_pcb_label_symbol.py:148, 163, 177, 193, 211, 226, 241` — 7 × `invalid-argument-type` — Wave T3c-2 — Why: `_NetEndpointTerminator(net=SimpleNamespace(...), ...)` — same pattern; `net` is typed `NetRef`.
- `tests/unit/test_pcb_model.py:149` — 1 × `invalid-argument-type` — Wave T3c-2 — Why: `_Column.__getitem__` typed `dict[Terminal, str]` indexed by a string literal; tests use string keys interchangeably with Terminal (which is `str` subclass).
- `tests/unit/test_pid_diagram.py:32, 55, 108` — 3 × — Wave T3c-2 — Why: `compute_bounding_box` test passes object that lacks bounding-box protocol; assignment tests assign on a frozen field for invariant checks.
- `tests/unit/test_pid_validation.py:23` — 1 × — Wave T3c-2 — Why: same pattern as test_pid_diagram.
- `tests/unit/test_project.py:1487` — 1 × — Wave T3c-2 — Why: `update_csv_with_internal_connections` test passes a stub instead of the full project type.
- `tests/unit/test_terminal_bridges.py:30` — 1 × — Wave T3c-2 — Why: `Connection.__init__` typed argument receives a string literal that subclasses `Terminal`.
- `tests/unit/test_terminal_type.py:39` — 1 × — Wave T3c-2 — Why: `Terminal` literal-comparison test exercises a path ty's narrowing doesn't follow.
- `tests/unit/test_typst_compiler.py:49, 228` — 2 × — Wave T3c-2 — Why: `TypstCompilerConfig(**defaults)` test passes string defaults that resolve to bool fields; `compiler._rel_path(abs_path)` test passes a Path where the method type expects `str`. Both are deliberate API stress tests.

**Pruned** in T3c-2: 22 × `# ty: ignore[unresolved-attribute]` on `tool=skidl.SKIDL,` lines across 11 pcb test files. After T3c-1 converted these from `# type: ignore[attr-defined]`, ty flagged them as `unused-ignore-comment` because under base-sync (skidl unresolved) ty does not surface attribute access on an unknown module. The original mypy directive was conditionally useful only when skidl *was* installed; under ty's resolution model it is dead noise. Removed.

### Summary

- Mypy `# type: ignore` converted to ty syntax: 55 (T3c-1).
- New `# ty: ignore[<rule>]` introduced (net): 32 (T3c-2 residuals) + 23 (T3b unresolved-import) + 9 (T3b unresolved-attribute) = 64.
- Stale ignores pruned: 22 (skidl.SKIDL `unused-ignore-comment`).
- Real bug fixes: 1 (`Project` import path in `examples/06_full_cabinet.py`).
- Real API-style fixes: 27 sites across all 6 examples (`tm_id` / `tag_prefix` from kwarg → positional).
- pyproject changes: none (no `tests/**` per-file-ignore added; per-line preferred for traceability).

ty diagnostics: 125 → 0. All checks passed.

## Wave T4 (annotation completeness)

T4 enables ruff's `ANN` rule set: 2292 baseline errors → 0. Of those, 2166
were in `tests/` and `examples/` and were cleared by per-file-ignore (T4a).
The 126 errors in `src/` were ratcheted to zero via auto-fix (T4b) and
manual annotation (T4c).

### T4a — per-file-ignore for `tests/**` and `examples/**`

`pyproject.toml` `[tool.ruff.lint.per-file-ignores]`:
- `tests/**` — `ANN` appended to existing list (`["D", "ARG", "PLR2004", "PLR0913", "S101", "S108", "ANN"]`).
- `examples/**` — new entry: `["ANN"]`.

Why: ANN's intent is library-API annotation discipline. Tests use pytest
fixtures and assertions where `-> None` / `*args: object` adds noise without
information; examples are demonstration scripts where signature-completeness
is not the audience's concern. Clearing these via config (instead of per-line
or per-file `# noqa`) reflects that the rule is correctly scoped to library
code.

Effect: -2166 errors (2292 → 126).

### T4b — auto-add return type annotations in `src/`

`ANN` added to `[tool.ruff.lint].select`. `ruff check src --select ANN
--fix --unsafe-fixes` resolved 43 of 126 errors:

- 17 ANN204 special methods (`__init__` / `__post_init__`) → `-> None`.
- 20 ANN201/ANN202 procedures → `-> None`.
- 5 nested-helper closures (`expand`/`process`/`_collect`/`draw_rect`) → `-> None`.
- 1 ANN201 (`mcp/server.py:_timeout_handler`) → `-> Never` (raises unconditionally).

`ruff format src` reflowed one `Project` method signature. No semantic
changes; ty held at 0, pytest held at 1827 passing.

Effect: -43 errors (126 → 83).

### T4c — manual annotations and `# noqa: ANN401` for genuine `Any`

The 83 residual errors broke down as 35 ANN001 (missing arg types), 8 ANN003
(`**kwargs` no type), 11 ANN202 / 2 ANN204 / 1 ANN201 (return types not
inferable), and 26 ANN401 (explicit `Any` rejections).

#### Real annotations (ANN001 / ANN002 / ANN003 / ANN201 / ANN202 / ANN204)

- `core/renderer.py:60,67` — `_expand(x: float, y: float)` and `process(elem: Element)` typed.
- `core/traversal.py:32` — `_collect(elem: Element)`.
- `catalog/cables.py:76`, `catalog/registry.py:48` — `__iter__` typed `Iterator[CableSpec]` / `Iterator[CatalogDevice]`.
- `electrical/builder.py:783,1255` — closures (`fixed_gen`, `_single_instance_gen`) typed against `GenerationState`.
- `electrical/builder_utils.py:62` — `_merge_dict_of_lists(dicts: Iterable[dict])`.
- `electrical/cable_export.py:26-117` — five private CSV writers typed against `ConnectorData` / `FieldDevice` / `CableData` / `_csv.DictWriter`.
- `mcp/server.py:45,51,187,306` — module/symbol/timeout-handler/render-patcher typed (`ModuleType` / `Callable[..., Any] | None` / `FrameType | None` / `(circuits, filename, **kwargs) -> object`).
- `pid/symbols/valves.py:32-70` — six private helpers typed (`tuple[Polygon, Polygon]`, `dict[str, Port]`, `tuple[Line, Line]`, `Element`).
- `project.py:1366` — `_render_multi_circuit_pages` typed against `dict[str, str]`.
- `rendering/typst/frame_generator.py:29,57` — `generate_frame(font_family: str) -> Circuit` and `draw_rect(x1: float, ...)`.

Two nested helpers were renamed (`expand` → `_expand` in `core/renderer.py`,
`single_instance_gen` → `_single_instance_gen` in `electrical/builder.py`)
to keep `scripts/api_style_gate.py` green: the gate's "x,y scalars without
position: Point" check is scoped to public API and skips `_`-prefixed names.

#### `# noqa: ANN401` (Any deliberate)

Per-line suppressions with one-line rationale. Two categories: kwargs
forwarders and duck-typed boundaries.

**`**kwargs: Any` forwarders** — public/private builder methods that pass
arbitrary keyword arguments through to underlying constructors or factories:

- `src/schematika/block/diagram.py:59` — `BlockDiagram.block(**kwargs: Any)` — Wave T4c — Why: forwards to `Block.__init__`; T2a SUPPRESSIONS already documents this widening.
- `src/schematika/block/model.py:164` — `Block.block(**kwargs: Any)` — Wave T4c — Why: same; child-block forwarder.
- `src/schematika/core/parts.py:392` — `_factory(**kwargs: Any)` — Wave T4c — Why: pin-symbol factory closure forwards to `Symbol(...)` constructor.
- `src/schematika/electrical/builder.py:151` — `CircuitBuilder.add_terminal(**kwargs: Any)` — Wave T4c — Why: forwards to `Terminal` / symbol factory.
- `src/schematika/electrical/builder.py:390` — `CircuitBuilder.add_symbol(**kwargs: Any)` — Wave T4c — Why: forwards to symbol factory.
- `src/schematika/electrical/builder.py:751` — `CircuitBuilder.add_reference(**kwargs: Any)` — Wave T4c — Why: forwards to reference symbol factory.
- `src/schematika/electrical/symbols/references.py:27` — `ref(**kwargs: Any)` — Wave T4c — Why: symbol factory keeps the universal builder-API kwargs surface for compatibility.
- `src/schematika/mcp/server.py:307` — `patched_render(**kwargs: Any)` — Wave T4c — Why: signature mirrors the patched `render_system` whose true kwargs vary.
- `src/schematika/pcb/builder.py:281,294,665` — `_label_symbol_factory.factory(*args, **kwargs: Any)` and `_placed_symbol_for_connector_terminator.factory(*args, **kwargs: Any)` and `make_factory._f(*args, **kwargs: Any)` — Wave T4c — Why: closures returned to `CircuitBuilder.add_symbol`; the surface is whatever the underlying base factory accepts.
- `src/schematika/pid/builder.py:195` — `PIDBuilder.add_equipment(**kwargs: Any)` — Wave T4c — Why: forwards to symbol factory.
- `src/schematika/pid/builder.py:270` — `PIDBuilder.add_instrument(**kwargs: Any)` — Wave T4c — Why: forwards to instrument-bubble factory.
- `src/schematika/project.py:265` — `Project.add_circuit_descriptors(**kwargs: Any)` — Wave T4c — Why: descriptor builder kwargs.
- `src/schematika/project.py:294` — `Project.add_circuit(**kwargs: Any)` — Wave T4c — Why: forwarded into the user's builder function.
- `src/schematika/project.py:340` — `_reserve_fn(**_kwargs: Any)` — Wave T4c — Why: closure conforming to the `(state, **kwargs) -> BuildResult` builder protocol.

**Duck-typed boundaries / dynamic dispatch (`obj: Any` / `circuit: Any`)** —
explicit `Any` for parameters whose true type lives in an unstubbed third-party
package (SKiDL) or is opaque outside the originating module:

- `src/schematika/core/transform.py:209` — `rotate(obj: Any, ...) -> Any` — Wave T4c — Why: `@singledispatch` base function; the registered overloads carry the precise types. The base must accept anything to dispatch.
- `src/schematika/electrical/layout/layout.py:206` — `layout_horizontal(start_state: Any, ...)` — Wave T4c — Why: `GenerationState` is defined in `electrical/model/state` and is opaque to the layout module; using `Any` avoids a circular import for a parameter that this module only forwards.
- `src/schematika/electrical/layout/layout.py:243` — `create_horizontal_layout(state: Any, ...)` — Wave T4c — Why: same.
- `src/schematika/pcb/adapter.py:12` — `template_name(template: Any) -> str` — Wave T4c — Why: duck-typed SKiDL `Part`/template (no stubs); the function is the boundary.
- `src/schematika/pcb/adapter.py:56` — `adapt(circuit: Any) -> CircuitIR` — Wave T4c — Why: SKiDL `Circuit`; explicit boundary at the IR layer.
- `src/schematika/pcb/builder.py:192` — `_should_rotate(symbol_factory: Any, ...)` — Wave T4c — Why: a `SymbolFactory` callable whose true signature varies; the function only inspects `.ports`.
- `src/schematika/pcb/builder.py:278` — `_label_symbol_factory(...) -> Any` — Wave T4c — Why: returns a closure conforming to whatever `add_symbol` consumes; explicit `Callable[..., Symbol]` would not change the runtime contract and triggers parameter-shape friction in callers.
- `src/schematika/pcb/builder.py:651` — `_render_column_to_circuit(state: Any, ...)` — Wave T4c — Why: same `GenerationState` opacity reason as `layout/`.
- `src/schematika/pcb/builder.py:728` — `build(circuit: Any, ...)` — Wave T4c — Why: SKiDL `Circuit` boundary.
- `src/schematika/pcb/builder.py:780` — `_render_and_pack(state: Any, ...)` — Wave T4c — Why: same `GenerationState` opacity.
- `src/schematika/pcb/model.py:22` — `_template_pin_nums(template: Any)` — Wave T4c — Why: duck-typed SKiDL template.
- `src/schematika/project.py:384` — `Project.add_pid(builder_or_factory: Any)` — Wave T4c — Why: accepts either a `PIDBuilder` instance or a `(state) -> PIDBuildResult` factory; widening the type into a union would surface as a type-narrowing burden on every caller.
- `src/schematika/project.py:475` — `Project.add_block_diagram(builder_or_factory: Any)` — Wave T4c — Why: same dispatch-on-shape pattern as `add_pid`.

Net ruff: 172 → 170 (the small drop is from incidental `# noqa: F401`
redundancies cleared by the new TC003 / TC004 fixups). ty: 0 → 0.

## Wave P1 (tooling refresh + Python 3.14)

- Dev tool floors raised to current latest stable: `ruff>=0.15.12`, `ty>=0.0.32`, `vulture>=2.16`, `pytest>=9.0.3`, `pre-commit>=4.6.0`, `mutmut>=3.5.0`. No suppressions; pure floor bump.
- `requires-python = ">=3.14"` (was `">=3.13,<3.14"`); new `.python-version` pin = `3.14`. ty infers Python target from `requires-python` per its docs. **Ruff `target-version` held at `"py313"` (not bumped to `"py314"`)** — ruff 0.15.12's formatter under `target-version = "py314"` rewrites `except (ValueError, TypeError):` to `except ValueError, TypeError:`, which is invalid Python 3 syntax. Comment in `pyproject.toml:[tool.ruff]` records the rationale; revisit when the upstream bug is fixed.
- darglint (upstream `terrencepreilly/darglint`, unmaintained since 2024) replaced with `darglint2>=1.8.2` (active fork at `akaihola/darglint2`). Hook id and entry in `.pre-commit-config.yaml` updated to match. Initial darglint2 violation count: 993 (later dropped entirely in Wave Q-Slim — see below).

## Wave Q-Slim (drop bandit / radon / docstr-coverage / darglint2)

Four dev tools removed because they duplicate ruff or contradict the docstring style enforced by the `python-coding-and-tooling` skill.

- **`bandit`** dropped — Why: `select = [..., "S"]` (Wave R8a) covers the same security checks via flake8-bandit, faster, with a single config. `[tool.bandit]` section also removed.
- **`radon` (cc + mi)** dropped — Why: `select = [..., "C90", "PLR"]` plus the threshold relaxations in Wave R7c (`max-complexity = 22`, `max-branches = 22`, `max-returns = 10`, `max-statements = 70`) cover complexity. Radon's reports duplicate this with a separate config.
- **`docstr-coverage`** dropped — Why: `select = [..., "D"]` flags missing docstrings per-site. The aggregate % is not actionable. `.docstr.yaml` deleted; the P1 swap from `interrogate` was correct in its own right but the underlying check was already redundant.
- **`darglint2`** dropped — Why: this tool enforces signature/docstring agreement, which contradicts the `python-coding-and-tooling` skill's docstring-style rule (short, WHY-only, do NOT restate the signature). The 993 darglint2 violations on this codebase mostly reflect AI-bloat docstrings that should be *deleted*, not made pydoclint-clean. No replacement (no `pydoclint`); ruff `D` covers presence + format, ty catches signature drift, and the audit lens is `reviewing-ai-generated-python` smell #4.

Pre-commit hooks for these four removed; `docs/TOOLING.md` updated with a "deliberately not used" section. The `python-coding-and-tooling` skill's "Forbidden Toolchain" table makes this enforceable for new code in any of this user's Python projects.

Net effect: 4 dev deps removed, 5 pre-commit hooks removed, `[tool.bandit]` section + `.docstr.yaml` deleted. ty: 0 → 0. ruff: 170 → 170.

## Follow-ups (post-R7)

- **`_phase1_tag_and_state` (`electrical/builder_phases.py`)**: complexity covered by the relaxed `max-branches = 22`, but R7 reviewer flagged this function as having extractable sub-logic (terminal-ID resolution + Y-position computation could become two helpers). Not fixed in R7 because it would mean either: (a) a non-trivial refactor that wants its own commit story, or (b) widening the scope of an already heavy wave. Tracked as a follow-up.

## Wave L3a (drive ruff to 0)

This wave cleared the 68 residual ruff errors after the L1/L2 hardening:
~50 source-fixes (line shrinks, signature underscoring, simplified
SIM/PERF flow, PEP 695 generics on `pure`/`translate`, `Union[...]` →
`X | Y` in `electrical/field_devices.py`, dict-key→`in dict` fix-ups,
SIM117 `with`-combiners), 9 per-line `# noqa` for genuine API surfaces,
and 2 config-level entries:

- `[tool.ruff.lint.per-file-ignores] "__init__.py"` — appended `F403` —
  Wave L3a — Why: 13 sites, all package shims that re-export with
  `from .x import *` and ship explicit `__all__` lists (added in L1).
  F403 is the rule that flags those re-exports as undetectable; the
  underlying purpose (catching star imports without `__all__`) doesn't
  apply here. Per-line `# noqa` would touch 13 lines across 8 shim
  files for one rule whose intent is already met structurally.

- `.pre-commit-config.yaml ty-check hook gains `files: ^(src|tests)/`` —
  Wave L3a — Why: aligns with the `ruff-format` and `ruff-check` hooks
  (already scoped to `src|tests`). Without this scope, `pre-commit run
  --all-files` ran ty over `tools/cad_parser/` and surfaced two
  `unresolved-attribute` diagnostics on `pymupdf` duck-typed `page`
  objects (out of scope per `[tool.ty.src] exclude = ["tools/"]` —
  T0b — but ty respects pyproject excludes only on full-tree runs, not
  on per-file invocations from pre-commit). The hook scope brings the
  pre-commit gate in line with the canonical `uv run ty check` gate
  (which already passes). No source change to `tools/`.

### Per-line `# noqa` added in L3a

- `src/schematika/block/rendering.py:152` — `_all_blocks` rename (not
  noqa — used positional naming convention). Reported here for
  completeness.
- `src/schematika/block/rendering.py:251` — `_offset` rename.
- `src/schematika/core/transform.py:172` — `# noqa: ANN401, ARG001`
  on `rotate(obj, angle, center)` — singledispatch base; the params
  are required by the dispatch protocol but the default handler
  warns + returns unchanged.
- `src/schematika/electrical/symbols/blocks.py:99` — `# noqa: ARG001`
  on `psu(label, pins)` — `pins` kept for the symbol-factory protocol.
- `src/schematika/electrical/symbols/references.py:24,27` —
  `# noqa: ARG001` on `pins` and `**kwargs` — same protocol reason.
- `src/schematika/pid/symbols/vessels.py:114` — `# noqa: ARG001` on
  `kind=` — accepted at the API surface for forward-compat with
  multi-kind heat exchangers, but only one kind implemented today.
- `src/schematika/project.py:360` — `# noqa: ARG002` on
  `add_field_devices(..., reuse_terminals=)` — reserved API
  parameter (docstring already says "reserved (ignored)").
- `src/schematika/electrical/model/constants.py:16,149` —
  `# noqa: E402` (alongside the existing `# noqa: I001`) on the two
  deferred imports that are intentional per CLAUDE.md "Import-order-
  sensitive files".

### Complexity threshold near-the-line offenders

Recorded so a future PR notices when a refactor would *cross* a
threshold and require justification. Numbers are at L3a freeze:

- `[mccabe] max-complexity = 22` (frozen). Highest current values:
  - `electrical/builder_phases.py:397 _phase4_render_graphics` — 22
  - `electrical/builder_phases.py:144 _phase2_register_connections` — 21
  - `electrical/builder.py:908 build` — 18
- `[pylint] max-args = 16` (frozen). Highest current values:
  - `electrical/builder.py:81 CircuitBuilder.add_terminal` — 16
  - `electrical/builder.py:278 CircuitBuilder.add_symbol` — 13
- `[pylint] max-returns = 10` (frozen). Highest current value:
  - `core/transform.py:33 translate` — 10 (singledispatch base).
- `[pylint] max-branches = 22` (frozen). Highest current values:
  - `electrical/builder_phases.py:144 _phase2_register_connections` — 22
  - `electrical/builder_phases.py:397 _phase4_render_graphics` — 21
- `[pylint] max-statements = 70` (frozen). Highest current value:
  - `electrical/builder_phases.py:144 _phase2_register_connections` — 69

Future violators of these thresholds must either fix the function or
add a SUPPRESSIONS.md entry with a substantive `Why:` and a per-line
`# noqa: <CODE>` — not bump the threshold.

## Wave Q1 (audit & shrink AI-inflated docstrings)

No new ruff suppressions. The wave is pure deletion / shrinkage of docstring text; no `# noqa` comments were added in src/. ruff total dropped 170 → 164 (incidental: long-summary lines that broke E501 disappeared along with their `Args/Returns` blocks).

Wave-specific notes worth recording (not suppressions per se):

- **Module-level multi-line docstrings kept on purpose:** `electrical/plc_resolver.py` documents the PLC tag-form + pin-suffix conventions (RTD `+R/RL/-R`, 4-20mA `Sig/GND`, DI/DO no suffix) that don't live in any signature. Every other module docstring was collapsed to one line.
- **Multi-line shrunk-but-not-single-line:** ~80 docstrings retained 2 lines because the WHY genuinely needed it (e.g. the three numbering modes on `PinDef`; the four-phase orchestrator in `_create_single_circuit_from_spec`). The rule isn't "all docstrings must be 1 line"; it's "no `Args/Returns/Raises` blocks that paraphrase the signature."
- **Tools added (gitignored):** `claude-tools/count_docstrings.py` and `claude-tools/list_multiline_docstrings.py`. Replicated from the parent checkout because worktrees don't share `claude-tools/`.

## Wave C2b (code-review cleanup)

- `tests/unit/core/test_options.py:119` — `# ty: ignore[missing-argument]` — Wave C2b — Why: `test_required_tag_prefix` intentionally calls `SymbolConfig()` without the required `tag_prefix` argument to assert `TypeError` is raised. The call is the point of the test; the type error is expected. The ignore suppresses ty's `missing-argument` diagnostic so CI stays green while the test still runs and catches regressions.

## Wave C2d-1 (add_reference + add_equipment bundling)

- `tests/unit/core/test_options.py` — `# ty: ignore[missing-argument]` on `EquipmentConfig()` — Wave C2d-1 — Why: `test_required_factory_and_tag_prefix` intentionally calls `EquipmentConfig()` without the required `factory` and `tag_prefix` arguments to assert `TypeError` is raised. The call is the point of the test; the type error is expected. Matches the C2b SymbolConfig precedent.

## Wave C2d-2 (CircuitBuilder.build bundling into BuildOptions)

- `tests/unit/core/test_options.py` — `# ty: ignore[too-many-positional-arguments]` on `BuildOptions(None)` — Wave C2d-2 — Why: `test_kw_only` intentionally passes a positional argument to a kw_only dataclass to assert `TypeError` is raised. The call is the point of the test; the type error is expected. Matches the C2b/C2d-1 test_kw_only precedent.
