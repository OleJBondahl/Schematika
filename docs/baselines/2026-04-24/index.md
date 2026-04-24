# Pre-refactor baseline — 2026-04-24

Entry point for humans and future agents; every row links to the detailed
output file next to it. Captured on `branch1`.

## Headline metrics

| Tool | Exit | Headline | Detail |
|---|---:|---|---|
| pytest (cov) | 0 | **1459 passed, 4 xfail, 84% coverage** (7323 statements, 1177 missed) | [pytest.txt](pytest.txt), [coverage_html/](coverage_html/index.html) |
| scc (summary) | 0 | 170 Python files, 29 537 code lines, complexity 1 892 | [loc_summary.txt](loc_summary.txt) |
| scc (by file) | 0 | per-file LoC | [loc_by_file.txt](loc_by_file.txt) |
| ruff (stats) | 1 | **615 errors**, 247 auto-fixable; top rule `D103` missing public-function docstring | [ruff_stats.txt](ruff_stats.txt) |
| ruff (full) | 1 | full issue list (620 lines) | [ruff_full.txt](ruff_full.txt) |
| ruff C90 (complexity) | 1 | 1 `C901` complex-structure finding | [complexity.txt](complexity.txt) |
| ty | 1 | **39 diagnostics** | [ty.txt](ty.txt) |
| interrogate | 0 | **80.3% docstring coverage** (647/806 objects) | [interrogate.txt](interrogate.txt) |
| vulture (conf 60) | 3 | **163 findings** (methods/attrs/variables flagged as unused) | [vulture.txt](vulture.txt) |
| import-linter | 1 | **1 contract broken**: `pcb` -> `project` (`schematika.pcb.builder:23`) | [import_linter.txt](import_linter.txt) |
| fp-purity-gate | 0 | **54 functions in core/ missing @pure** decorator (advisory) | [purity_gate.txt](purity_gate.txt) |
| api-style-gate | 0 | **12 findings**: missing `/`, x/y scalars, build returning None | [api_style_gate.txt](api_style_gate.txt) |
| darglint | 0 | **835 DAR violations** in src/schematika/ | [darglint.txt](darglint.txt) |
| mutmut (kill rate) | (see file) | see below | [mutmut_results.txt](mutmut_results.txt), [mutmut_survivors.txt](mutmut_survivors.txt) |

Exit codes: 0 = passed, 1 = issues found, 3 = vulture "unused code" exit.
Non-zero on ruff / ty / import-linter / vulture is expected — these are the
pre-existing debt we pre-commit to a baseline so refactor waves can diff
against it.

## Methodology

- pytest run with `--cov=src/schematika --cov-report=term-missing --cov-report=html:docs/baselines/2026-04-24/coverage_html`. Extras `pcb` + `mcp` installed via `uv sync --extra pcb --extra mcp`.
- Each tool output includes a trailing `EXIT=<n>` line so future diffs see both content **and** exit-code regressions.
- `ruff_full.txt` was capped at 2000 lines at capture; the whole file fits so no truncation actually applied. No data loss.
- `darglint.txt` was capped at 4000 lines; the full output is 890 lines so no truncation applied.
- Mutmut was run with a narrowed test scope (`tests/unit/test_transform.py` + `tests/unit/test_pcb_*.py`, 194 tests) to keep the wall-clock time under 30 min on Windows. Full-suite mutmut runs should produce the same or higher kill rate.

## Mutmut kill rate (2026-04-24)

*(filled in by the task-3 commit — see `mutmut_results.txt`)*
