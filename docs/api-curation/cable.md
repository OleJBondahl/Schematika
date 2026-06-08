# API curation — cable

**Source:** `src/schematika/cable/__init__.py`, `cable/builder.py`, `cable/model.py`, `cable/renderer.py`.
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - `cable/__init__.py` has an explicit `__all__` listing 7 names. No leaked-public names detected.
> - No consumer (`auxillary_cabinet_v3`) imports from `schematika.cable` directly. (Cable rendering happens via `Project.cables` in this design — the `cable/` package's public API is consumed by `schematika/project.py`, not by end-users yet.)
> - Per the "external usage" rule (internal-cross-package imports do not count), the `cable` module currently has zero external usage. This means every row is DEMOTE_CANDIDATE per the mechanical rule, but several entries are clearly aspirational public API that the user will likely want to KEEP.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `CableConnection` | dataclass | `cable/model.py:38` | yes | no | no | DEMOTE_CANDIDATE (aspirational data class) | _ |
| 2 | `CableConnector` | dataclass | `cable/model.py:9` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 3 | `CableDef` | dataclass | `cable/model.py:23` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 4 | `CableDrawing` | dataclass | `cable/model.py:50` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 5 | `build_cable_drawings` | function | `cable/builder.py:231` | yes | no | no | DEMOTE_CANDIDATE (top-level builder; primary entry) | _ |
| 6 | `render_cable_svg` | function | `cable/renderer.py:53` | yes | no | no | DEMOTE_CANDIDATE | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__`; add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage. User decides if aspirational/forward-API or genuinely unused-and-internal.
- **MAKE_INTERNAL** — leaked-public with no usage.
- **REMOVE** — dead module / dead symbol.

## Summary

- Total symbols inspected: 7
- KEEP: 0
- PROMOTE: 0
- DEMOTE_CANDIDATE: 7
- MAKE_INTERNAL: 0
- REMOVE: 0

> Notes for review: every name in `cable.__all__` is "DEMOTE_CANDIDATE" by the mechanical rule, but the consumer reaches cable functionality through `Project.cables` (internal cross-package import, not counted). The user may want to either:
> 1. Override most rows to **KEEP** because the API is the documented entry point for direct cable-only use, even if the canonical workflow goes through `Project`; or
> 2. Override to **MAKE_INTERNAL** for the dataclasses (`CableConnection`, `CableConnector`, `CableDef`) that are constructed by the builder, leaving only the three builder/renderer functions public.
> Strong recommendation to revisit during phase 4.
