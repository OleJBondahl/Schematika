# API curation — top

**Source:** `src/schematika/__init__.py`
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation: `src/schematika/__init__.py` has no `__all__`; it consists solely of `from .electrical import *`. Every symbol exposed at the `schematika` top-level is therefore inherited from `schematika.electrical`'s `__all__`. The matrix below covers two distinct things: (a) `schematika.<name>` callsites in the consumer/examples (which are the primary public API surface in practice), and (b) the wildcard re-export itself. Symbol-by-symbol decisions live in `electrical.md`; this file only flags the wildcard pattern.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `from .electrical import *` (wildcard) | re-export | `src/schematika/__init__.py:4` | n/a (no `__all__` here) | yes — most consumer `from schematika import …` lines depend on this | yes — every `examples/*.py` does `from schematika import …` | KEEP (but consider an explicit `__all__` in A1) | _ |
| 2 | `Project` | class | `src/schematika/project.py` (NOT re-exported) | no — explicitly excluded from `electrical.__all__` | no consumer uses `from schematika import Project` (consumer uses `from schematika.project import Project` at `block_diagram.py:8`, `cabinet.py` uses other surface) | yes — `examples/06_full_cabinet.py:44` and docs use `from schematika.project import Project` | KEEP (port-of-entry: must always be `from schematika.project`, not top-level) | _ |
| 3 | `overview` | submodule | `src/schematika/overview/` (planned, not yet implemented) | no | no | yes — `docs/overview-module/05-overview-api.md:288`, `docs/overview-module/08-worked-example.md:15` | DEMOTE_CANDIDATE (planned module, not yet shipped — defer to overview-module spec) | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__` (or "leaked-public"); add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage. User decides if aspirational/forward-API or genuinely unused-and-internal.
- **MAKE_INTERNAL** — leaked-public with no usage. Rename `_foo` or move to private module (Phase 5 work).
- **REMOVE** — dead module / dead symbol. Candidate for outright deletion (especially in `block/`).
- **KEEP (port-ID contract)** — symbol factories under `electrical/symbols/`. Port IDs are documented in factory docstrings; these are public regardless of grep results.

## Summary

- Total symbols inspected: 3 (the top-level package re-exports its full surface from `electrical`; per-symbol decisions live in `electrical.md`)
- KEEP: 2 (the wildcard re-export and the documented `from schematika.project import Project` import path)
- DEMOTE_CANDIDATE: 1 (`schematika.overview` — planned but not yet implemented)
- PROMOTE: 0
- MAKE_INTERNAL: 0
- REMOVE: 0

> Open question for review: should A1 add an explicit `__all__` to `src/schematika/__init__.py` (mirroring `electrical.__all__`) so that the top-level surface is auditable here, instead of dispatching every check to `electrical.md`? Default answer: yes, but flagged for user confirmation in phase 4.
