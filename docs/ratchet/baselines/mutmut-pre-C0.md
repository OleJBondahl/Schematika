# Mutmut baseline — pre-C0 (2026-04-25)

Captured from a mutmut run the user kicked off **before** any C-series wave was executed.
Re-run after Wave C5 (final review) and compare kill-rate / survivor count.

## Run state

- Branch base: `branch1`, prior to any C-series wave commit.
- Config: `pyproject.toml [tool.mutmut]` — `paths_to_mutate = ["src/schematika/"]`,
  `runner = "python -m pytest -x -q --no-cov"`, `tests_dir = ["tests/"]`.

## Raw numbers

```
14779/14779  🎉 11686  🫥 775  ⏰ 42  🤔 0  🙁 2276  🔇 0  🧙 0
```

mutmut 3 status legend:

| Icon | Meaning | Count |
|------|---------|------:|
| 🎉 | killed (a test caught the mutation) | **11,686** |
| 🫥 | no_tests (no test exercises the mutated line) | 775 |
| ⏰ | timeout (mutation hung past `timeout = 30`) | 42 |
| 🤔 | suspicious (test-failure pattern unclear) | 0 |
| 🙁 | **survived** (mutation passed the suite) | **2,276** |
| 🔇 | skipped (mutmut declined to mutate) | 0 |
| 🧙 | untested (not yet run) | 0 |
| **Total** | | **14,779** |

## Kill rates

- **Strict** (killed / executed-with-tests):
  executed-with-tests = 14,779 − 775 − 0 = 14,004 → **11,686 / 14,004 = 83.45%**
- **Inclusive** (killed / total mutants):
  **11,686 / 14,779 = 79.07%**
- **Survivor share** (survived / executed-with-tests):
  2,276 / 14,004 = **16.25%** ← this is the population the C-series should shrink.

## Where the survivors likely concentrate

By inspection, the 2,276 survivors will cluster in the high-complexity functions
that COMPLEXITY_PLAN.md targets: `translate`, `_render_page`, `_render_element`,
the `_phaseN_*` build-pipeline functions, and the SVG path parsers
(`_translate_path_d`, `_rotate_path_d`). Branch-heavy code with sparse
characterisation coverage is exactly the surface mutmut surfaces.

## Expected post-C5 deltas

The plan should move the numbers in three directions:

1. **Killed count rises, survived count falls.** Each wave adds characterisation
   tests (`pytest-subtests` table tests, hypothesis properties, `pytest.warns` for
   fallbacks) before refactoring, so previously-untested branches gain coverage.
2. **`no_tests` (775) shrinks.** Extractions to `core/*.py` come with unit tests
   (the plan's 90%-core-coverage gate enforces this), so newly-extracted lines
   start their life with mutants that are reachable.
3. **Total mutant count may drop.** LoC reduction (a stated plan goal) reduces
   the mutation surface. A lower total with similar absolute survivors is *not*
   an improvement — only the kill-rate / survivor-share comparison is.

## Re-run after C5

```bash
uv sync --all-extras
uv run mutmut run            # full re-run
uv run mutmut results        # summary
```

Then write `docs/ratchet/baselines/mutmut-post-C5.md` with the same table and
delta against this file.
