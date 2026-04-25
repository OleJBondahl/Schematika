# Wave C0-pre baseline — ratchet collectors + test plumbing

Branch base: `branch1` @ `5f584ea` (after the COMPLEXITY_PLAN.md commit).

## State at start

`uv sync --all-extras` then `just metrics` → `docs/ratchet/snapshots/2026-04-25T220531.toml`.

```
[complexity.distribution]
above_complexity_10 = 19
above_args_8        = 9    (was 10 in earlier snapshot — one PLR0913 site shed during Wave A)
above_branches_12   = 9
above_statements_50 = 7
above_returns_6     = 2

[complexity.peaks]
max_complexity   = 22  in _phase4_render_graphics
max_args         = 16  in add_terminal
max_branches     = 22  in _phase2_register_connections
max_statements   = 69  in _phase2_register_connections
max_returns      = 10  in translate

[suppressions]
noqa             = 70
ty_ignore        = 105

[codebase]
src_loc          = 33,271
src_complexity_scc = 2,231
python_files_src = 110

[tests]
passed           = 1,876   (matches baseline.toml floor)
coverage_percent = 89
core_coverage    = 93      (computed from per-module rollup)
```

`pyproject.toml` thresholds (frozen high-water marks):
- `max-complexity = 22`
- `max-args = 16`
- `max-branches = 22`
- `max-statements = 70`
- `max-returns = 10`

## Wave scope

**No code changes; infrastructure-only commit.** Per plan: "Run inline; no implementer subagent."

1. Extend `scripts/ratchet_check.py`:
   - `_COMPLEXITY_RULES` constant (5-tuple of rule, config_key, threshold, peak_key).
   - `collect_complexity_peaks()` — runs ruff at lowered thresholds, returns dict[str, int] with the 5 peaks.
   - `collect_pytest_and_cov()` extended to return `(passing, repo_cov, core_cov)` 3-tuple. core_cov computed by summing Stmts/Miss across `src/schematika/core/*.py` lines in the per-module report (no second pytest run).
   - `gather()` emits 5 new `le`-kind Metrics (one per peak) + 1 new `ge`-kind Metric (`min_core_coverage_percent`).
   - `HEADER` template + `cmd_update`'s `required` list extended.
2. Extend `docs/ratchet/baseline.toml`:
   - `[complexity]` section: peaks pinned at observed (22 / 16 / 22 / 69 / 10).
   - `[pytest] min_core_coverage_percent = 93` (current measured floor; plan target 90).
3. `pyproject.toml`:
   - `[dependency-groups] dev` += 4 plugins (`pytest-subtests>=0.13`, `inline-snapshot>=0.20`, `pytest-timeout>=2.3`, `dirty-equals>=0.9`).
   - `[tool.pytest.ini_options]`: `timeout = 30` + `addopts += --inline-snapshot=disable`.

## Done condition

- `uv run python scripts/ratchet_check.py` → exit 0, prints 12-row pass table.
- `uv run python scripts/ratchet_check.py --fast` → exit 0, prints 9-row pass table (skips pytest+cov).
- `uv run pytest --collect-only -q` → 1876 tests collected (no plugin breaks discovery).
- `uv run pytest -q --continue-on-collection-errors` → 1876 passed (no timeout triggered on any test).
- All 12 ratchet metrics newly green; baseline.toml has the new sections; pyproject has the new plugins.
