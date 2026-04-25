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

- `just check` — fast incremental gates: `ruff format --check`, `ruff check`, `ty check`
- `just gates` — every pre-commit hook (whole-repo, strict): ruff, ty, vulture, import-linter, fp_purity_gate, api_style_gate (`--strict`), codesight (advisory)
- `just test` — pytest (use `uv sync --all-extras` so pcb tests collect)
- `just cov` — pytest with term-missing coverage
- `just stats` — `scripts/stats.py` (LoC, tests, coverage, ty count, ruff count)
- `just mutate [module]` — mutmut on one path; **Linux-only**, slow, off-machine
- `just dead-code` — vulture at 60% confidence (not a hook)
- `just docs` — pdoc to `docs/api/`
- `just docs-test` — pytest-examples on `docs/` and `README.md`
- `just context` — repomix dump
- `just context-wiki` — codesight wiki
- `just purity` / `just api-style` — standalone gate invocation (also covered by `just gates`)
- `just ci` — `gates + test`. THE canonical "everything green?" command.

## Notes

### `just ci` is the canonical gate

`just ci` runs every quality tool (via `pre-commit run --all-files`) plus the full pytest suite. It is the answer to "did I break anything?" Local-only by design — no GitHub Actions exist, the `justfile` IS the CI definition. mutmut is excluded because it's Linux-only and slow; run `just mutate` periodically on a dedicated Linux box.

### `deal` / zero-deps tradeoff

`deal` is in `[dependency-groups].dev` only — end users never install it. No `schematika._purity` shim exists. Decision deferred: if someone wants `@deal.pure` runtime assertions in end-user code, write `src/schematika/_purity.py` with `pure = deal.pure if HAVE_DEAL else lambda f: f` so decorated `core/` functions still run without deal installed. Until then, `fp_purity_gate.py` accepts either `@pure` or `@deal.pure` names — it's pure AST, no import.

### codesight on a pure-Python library

codesight 1.13.1 detects "project type: python, raw-http, no ORM". Output: 0 routes, 0 models, 0 components, 154 library files, 1 env var (`PYTEST_UPDATE_SNAPSHOTS`). It's route/ORM/component oriented, so the wiki (`.codesight/wiki/{index,overview,libraries}.md`) is thinner than on a web app — but `libraries.md` is a reasonable import-graph cheat sheet and the hot-files list is accurate. Keep the hook; treat output as "directory map" not "architecture doc".

