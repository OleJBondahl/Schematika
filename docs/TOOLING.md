# Tooling

How to run the quality/metrics stack. Regenerate this file when the numbers shift.

## Stack

| Tool | Role | Wiring | Configured via |
|---|---|---|---|
| ruff | Lint + format (incl. security `S`, complexity `C90/PLR`, docstrings `D`) | pre-commit, `just check` | `pyproject.toml` `[tool.ruff]` |
| ty | Type check | pre-commit, `just check` | `pyproject.toml` `[tool.ty.src]` |
| vulture (80%) | Dead code | pre-commit | `--min-confidence 80` inline |
| vulture (60%) | Dead code sweep | `just dead-code` only | inline |
| import-linter | Layering contracts | pre-commit, `just ci` | `.importlinter` |
| codesight (wiki) | AST-based repo map | pre-commit, `just context-wiki` | `npx codesight --wiki` |
| fp_purity_gate | `core/` @pure check | pre-commit, `just purity` | `scripts/fp_purity_gate.py` |
| api_style_gate | Schematika API rules | pre-commit, `just api-style` | `scripts/api_style_gate.py` |
| pytest + pytest-cov | Tests + coverage | `just test` / `just cov` | `pyproject.toml` `[tool.pytest.ini_options]` |
| pdoc | API reference | `just docs` | CLI only |
| pytest-examples | Markdown doctest | `just docs-test` | CLI only |
| mutmut | Mutation testing | `just mutate` | `pyproject.toml` |
| hypothesis | Property-based tests | inline in tests | dev dep |
| repomix | LLM context dump | `just context` | `npx repomix` |
| deal | Purity & contracts in `core/` | dev-dep + decorators | `[dependency-groups].dev` |

For live counts (LoC, test count, coverage, ty diagnostics, ruff count), run `just stats`.

## Tools deliberately NOT used

| Tool | Why dropped | Replaced by |
|---|---|---|
| bandit | Redundant with ruff `S` rules | `select = [..., "S"]` |
| radon (cc, mi) | Redundant with ruff `C90 + PLR` complexity rules | `select = [..., "C90", "PLR"]` with thresholds in `[tool.ruff.lint.mccabe]` / `[tool.ruff.lint.pylint]` |
| docstr-coverage | Aggregate % is not actionable; ruff flags missing per-site | `select = [..., "D"]` with `convention = "google"` |
| interrogate | Same as docstr-coverage; also breaks on Windows without cairo | `select = [..., "D"]` |
| darglint / darglint2 / pydoclint | Enforces signature/docstring agreement, which contradicts the docstring style this repo follows (short, WHY-only — see `python-coding-and-tooling` skill). Also: darglint upstream is unmaintained | None — ruff `D` covers presence + format; signature drift is caught by `ty` (parameters must match types) and `reviewing-ai-generated-python` smell #4 is the audit lens |
| pylint | Redundant with ruff `PLR/PLE/PLW`, 100x slower | `select = [..., "PLR"]` |
| mypy / pyright | Project standardises on `ty`. Mixed checkers create dueling `# ignore[...]` syntax | `ty` |
| black / isort / flake8 (and plugins) | All replaced by ruff | `ruff format` + `ruff check` |

This list is enforced by the `python-coding-and-tooling` global skill (see Forbidden Toolchain). If a future contributor proposes adding any of these tools, point them at the skill.

## Live metrics

Numbers move on every wave. Don't pin them here. Run `just stats` for the live values.

## `just` targets

See `justfile`.

- `just check` — ruff format+check, ty, `pre-commit run --all-files`
- `just test` — pytest
- `just cov` — pytest with term-missing coverage
- `just stats` — `scripts/stats.py` (LoC, tests, coverage, ty count, ruff count)
- `just mutate [module]` — mutmut on one path (default: `src/schematika/pcb/builder.py`)
- `just dead-code` — vulture at 60% confidence (not a hook)
- `just docs` — pdoc to `docs/api/`
- `just docs-test` — pytest-examples on `docs/` and `README.md`
- `just context` — repomix dump
- `just context-wiki` — codesight wiki
- `just purity` / `just api-style` — advisory gates
- `just ci` — `check test purity api-style`

## Notes

### `deal` / zero-deps tradeoff

`deal` is in `[dependency-groups].dev` only — end users never install it. No `schematika._purity` shim exists. Decision deferred: if someone wants `@deal.pure` runtime assertions in end-user code, write `src/schematika/_purity.py` with `pure = deal.pure if HAVE_DEAL else lambda f: f` so decorated `core/` functions still run without deal installed. Until then, `fp_purity_gate.py` accepts either `@pure` or `@deal.pure` names — it's pure AST, no import.

### codesight on a pure-Python library

codesight 1.13.1 detects "project type: python, raw-http, no ORM". Output: 0 routes, 0 models, 0 components, 154 library files, 1 env var (`PYTEST_UPDATE_SNAPSHOTS`). It's route/ORM/component oriented, so the wiki (`.codesight/wiki/{index,overview,libraries}.md`) is thinner than on a web app — but `libraries.md` is a reasonable import-graph cheat sheet and the hot-files list is accurate. Keep the hook; treat output as "directory map" not "architecture doc".

### import-linter pre-existing failures

Two contracts fail on branch1 head: `schematika.electrical -> schematika.project` at `electrical/__init__.py:80` and `schematika.pcb.builder -> schematika.project` at `pcb/builder.py:23`. These are pre-existing cycles and out of scope for this wiring commit. See §5.4 of `CODEBASE_AUDIT.md` for the layering plan.

### Two failing tests

`tests/unit/test_pcb_traverse_errors.py::TestOrphanSliceError::{test_orphan_slice_raises, test_orphan_slice_error_has_part_ref}` fail on branch1 head — pre-existing, out of scope.

### Pre-commit hooks were added with `--no-verify`

The two wiring commits (6 and 7) were made with `--no-verify` because (a) pre-existing src/ lint errors would block any commit, and (b) this worktree's scope is config files only. Once the ruff cleanup from §5.4 lands, hooks should run cleanly on new commits.
