# API curation — pcb (v2)

**Source:** `src/schematika/pcb/__init__.py`, `src/schematika/pcb/advanced.py`, `src/schematika/pcb/builder.py`, `src/schematika/pcb/errors.py`, `src/schematika/pcb/model.py`.
**Last updated:** 2026-05-05 (Phase 1 v2 scaffold)
**Status:** CURRENT — v2 public surface is finalized.

> Phase 1 changes:
> - Refactored to two-tier surface: Tier-1 (`schematika.pcb`) exposes only `build()`, `review()` stub, and `PCBBuildError`.
> - All v2 model types and error classes moved to `schematika.pcb.advanced` for power users.
> - Removed v1 leftovers: `A3_LANDSCAPE`, `A4_LANDSCAPE`, `HeightOverflowError`, `OrphanSliceError`.
> - Package is aspirational (no external consumers yet) but intentionally exposed for SKiDL bridge users.

## Tier-1: Top-level `schematika.pcb`

| Symbol | Kind | In `__all__` | Status |
|---|---|---|---|
| `build` | function | yes | KEEP (primary entry point, documented) |
| `review` | function | yes | KEEP (stub for v2 phase 2+) |
| `PCBBuildError` | exception | yes | KEEP (user-facing error base class) |

## Tier-2: `schematika.pcb.advanced`

### Errors

| Symbol | Kind | In `__all__` | Status |
|---|---|---|---|
| `DuplicateMappingError` | exception | yes | KEEP (power-user error) |
| `IncompleteSliceError` | exception | yes | KEEP (power-user error) |
| `MultiPinSliceError` | exception | yes | KEEP (power-user error) |
| `PinNotOnTemplateError` | exception | yes | KEEP (power-user error) |
| `PortNotOnSymbolError` | exception | yes | KEEP (power-user error) |
| `UnmappedPartError` | exception | yes | KEEP (power-user error) |
| `UnnamedNetError` | exception | yes | KEEP (power-user error) |

### Model Types

| Symbol | Kind | In `__all__` | Status |
|---|---|---|---|
| `Column` | dataclass | yes | KEEP (power-user model) |
| `ConnectorBlock` | dataclass | yes | KEEP (power-user model) |
| `ConnectorMap` | dataclass | yes | KEEP (power-user model) |
| `FloatingPart` | dataclass | yes | KEEP (power-user model) |
| `Page` | dataclass | yes | KEEP (power-user model) |
| `PCBBuildResult` | dataclass | yes | KEEP (returned by `build()`) |
| `PinColumns` | dataclass | yes | KEEP (power-user model) |
| `PinPlacement` | dataclass | yes | KEEP (power-user model) |
| `PlacedSlice` | dataclass | yes | KEEP (power-user model) |
| `PowerNetMap` | dataclass | yes | KEEP (power-user model) |
| `SymbolMap` | dataclass | yes | KEEP (power-user model) |
| `SymbolMapping` | dataclass | yes | KEEP (power-user model) |
| `SymbolSlice` | dataclass | yes | KEEP (power-user model) |
| `Terminator` | dataclass | yes | KEEP (power-user model) |

## Summary

- Tier-1 symbols: 3 (all KEEP)
- Tier-2 symbols: 21 (all KEEP)
- v1 leftovers removed: `A3_LANDSCAPE`, `A4_LANDSCAPE`, `HeightOverflowError`, `OrphanSliceError`

> Rationale: The v2 scaffold consolidates the public surface into a clean two-tier API. Tier-1 is for typical users (`build()` and error handling). Tier-2 re-exports power-user types that SKiDL-bridge developers will construct and pass to v2 builders. All v1 constants and error classes that don't map to v2 semantics have been removed.
