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
| mutmut (kill rate) | 0 | **66 % on 403 processed** (249 killed + 18 timeout, 126 survived); 148 unprocessed in transform.py | [mutmut_results.txt](mutmut_results.txt), [mutmut_survivors.txt](mutmut_survivors.txt) |

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

**Scope:** partial. Aborted at 403/551 mutants processed (73%). The 148 unprocessed mutants are all in `src/schematika/core/transform.py` (mutants 340-552, covering `_rotate_path_d` — no existing test exercises SVG path-d rotation deeply enough to provide a mutmut sample).

**Kill rate on the processed subset (403 mutants across `pcb/builder.py` + `core/transform.py`):**

| Outcome | Count | % |
|---|---:|---:|
| Killed | 249 | **62 %** |
| Timed out (effectively killed) | 18 | 4 % |
| Survived | 136 (126 after dedup in `mutmut results`) | 34 % |
| Suspicious | 0 | 0 % |

Counted as kills (killed + timeout): **66 %**. The `mutmut results` output lists 126 survivors — 10 fewer than the live run because some mutant IDs map to identical source mutations and collapse on final tally.

**Surviving-mutant distribution** (from `mutmut_results.txt`):

| File | Survived |
|---|---:|
| `src/schematika/pcb/builder.py` | 113 |
| `src/schematika/core/transform.py` | 13 |

Plus 213 untested/skipped in `transform.py` (mutants 340-552, `_rotate_path_d`).

**Survivor themes** (from `mutmut_survivors.txt`, all 126 extracted):

| Theme | Count | Example | Test strategy |
|---|---:|---|---|
| Loop-semantic swap (`continue`↔`break`) | 11 | `classify_nets`: `continue → break` | Fixture with orphan pin (`n<=1`) followed by real chain |
| Frozen dataclass flip | 4 | `_Column`, `_ConnectorTerminator`, `_NetEndpointTerminator`, `_PlacedSymbol` | `pytest.raises(FrozenInstanceError)` smoke |
| Layout constants | 5 | `A4_LANDSCAPE: (297,210) → (298,210)`; `DEFAULT_SYMBOL_SLOT_HEIGHT: 40.0 → 41.0` | Pin exact values in `test_pcb_constants.py` |
| Vector rotation math | 3 | `v.dx * sin_a → v.dx / sin_a` | Rotate at 30/45/90/180/270° with `pytest.approx` |
| Port/Point coord tweaks | many | `Port("1", Point(0,0), Vector(0,-1)) → Point(1,0)` | Assert `.position` + `.direction` on factory outputs |
| Type-alias nullification | 2 | `_Terminator = _C... \| _N... → _Terminator = None` | Runtime-innocuous; low priority |
| Variable `= None` | many | `smap = None`, `placed = None` | Covered transitively by realistic fixtures |
| String XX markers | a few | `"POWER" → "XXPOWERXX"` | Assert exact string values |

**How to re-run:** `bash scripts/run_mutmut.sh`. Mutmut state persists in `.mutmut-cache/`; delete it to start over. On Windows mutmut can wedge after ~400 mutants — resume with a fresh cache if needed.

**Re-extract survivors:** `bash scripts/extract_survivors.sh` (handles both comma-separated IDs and `N-M` range syntax).
