# API curation — block

**Source:** `src/schematika/block/__init__.py`, `block/constants.py`, `block/model.py`, `block/diagram.py`, `block/validation.py`.
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> **DEAD-MODULE FLAG (per project memory):**
> Per `~/.claude/projects/.../MEMORY.md` ("Block module is dead code"): `schematika.block` is a trial, not in production. The default recommendation for every row in this matrix is **REMOVE**. The user may override individual rows to "KEEP" / "DEMOTE_CANDIDATE" if they want to revive specific names rather than delete the package wholesale.
>
> Counter-evidence: `auxillary_cabinet_v3/src/block_diagram.py:7` does still import `from schematika.block import AC_POWER, DASHED, ETHERNET, SIGNAL_CABLE, BlockDiagram`. So the package is *not* fully dead in the consumer; either MEMORY.md is stale or the consumer's `block_diagram.py` itself is dead. **Phase 4 must resolve this contradiction before Phase 5 deletes anything.**

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `AC_POWER` | constant (CableStyle) | `block/model.py:53` | yes | yes (`block_diagram.py:7`) | no | REMOVE (per MEMORY.md; counter-evidence in consumer — please confirm) | _ |
| 2 | `BLOCK_DEFAULT_HEIGHT` | constant | `block/constants.py:38` | yes | no | no | REMOVE | _ |
| 3 | `BLOCK_GAP` | constant | `block/constants.py:36` | yes | no | no | REMOVE | _ |
| 4 | `BLOCK_LABEL_SIZE` | constant | `block/constants.py:47` | yes | no | no | REMOVE | _ |
| 5 | `BLOCK_MIN_WIDTH` | constant | `block/constants.py:39` | yes | no | no | REMOVE | _ |
| 6 | `BLOCK_STROKE_WIDTH` | constant | `block/constants.py:40` | yes | no | no | REMOVE | _ |
| 7 | `CABLE_BUNDLE_SPACING` | constant | `block/constants.py:43` | yes | no | no | REMOVE | _ |
| 8 | `CABLE_COLOR_AC_POWER` | constant | `block/constants.py:62` | yes | no | no | REMOVE | _ |
| 9 | `CABLE_COLOR_DC_CONTROL` | constant | `block/constants.py:63` | yes | no | no | REMOVE | _ |
| 10 | `CABLE_COLOR_ETHERNET` | constant | `block/constants.py:65` | yes | no | no | REMOVE | _ |
| 11 | `CABLE_COLOR_SIGNAL` | constant | `block/constants.py:64` | yes | no | no | REMOVE | _ |
| 12 | `CABLE_ETHERNET_DASH` | constant | `block/constants.py:59` | yes | no | no | REMOVE | _ |
| 13 | `CABLE_LABEL_OFFSET` | constant | `block/constants.py:44` | yes | no | no | REMOVE | _ |
| 14 | `CABLE_TYPE_STYLES` | dict constant | `block/model.py:58` | yes | no | no | REMOVE | _ |
| 15 | `CABLE_WEIGHT_CONTROL` | constant | `block/constants.py:54` | yes | no | no | REMOVE | _ |
| 16 | `CABLE_WEIGHT_ETHERNET` | constant | `block/constants.py:56` | yes | no | no | REMOVE | _ |
| 17 | `CABLE_WEIGHT_POWER` | constant | `block/constants.py:53` | yes | no | no | REMOVE | _ |
| 18 | `CABLE_WEIGHT_SIGNAL` | constant | `block/constants.py:55` | yes | no | no | REMOVE | _ |
| 19 | `CONTAINER_PADDING` | constant | `block/constants.py:37` | yes | no | no | REMOVE | _ |
| 20 | `DASHED` | constant (BlockStyle) | `block/model.py:83` | yes | yes (`block_diagram.py:7`) | no | REMOVE (counter-evidence — consumer uses) | _ |
| 21 | `DC_CONTROL` | constant (CableStyle) | `block/model.py:54` | yes | no | no | REMOVE | _ |
| 22 | `ETHERNET` | constant (CableStyle) | `block/model.py:56` | yes | yes (`block_diagram.py:7`) | no | REMOVE (counter-evidence — consumer uses) | _ |
| 23 | `GRID_SIZE` (re-export) | constant | `core/constants.py` | yes | no | no | REMOVE | _ |
| 24 | `LEGEND_ENTRY_HEIGHT` | constant | `block/constants.py:69` | yes | no | no | REMOVE | _ |
| 25 | `LEGEND_LINE_SAMPLE_LENGTH` | constant | `block/constants.py:68` | yes | no | no | REMOVE | _ |
| 26 | `NOTE_TEXT_SIZE` | constant | `block/constants.py:50` | yes | no | no | REMOVE | _ |
| 27 | `SIGNAL_CABLE` | constant (CableStyle) | `block/model.py:55` | yes | yes (`block_diagram.py:7`) | no | REMOVE (counter-evidence — consumer uses) | _ |
| 28 | `SOLID` | constant (BlockStyle) | `block/model.py:82` | yes | no | no | REMOVE | _ |
| 29 | `TAG_BOX_PADDING` | constant | `block/constants.py:49` | yes | no | no | REMOVE | _ |
| 30 | `TAG_LABEL_SIZE` | constant | `block/constants.py:48` | yes | no | no | REMOVE | _ |
| 31 | `Block` | class | `block/model.py:128` | yes | no | no | REMOVE | _ |
| 32 | `BlockDiagram` | class | `block/diagram.py:48` | yes | yes (`block_diagram.py:7`) | no | REMOVE (counter-evidence — consumer uses) | _ |
| 33 | `BlockStyle` | dataclass | `block/model.py:73` | yes | no | no | REMOVE | _ |
| 34 | `Cable` | dataclass | `block/model.py:110` | yes | no | no | REMOVE | _ |
| 35 | `CableStyle` | dataclass | `block/model.py:45` | yes | no | no | REMOVE | _ |
| 36 | `MirroredBlock` | dataclass | `block/model.py:238` | yes | no | no | REMOVE | _ |
| 37 | `Placement` | dataclass | `block/model.py:92` | yes | no | no | REMOVE | _ |
| 38 | `ValidationResult` | dataclass | `core/validation.py:24` (re-imported) | yes | no | no | REMOVE (re-exports core type into block — extraneous regardless) | _ |
| 39 | `validate_block_diagram` | function | `block/validation.py:99` | yes | no | no | REMOVE | _ |

## Recommendation legend

- **REMOVE** — dead module / dead symbol. Per project memory the entire `block` package is a trial.
- All other categories defined in other matrices.

## Summary

- Total symbols inspected: 39
- REMOVE: 39 (per MEMORY.md "block module is dead code")
- KEEP / PROMOTE / DEMOTE_CANDIDATE / MAKE_INTERNAL: 0

> Notes for review:
> 1. **Critical:** consumer `block_diagram.py` actively imports 5 names (`AC_POWER`, `BlockDiagram`, `DASHED`, `ETHERNET`, `SIGNAL_CABLE`). MEMORY.md says block is dead, but the consumer suggests otherwise. Phase 4 needs to:
>    (a) confirm `block_diagram.py` is itself dead and can be deleted from the consumer, **or**
>    (b) update MEMORY.md to remove the "dead code" label for `schematika.block`.
> 2. If (b), the recommendations should be revised: `AC_POWER`, `BlockDiagram`, `DASHED`, `ETHERNET`, `SIGNAL_CABLE` would all become **KEEP**, and the rest would mostly be **DEMOTE_CANDIDATE**.
> 3. If (a), Phase 5 deletes the entire `src/schematika/block/` directory and `auxillary_cabinet_v3/src/block_diagram.py`.
