# Wave C0a baseline — translate + _render_page → match/case

Branch base: `branch1` @ `374152b` (post-C0-pre).
Wave branch: `complexity/C0a` in worktree `.worktrees/complexity/C0a`.

## State at start

`docs/ratchet/baseline.toml` `[complexity]`:
```
max_complexity   = 22
max_args         = 16
max_branches     = 22
max_statements   = 69
max_returns      = 10   <- this wave drives down
```

`pyproject.toml` `[tool.ruff.lint.pylint] max-returns = 10`.

PLR0911 offenders at default threshold 6:
- `src/schematika/core/transform.py:33` `translate` — 10 returns (tier-3, public dispatch, has `warnings.warn` fallback)
- `src/schematika/rendering/typst/compiler.py:262` `_render_page` — 8 returns (tier-3, `_`-prefixed internal dispatch)

`pytest`: 1876 passed, repo coverage 89%, core coverage 93%.

## Wave scope

Two function rewrites, single worktree branch.

### Function 1: `translate` (public dispatch, preserve fallback)

Convert the 9-arm isinstance chain to a single `match` expression. **Preserve the `warnings.warn(...)` semantics** — it's a public API used externally; replacing it with `assert_never` would change behavior on unknown types from "warn-and-return-unchanged" to "crash". Use `case _:` for the fallback.

The function has PEP 695 generic syntax `def translate[T: Element | Point | Port | Vector](obj: T, dx: float, dy: float) -> T:` and uses `cast("T", ...)` per branch because ty doesn't perfectly narrow generic returns. The match version preserves both.

Target metrics: PLR0911 10 → 1 (single match), C901 unchanged-or-better.

### Function 2: `_render_page` (internal dispatch, use assert_never)

Internal `_`-prefixed method dispatching on `page.page_type` (closed string enum). No existing fallback — use `from typing import assert_never` in the `case _:` arm. Stricter is cheap here: ty catches missed page kinds at type-check time, runtime crash on unknown types is preferable to silent miscompile.

Target metrics: PLR0911 8 → 1.

## Done condition

- `uv run ruff check src --select PLR0911 --config 'lint.pylint.max-returns=6'` → 0 errors.
- `pyproject.toml` `[tool.ruff.lint.pylint] max-returns = 6` (down from 10).
- `docs/ratchet/baseline.toml` `[complexity] max_returns = <new peak ≤ 6>`.
- `uv run pytest -q --continue-on-collection-errors` → 1876 passed (no regression).
- `uv run pytest --cov=src/schematika/core` core/* TOTAL ≥ 93% (the floor is now ratcheted).
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps (both functions are tier-3, no Examples required — but verify nothing else regressed).
- `uv run pre-commit run --all-files` → exit 0 in worktree.
- `uv run python scripts/ratchet_check.py` → exit 0; `complexity.max_returns` cell reports the new peak.

## Test strategy (per plan section A + B)

- **Characterisation tests for `translate` first**: existing `tests/unit/test_transform.py` exercises most arms — implementer runs `uv run pytest --cov=src/schematika/core/transform.py --cov-report=term-missing` to identify uncovered isinstance branches and adds tests for any gap. Use `pytest-subtests` for table-driven tests, one subtest per Element subtype. Add a hypothesis property: `translate(translate(p, dx, dy), -dx, -dy) ≈ p` (use `dirty-equals.IsApprox(rel=1e-9)` for the float comparison) — verifies inverse-translation cancels.
- **Characterisation tests for `_render_page`**: per-page-kind table test with `pytest-subtests`, one subtest per `page_type` enum value. Add a test that asserts `assert_never` fires on a fabricated invalid `page_type` — guards against accidental fallback removal.
- **No new core/ helpers in this wave** → no new `core/` unit tests needed beyond the characterisation work above. Core coverage must stay ≥ 93%.

## Out of scope

- Touching any function other than `translate` and `_render_page`.
- Adding new core/ helpers (later waves).
- Changing the `cast("T", ...)` pattern in `translate` (ty narrowing is a known limitation; not a C0a concern).
- Updating `docs/API_STYLE.md` (separate doc commit, not in this wave).
