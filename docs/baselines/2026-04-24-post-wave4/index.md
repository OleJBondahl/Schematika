# Post-Wave-4 snapshot — 2026-04-24

Intermediate metric snapshot after Waves 1–4. Mutmut **not** re-run (kept as
pre-refactor baseline at `../2026-04-24/`, to be replayed once after Wave 6 as
the post-refactor snapshot).

All other metric tools re-captured via `bash scripts/run_baselines.sh
docs/baselines/2026-04-24-post-wave4` + `bash scripts/run_pytest_baseline.sh
docs/baselines/2026-04-24-post-wave4`.

## Delta table — pre-refactor (2026-04-24) → post-Wave-4

| Tool | Pre | Post | Δ | Note |
|---|---:|---:|---:|---|
| pytest | 1459 pass / 4 xfail | **1582 pass / 4 xfail** | +123 | Wave 3 safety-net tests |
| coverage | 84 % (1177 missed / 7323) | 84 % (1161 missed / 7325) | −16 missed | slightly better |
| scc LoC (Python) | 29 537 / 170 files | 30 636 / 174 files | +1 099 / +4 | new test files |
| scc complexity | 1 892 | 1 916 | +24 | ditto |
| ruff errors | 615 | **602** | −13 | no new src/ violations; tests/ untouched |
| ruff auto-fixable | 247 | — | — | not re-pulled; ruff stats shows top rules D212/PLR0913/D102 |
| ty diagnostics | 39 | 54 | **+15** | all in Wave-3 new test files; library code unchanged |
| interrogate | 80.3 % (647/806) | 80.1 % (646/806) | −0.2 pp | one internal helper deleted in Wave 4 |
| vulture (conf 60) | 163 | 162 | −1 | `add_to_project` removed |
| import-linter | **1 broken** | **0 broken** | ✓ | Wave 4 fixed `pcb → project` |
| fp-purity-gate | 54 missing | 54 missing | 0 | untouched; Wave 6 target |
| api-style-gate | 18 (log) / 12 (index.md) | **17** | −1 | `add_to_project` removed; keeping the 18-based count |
| darglint (lines) | 890 | 885 | −5 | |
| ruff C90 (complexity) | 1 | 1 | 0 | same offender |

**Net assessment:** stable. The only regression is +15 ty diagnostics, all from
Wave 3 test files using loose typing on deliberate internal-access tests
(`_other_pin`, etc.). No regressions in library code. One real win:
import-linter now passes cleanly.

## ty regression detail (post-Wave-4 only)

All 15 new diagnostics are in `tests/`, not `src/`:

| File | Count | Source |
|---|---:|---|
| `tests/unit/test_pcb_label_symbol.py` | 8 | `Argument is incorrect` (loose kwargs to internal factories) |
| `tests/unit/test_pcb_internal_invariants.py` | 6 | `_other_pin` arg types + `Argument is incorrect` |
| `tests/unit/test_pcb_model.py` | 1 | `Argument is incorrect` |

Wave 5 or Wave 6 can tighten these with explicit `# type: ignore[...]` or by
widening the internal signatures. Not blocking.

## What changed in the library

| Commit | Summary |
|---|---|
| `f7ed8d6` | Wave 4: moved `pcb.add_to_project` → `Project.add_pcb`; dropped pcb→project import |
| `def5436`..`bc66e95` | Wave 3: +123 tests, 0 source edits |
| `3c12ade` | Mutmut baseline finalized (403/551 processed, 66 % kill rate) |

## Why no mutmut re-run

The `2026-04-24/mutmut_results.txt` snapshot is the pre-refactor reference.
Re-running mutmut now would:
1. Reset the diff target mid-refactor (loses Wave-3→post-Wave-6 kill-rate Δ).
2. Cost 60–90 min of wall-clock; flaky on Windows (last run aborted at 403/551).
3. Duplicate the signal from pytest (+123 new targeted tests).

Schedule one more mutmut run after Wave 6 as the post-refactor snapshot.
