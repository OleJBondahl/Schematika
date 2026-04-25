# API curation — core

**Source:** `src/schematika/core/__init__.py` (which leaks names from `geometry`, `symbol`, `primitives`, `bbox`, `exceptions`).
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - `core/__init__.py` has **NO `__all__`**. Every top-level non-underscored name imported there is leaked-public.
> - Per CLAUDE.md invariants, `core/` is the foundation: domain packages import from it, but `core/` itself is documented as a layer that "is I/O-free" rather than as a public API. The expected user surface is the domain packages (`electrical`, `pid`, `pcb`, etc.), not `schematika.core`.
> - Several `core` exception types ARE part of the documented error contract — they are re-exported by `electrical/exceptions.py` and listed in `electrical.__all__`. Whether `schematika.core` should also expose them directly is the question for the user.
> - Other internal-by-convention symbols include `Element`, `Point`, `Style`, `Vector`, `Symbol`, `Port`, `Circle`, `Group`, `Line`, `Path`, `Polygon`, `Text`, `BoundingBox`, `compute_bounding_box`. Consumer never imports `from schematika.core …`.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `Element` | dataclass | `core/geometry.py:59` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 2 | `Point` | dataclass | `core/geometry.py:25` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 3 | `Style` | dataclass | `core/geometry.py:47` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 4 | `Vector` | dataclass | `core/geometry.py:7` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 5 | `Port` | dataclass | `core/symbol.py:14` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 6 | `Symbol` | class | `core/symbol.py:30` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 7 | `SymbolFactory` | type alias | `core/symbol.py:48` | leaked-public | no | no | MAKE_INTERNAL (note: re-exported via `electrical.__all__`, see `electrical.md`) | _ |
| 8 | `Circle` | dataclass | `core/primitives.py:18` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 9 | `Group` | dataclass | `core/primitives.py:48` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 10 | `Line` | dataclass | `core/primitives.py:9` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 11 | `Path` | dataclass | `core/primitives.py:40` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 12 | `Polygon` | dataclass | `core/primitives.py:56` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 13 | `Text` | dataclass | `core/primitives.py:27` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 14 | `BoundingBox` | dataclass | `core/bbox.py:20` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 15 | `compute_bounding_box` | function | `core/bbox.py:109` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 16 | `CircuitValidationError` | exception | `core/exceptions.py:4` | leaked-public (also re-exported in `electrical.__all__`) | no | no | MAKE_INTERNAL (canonical surface is `schematika.<name>` via electrical re-export) | _ |
| 17 | `ComponentNotFoundError` | exception | `core/exceptions.py:30` | leaked-public (also re-exported in `electrical.__all__`) | no | no | MAKE_INTERNAL | _ |
| 18 | `PortNotFoundError` | exception | `core/exceptions.py:16` | leaked-public (also re-exported in `electrical.__all__`) | no | no | MAKE_INTERNAL | _ |
| 19 | `TagReuseError` | exception | `core/exceptions.py:40` | leaked-public (also re-exported in `electrical.__all__`) | no | no | MAKE_INTERNAL | _ |
| 20 | `TerminalReuseError` | exception | `core/exceptions.py:54` | leaked-public (also re-exported in `electrical.__all__`) | no | no | MAKE_INTERNAL | _ |
| 21 | `WireLabelMismatchError` | exception | `core/exceptions.py:68` | leaked-public (also re-exported in `electrical.__all__`) | no | no | MAKE_INTERNAL | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__` (or "leaked-public"); add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage.
- **MAKE_INTERNAL** — leaked-public with no usage. Per CLAUDE.md, `core/` is internal-by-convention.
- **REMOVE** — dead module / dead symbol.

## Summary

- Total symbols inspected: 21
- KEEP: 0
- PROMOTE: 0
- DEMOTE_CANDIDATE: 0
- MAKE_INTERNAL: 21 (all — `core/` is internal-by-convention per CLAUDE.md)
- REMOVE: 0

> Notes for review:
> 1. **All 21 names are flagged MAKE_INTERNAL.** This does NOT mean rename to `_foo` — that would break domain-package imports throughout the codebase. The recommendation is interpretive: A1 should keep these importable via `schematika.core.<module>` (e.g. `from schematika.core.geometry import Vector`) but NOT expose them at the `schematika.core` package facade. The cleanest implementation is to **add an empty `__all__ = []` to `core/__init__.py`** so static tools see the package as "no public names" while internal code keeps using fully-qualified module paths.
> 2. The exception classes are already exposed (correctly) via `electrical.__all__` and `pcb.__all__`. The `core/__init__.py` exposure is redundant.
> 3. Consider whether the geometric primitives (`Vector`, `Point`, `Element`, `Symbol`, `Port`) should be promoted to a stable public API — users writing custom symbol factories would need them. Currently they're imported from deep paths (`schematika.core.geometry`) inside the codebase. This is a decision for the user.
