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

## Wave R7b (PLR0913 too-many-args)

- `[tool.ruff.lint.pylint] max-args = 16` — Wave R7b — Why: Schematika's API style (see `docs/API_STYLE.md`) mandates ≤1 positional identity argument + all other parameters as keyword-only for all `add_*`/builder methods. This is enforced by the `api_style_gate.py` script. 8 of the 10 flagged functions are public builder methods that legitimately need many independent keyword-only parameters; bundling them into dataclasses would require callers to construct config objects for what are really flat option sets. The ceiling of 16 is set by `CircuitBuilder.add_terminal` (self + 1 positional + ~14 keyword-only). Public builder/factory functions: `CircuitBuilder.add_terminal` (16), `CircuitBuilder.add_symbol` (13), `CircuitBuilder.add_spdt` (12), `build_from_descriptors` (12), `CircuitBuilder.build` (11), `PIDBuilder.add_equipment` (10), `create_horizontal_layout` (9), `CircuitBuilder.add_reference` (9). Two private helpers (`_walk_loop` (9), `_route_one_cable` (9)) are also covered by the relaxed limit; these are non-trivial pipeline helpers in domains (PCB traversal, cable routing) where splitting parameters into a config dataclass would be over-engineering for internal code, but they do **not** fall under the public builder/factory contract — they're grandfathered under the same threshold rather than re-justified.

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

## Wave P1 (tooling refresh + Python 3.14)

- Dev tool floors raised to current latest stable: `ruff>=0.15.12`, `ty>=0.0.32`, `vulture>=2.16`, `pytest>=9.0.3`, `pre-commit>=4.6.0`, `mutmut>=3.5.0`. No suppressions; pure floor bump.
- `requires-python = ">=3.14"` (was `">=3.13,<3.14"`); new `.python-version` pin = `3.14`. ty infers Python target from `requires-python` per its docs. **Ruff `target-version` held at `"py313"` (not bumped to `"py314"`)** — ruff 0.15.12's formatter under `target-version = "py314"` rewrites `except (ValueError, TypeError):` to `except ValueError, TypeError:`, which is invalid Python 3 syntax. Comment in `pyproject.toml:[tool.ruff]` records the rationale; revisit when the upstream bug is fixed.
- darglint (upstream `terrencepreilly/darglint`, unmaintained since 2024) replaced with `darglint2>=1.8.2` (active fork at `akaihola/darglint2`). Hook id and entry in `.pre-commit-config.yaml` updated to match. Initial darglint2 violation count: 993 (Q1 will ratchet).

## Follow-ups (post-R7)

- **`_phase1_tag_and_state` (`electrical/builder_phases.py`)**: complexity covered by the relaxed `max-branches = 22`, but R7 reviewer flagged this function as having extractable sub-logic (terminal-ID resolution + Y-position computation could become two helpers). Not fixed in R7 because it would mean either: (a) a non-trivial refactor that wants its own commit story, or (b) widening the scope of an already heavy wave. Tracked as a follow-up.
