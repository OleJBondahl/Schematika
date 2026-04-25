# API curation — pcb

**Source:** `src/schematika/pcb/__init__.py`, `pcb/builder.py`, `pcb/errors.py`, `pcb/model.py`.
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - Consumer project (`auxillary_cabinet_v3`) currently does NOT import from `schematika.pcb`. The only external "usage" is in this repo's own design spec at `docs/superpowers/specs/2026-04-24-schematika-pcb-design.md:148` (a forward-looking design doc, not real consumer code).
> - The package was recently introduced (per `docs/baselines/2026-04-24-post-wave6/` and the SKILL note in CLAUDE.md). It is intentionally exposed for SKiDL bridge users.
> - `pcb/__init__.py` has an explicit `__all__`. No leaked-public symbols detected.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `A3_LANDSCAPE` | constant | `pcb/builder.py:33` | yes | no | no | DEMOTE_CANDIDATE (aspirational page-size constant) | _ |
| 2 | `A4_LANDSCAPE` | constant | `pcb/builder.py:32` | yes | no | no | DEMOTE_CANDIDATE (aspirational page-size constant) | _ |
| 3 | `build` | function | `pcb/builder.py:716` | yes | no | yes (`docs/superpowers/specs/2026-04-24-schematika-pcb-design.md:148`) | KEEP (primary entry point of the new module) | _ |
| 4 | `DuplicateMappingError` | exception | `pcb/errors.py:97` | yes | no | no | DEMOTE_CANDIDATE (error contract; users may catch even if grep doesn't find it) | _ |
| 5 | `HeightOverflowError` | exception | `pcb/errors.py:148` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 6 | `IncompleteSliceError` | exception | `pcb/errors.py:71` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 7 | `MultiPinSliceError` | exception | `pcb/errors.py:53` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 8 | `OrphanSliceError` | exception | `pcb/errors.py:131` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 9 | `PCBBuildError` | exception (base) | `pcb/errors.py:4` | yes | no | no | DEMOTE_CANDIDATE (base class — likely the documented catch point) | _ |
| 10 | `PinNotOnTemplateError` | exception | `pcb/errors.py:13` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 11 | `PortNotOnSymbolError` | exception | `pcb/errors.py:33` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 12 | `UnmappedPartError` | exception | `pcb/errors.py:114` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 13 | `ConnectorMap` | dataclass | `pcb/model.py:47` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 14 | `PCBBuildResult` | dataclass | `pcb/model.py:169` | yes | no | no | DEMOTE_CANDIDATE (returned by `build()` — user constructs / consumes; keep aspirationally) | _ |
| 15 | `PowerNetMap` | dataclass | `pcb/model.py:56` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 16 | `SymbolMap` | dataclass | `pcb/model.py:39` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 17 | `SymbolMapping` | dataclass | `pcb/model.py:64` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 18 | `SymbolSlice` | dataclass | `pcb/model.py:31` | yes | no | no | DEMOTE_CANDIDATE | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__`; add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage. User decides if aspirational/forward-API or genuinely unused-and-internal.
- **MAKE_INTERNAL** — leaked-public with no usage.
- **REMOVE** — dead module / dead symbol.

## Summary

- Total symbols inspected: 18
- KEEP: 1 (`build`)
- PROMOTE: 0
- DEMOTE_CANDIDATE: 17
- MAKE_INTERNAL: 0
- REMOVE: 0

> Notes for review: the entire `pcb` module is aspirational — no consumer uses it yet. The exception hierarchy and the data classes are reasonably exposed because users of the SKiDL bridge will inevitably need to construct mappings and catch errors. Bulk DEMOTE here likely overstates "unused-ness". Suggest the user override most of these to KEEP after review.
