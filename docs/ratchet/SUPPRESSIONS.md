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

## Follow-ups (post-R7)

- **`_phase1_tag_and_state` (`electrical/builder_phases.py`)**: complexity covered by the relaxed `max-branches = 22`, but R7 reviewer flagged this function as having extractable sub-logic (terminal-ID resolution + Y-position computation could become two helpers). Not fixed in R7 because it would mean either: (a) a non-trivial refactor that wants its own commit story, or (b) widening the scope of an already heavy wave. Tracked as a follow-up.
