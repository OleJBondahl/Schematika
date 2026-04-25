# Ratchet suppressions

Suppressions added during quality ratchet waves. Each entry includes the file, rule, wave, and justification.

## Wave R2a (RUF)

- `src/schematika/electrical/__init__.py:140` — `# noqa: RUF022` — Wave R2a — Why: `__all__` is grouped by category (Core, Symbol factories, Constants, Utilities, Devices, PLC, Exceptions) for readability. Sorting alphabetically would destroy the intentional grouping that helps users find exports.

- `src/schematika/pcb/__init__.py:28` — `# noqa: RUF022` — Wave R2a — Why: `__all__` is grouped by sub-module (builder, errors, model) for readability. Sorting alphabetically would mix the logical sections.

## Wave R5 (N-series naming)

- `tests/unit/test_pcb_adapter.py` — `[N806]` in per-file-ignores — Wave R5 — Why: tests use IEC fuse/terminal designators (F1, F2, F3, T1, _F1, _F2, _F3) as fixture identifiers; lowercasing would lose intent and misrepresent IEC naming conventions.

- `tests/unit/test_plc_resolver.py` — `[N806, N817]` in per-file-ignores — Wave R5 — Why: N806 covers `DI_MODULE_1CH` (PLC channel-count identifier, uppercase is conventional); N817 covers `PD`/`PMT`/`PR` import aliases for `PlcDesignation`/`PlcModuleType`/`PlcRack` (acronym aliases aid readability in dense PLC resolver tests).

- `tests/unit/test_terminal_type.py` — `[N817]` in per-file-ignores — Wave R5 — Why: `T` is the conventional single-letter alias for `Terminal` in IEC context test fixtures; renaming would reduce clarity.
