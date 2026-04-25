# API curation — catalog

**Source:** `src/schematika/catalog/__init__.py`, `catalog/cables.py`, `catalog/device.py`, `catalog/registry.py`, `catalog/errors.py`.
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - `catalog/__init__.py` has **NO `__all__`**. Every name imported there (`CatalogDevice`, `ElectricalSpec`, `InstrumentSpec`, `ProcessSpec`, `CableRegistry`, `CableSpec`, `DeviceCatalog`) is leaked-public.
> - `catalog/cables.py` has its own `__all__ = ["CableRegistry", "CableSpec"]`.
> - Consumer (`auxillary_cabinet_v3/src/pid.py:8`) imports `CatalogDevice, DeviceCatalog, InstrumentSpec, ProcessSpec` from `schematika.catalog`. These should be PROMOTEd if A1 introduces an explicit `__all__` in `catalog/__init__.py`.
> - `CatalogError` (the base exception) is defined in `catalog/errors.py` but is not re-exported from the package facade. It would be MAKE_INTERNAL today by the mechanical rule, but error-base classes are typically part of the public contract — flagged for user judgment.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `CatalogDevice` | dataclass | `catalog/device.py:53` | leaked-public | yes (`pid.py:8`) | no | PROMOTE | _ |
| 2 | `ElectricalSpec` | dataclass | `catalog/device.py:43` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 3 | `InstrumentSpec` | dataclass | `catalog/device.py:14` | leaked-public | yes (`pid.py:8`) | no | PROMOTE | _ |
| 4 | `ProcessSpec` | dataclass | `catalog/device.py:33` | leaked-public | yes (`pid.py:8`) | no | PROMOTE | _ |
| 5 | `CableRegistry` | class | `catalog/cables.py:47` | leaked-public (in `cables.py:__all__` but `catalog/__init__.py` has no `__all__`) | no | no | MAKE_INTERNAL | _ |
| 6 | `CableSpec` | dataclass | `catalog/cables.py:21` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 7 | `DeviceCatalog` | class | `catalog/registry.py:19` | leaked-public | yes (`pid.py:8`) | no | PROMOTE | _ |
| 8 | `CatalogError` | exception | `catalog/errors.py:4` | not exposed (NOT re-imported in `catalog/__init__.py`) | no | no | MAKE_INTERNAL — but flagged: error base classes typically belong in the public surface | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__` (or "leaked-public"); add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage. User decides if aspirational/forward-API or genuinely unused-and-internal.
- **MAKE_INTERNAL** — leaked-public with no usage. Rename `_foo` or move to private module.
- **REMOVE** — dead module / dead symbol.

## Summary

- Total symbols inspected: 8
- KEEP: 0
- PROMOTE: 4 (`CatalogDevice`, `InstrumentSpec`, `ProcessSpec`, `DeviceCatalog`)
- DEMOTE_CANDIDATE: 0
- MAKE_INTERNAL: 4 (`ElectricalSpec`, `CableRegistry`, `CableSpec`, `CatalogError`)
- REMOVE: 0

> Notes for review:
> 1. **`catalog/__init__.py` has no `__all__`.** A1 should add one. The four PROMOTE entries indicate which names belong in it for sure.
> 2. `ElectricalSpec` is leaked-public but unused; consumer's `pid.py` uses `ProcessSpec` and `InstrumentSpec` but not `ElectricalSpec` — possibly aspirational.
> 3. `CableRegistry` and `CableSpec` are leaked-public from `catalog/cables.py`. They might be aspirational shared-cable-catalog API; user decides.
> 4. `CatalogError` is the base exception. It is currently NOT re-exported from `catalog/__init__.py`. If users are expected to `except CatalogError`, A1/A2 should add it to the package facade.
