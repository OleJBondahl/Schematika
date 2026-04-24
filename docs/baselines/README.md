# Baselines

Pre-refactor metric snapshots. Each subdirectory (named `YYYY-MM-DD`) captures
the output of every quality-gate tool at a named point in time so future waves
of a refactor have a concrete diff target.

## Regenerate

Most metrics are a single command away:

```bash
just stats              # live LoC, test count, coverage, ty diagnostic count
just mutate <file>      # mutation testing on one module
```

For a full snapshot matching what lives under `2026-04-24/`, run:

```bash
bash claude-tools/run_baselines.sh       # all metric tools -> docs/baselines/<date>/
bash claude-tools/run_pytest_baseline.sh # pytest + coverage HTML
bash claude-tools/run_mutmut.sh          # mutation testing (slow, 10-30 min)
```

The shell scripts capture stdout+stderr and the exit code of each tool; a tool
failing (ruff, ty, import-linter, vulture) is *data*, not a blocker.

## Retention

- Keep one baseline per major refactor milestone (pre-refactor, post-refactor).
- Delete or archive intermediate snapshots once their refactor PR is merged.
- `coverage_html/` directories are large — safe to delete; pytest.txt keeps the
  line-level coverage numbers.

## Interpretation guide

| Question | File |
|---|---|
| Coverage regressed? | `pytest.txt` (TOTAL line, bottom) |
| Ruff debt grew? | `ruff_stats.txt`, detail in `ruff_full.txt` |
| New type-checker diagnostics? | `ty.txt` |
| Dead code appeared? | `vulture.txt` (min-confidence 60) |
| Docstring coverage dropped? | `interrogate.txt` |
| API-style regressions? | `api_style_gate.txt` |
| Purity gate regressions? | `purity_gate.txt` |
| Docstring/signature drift? | `darglint.txt` |
| Import-layering breaks? | `import_linter.txt` |
| Cyclomatic complexity grew? | `complexity.txt` |
| LoC per file changed? | `loc_by_file.txt` / `loc_summary.txt` |
| Tests stopped catching mutations? | `mutmut_results.txt` + `mutmut_survivors.txt` |

`index.md` inside each snapshot condenses everything to a single table.
