# Complexity & Duplication Reduction Plan

Goal: drive `pyproject.toml` complexity thresholds back toward ruff defaults (`max-complexity=10`, `max-returns=6`, `max-branches=12`, `max-args=8`, `max-statements=50`) by **extracting pure functions to `core/`** and **eliminating duplicated logic via shared core helpers**. After each wave: drop the relevant `pyproject.toml` threshold, lock the new low-water mark in `docs/ratchet/baseline.toml`, and prove `pytest --cov=src/schematika/core` ≥ 90 %. No new external runtime dependencies.

This plan picks up after Wave L3c. The existing ratchet machinery (`scripts/ratchet_check.py`, `scripts/metrics_snapshot.py`, `docs/ratchet/baseline.toml`, the 9-hook `.pre-commit-config.yaml`) is reused; one focused extension is needed (Wave C0-pre).

## Status as of 2026-04-25 (snapshot `2026-04-25T184750.toml`)

Live numbers from `just metrics` (the existing `metrics_snapshot.py`, which already runs lowered-threshold ruff for every relevant rule):

```
[complexity.distribution]
above_complexity_10 = 19    # C901
above_args_8        = 10    # PLR0913
above_branches_12   = 9     # PLR0912
above_statements_50 = 7     # PLR0915
above_returns_6     = 2     # PLR0911

[complexity.peaks]
max_complexity   = 22  in _phase4_render_graphics       (electrical/builder_phases.py:397)
max_args         = 16  in add_terminal                  (electrical/builder.py:81)
max_branches     = 22  in _phase2_register_connections  (electrical/builder_phases.py:144)
max_statements   = 69  in _phase2_register_connections  (electrical/builder_phases.py:144)
max_returns      = 10  in translate                     (core/transform.py:33)

[codebase]
src_loc            = 34 577
src_complexity_scc = 2 086
[suppressions]
noqa               = 75
ty_ignore          = 112
[tests]
passed             = 1 981
coverage_percent   = 89   (repo-wide)
```

Frozen `pyproject.toml` thresholds (high-water mark — this plan drives them down):

| Threshold | Current | Target (post-plan) |
| --------- | ------- | ------------------ |
| `max-complexity` (C901) | 22 | 10 |
| `max-returns` (PLR0911) | 10 | 6 |
| `max-branches` (PLR0912) | 22 | 12 |
| `max-args` (PLR0913) | 16 | 8 (decision rule below) |
| `max-statements` (PLR0915) | 70 | 50 |

All 44 ruff violations under R7b/R7c are policy-suppressed in `SUPPRESSIONS.md`. The plan deletes those entries one wave at a time as their underlying violations disappear.

## Strategy

Two complementary levers, applied per wave:

1. **Pure-function extraction.** Sub-logic in each hot function — pin-tuple math, set intersection on pin IDs, geometry comparisons, dispatch arithmetic — moves into `src/schematika/core/` modules as `@pure` (or `@deal.pure`) functions. The `fp_purity_gate.py` AST script (already strict in pre-commit, scopes to `src/schematika/core/` only, scans top-level `def`/`async def`, accepts `@pure` from `schematika._purity` or `@deal.pure`) catches new core/ functions automatically.
2. **Duplicated logic → shared core helpers.** Patterns that exist in 2+ domain packages (tolerance comparisons, axis-aligned line detection, dict-of-lists merging, element traversal) collapse into a single canonical implementation in `core/`. Domain modules import from `core/`; the existing import-linter contracts (`electrical-not-project`, `pcb-not-project`) keep direction sane.

Modern-Python idioms used as supporting tools (no external deps, all stdlib):

- **`match` / `case`** (Py 3.10+) — replaces isinstance/dispatch chains in `translate`, `_translate_path_d`, `_rotate_path_d`, `_render_element`, `_render_page`. Ruff still counts each `case` arm as a branch (no C901/PLR0912 reduction), **but** PLR0911 collapses to 1 (single match expression has one return) and PLR0915 trims via destructure-in-head.
- **`@dataclass(frozen=True, slots=True, kw_only=True)`** (Py 3.10+) — option bundles for the 16-arg / 13-arg builder methods. Direct PLR0913 reduction. `slots=True` is the project default for new frozen dataclasses.
- **`itertools.batched`** (Py 3.12+) — pole iteration in `_phase2`/`_phase3`; replaces manual chunking loops.
- **`typing.Protocol`** (Py 3.8+) — replaces `Any` boundaries (`_should_rotate(symbol_factory: Any)`, `adapt(circuit: Any)`); deletes ANN401 SUPPRESSIONS entries.
- **PEP 695 generics** (`def fn[T: Bound](...)`, Py 3.12+) — already in use on `pure`/`translate`. Apply to new core helpers; -2 LoC vs explicit `TypeVar`.

External libraries (`returns`, `expression`, `toolz`, `pyrsistent`, `more-itertools`) are **not** added: the zero-runtime-deps-in-core constraint is hard, and the stdlib idioms above cover every observed need. PEP 750 t-strings (3.14), free-threading (3.13/14), and PEP 765 finally-clauses bring nothing load-bearing for *this* refactor.

### Behaviour preservation

Schematika has no central snapshot fixture (`tests/conftest.py` is empty by design). Refactor safety relies entirely on the test suite — there is **no** visual-review step in any wave (per user decision: P&ID is not special; the existing tests are the contract). Defenses:
- The existing 1 981-test pytest suite (must pass per wave; count must not drop).
- `pytest --cov=src/schematika/core` ≥ 90 % verified at end of every wave that touches `core/`.
- Per-function characterisation tests added by the implementer subagent **before** each refactor of a non-trivial function (see "Test strategy" below).
- `inline-snapshot` for capturing the SVG element tree returned by complex functions, locked in the test file as a Python literal — any unintended change in output causes test failure.

`PYTEST_UPDATE_SNAPSHOTS=1` regeneration is **forbidden** during a wave unless the wave's stated purpose is regenerating snapshots; an unexpected snapshot diff is a wave failure to be debugged, not absorbed.

## Working model

Subagent-driven development per the `superpowers:subagent-driven-development` skill: the controller (this session, opus) extracts each wave's tasks, dispatches one implementer subagent per task with full task text + context, then dispatches sequential spec-compliance and code-quality reviewer subagents. Reviewer issues loop back to the same implementer. Tasks within a wave are sequential (no parallel implementer subagents — conflicts). Waves are sequential; each merges before the next starts.

### Worktree convention

```bash
git worktree add .worktrees/complexity/<wave-id> -b complexity/<wave-id>
# .worktrees/ is gitignored.
```

Each wave branches off the latest `branch1` HEAD, lands as a single squash-merge into `branch1` once both reviews pass, then the worktree is removed (`uv run python scripts/cleanup_worktree.py` if available, else manual `git worktree remove`).

### Subagent model selection

Per skill guidance: cheapest model that can do the work.

| Wave class | Model | Reason |
| ---------- | ----- | ------ |
| C0a–C0e (mechanical, 1–2 files, clear specs) | haiku | Match-case rewrites, small extractions; the spec encodes the answer. |
| C1a–C1e (multi-file phase-function refactors) | sonnet | Cross-module integration, frozen-dataclass introduction, must coordinate `state` flow. |
| C2a–C2d (public API, consumer coordination) | sonnet | Touches surface; risk of breaking real callers. |
| C3a–C3d (de-dup) | haiku | Migrate N call sites to one canonical helper. |
| C4a (Protocols), C4b (LoC gate), C4d (final sweep) | sonnet | Cross-cutting; small, but design judgment matters. |
| Spec reviewer subagents | haiku | Mechanical "does the diff match the spec" check. |
| Code-quality reviewer subagents | sonnet | Catches over-abstraction, AI-bloat, weak naming. |
| Final review (Wave C5) | opus + `superpowers:code-reviewer` | Whole-initiative, multi-PR scope; treat as the merge gate. |

### Per-wave protocol

For each wave the controller does, in order:

1. **Snapshot baseline.** Copy the relevant excerpts of the latest `docs/ratchet/snapshots/<timestamp>.toml` (run `just metrics` if stale) into `docs/ratchet/baselines/<wave-id>.md`. Capture: peaks before, distribution counts before, src LoC before, core/ coverage % before, target peaks/distribution/coverage after.
2. **Dispatch implementer** with full task text + scene-setting context (architecture rules, file list, target metrics, no-scope-creep reminder, the `superpowers:test-driven-development` skill reminder, sibling-file isolation rule). Implementer **does not read the plan file**; the controller passes everything it needs.
3. **Implementer loop** (in worktree):
   - **First action: `uv sync --all-extras`.** All test counts in this plan assume optional extras are installed (pcb tests need skidl/openpyxl, cable tests need wireviz, etc.). Without `--all-extras`, ~154 tests fail to collect and the wave's "test count must not drop" check is meaningless. The implementer never runs `uv sync` without `--all-extras`.
   - Read the target function. Run `uv run pytest --cov=src/schematika/<module> --cov-report=term-missing` to identify uncovered branches.
   - **Add characterisation tests first** for any uncovered branch the refactor will touch. Property tests via `hypothesis` for geometry / arithmetic helpers; `inline-snapshot` for complex outputs; `pytest-subtests` for table-driven dispatch.
   - Refactor in small, test-passing increments (TDD).
   - Drop the corresponding `pyproject.toml` threshold (or `baseline.toml` peak — see C0-pre) to its target value for the wave.
   - Run, in order:
     - `uv run ruff check src tests` → 0 (under the new threshold)
     - `uv run ty check` → 0 (held)
     - `uv run pytest --continue-on-collection-errors` → ≥ pre-wave passing count (baseline = **1 981** with `--all-extras`)
     - `uv run pytest --cov=src/schematika/core --cov-report=term` → ≥ baseline (rises monotonically; final target ≥ 90 %; only required if wave touched `core/`)
     - `uv run python scripts/api_style_gate.py --strict` → exit 0 (any wave touching public API surface)
     - `uv run python scripts/api_docs_audit.py --strict` → exit 0 (any wave touching tier-1 symbols — see Docstring tier policy below)
     - `uv run pre-commit run --all-files` → exit 0
     - `uv run python scripts/ratchet_check.py` → exit 0
   - Update `docs/ratchet/baseline.toml` via `just ratchet-update` if any locked metric improved.
   - Commit. Report: `DONE` / `DONE_WITH_CONCERNS:<text>` / `NEEDS_CONTEXT:<text>` / `BLOCKED:<text>`.
4. **Spec compliance review** (separate subagent, no conversation history): given the wave spec text + the diff (commit SHA range), verify only in-scope rules/thresholds changed, no other config changes, no unrelated diffs. If issues, return to step 3 with same implementer subagent.
5. **Code quality review** (separate subagent, only after spec review ✓): given the diff, audit for over-abstraction, single-use helpers added "for later", weak names, `# noqa` without `Why:`, missing tests on extracted helpers, AI-bloat docstrings (per `reviewing-ai-generated-python` skill smells). Issues loop back to step 3.
6. **Merge.** Squash-merge into `branch1`, remove worktree, append `docs/ratchet/PROGRESS.md` entry following the existing format (date, branch, commits, before/after counts, suppressions added, gate state, pytest count, coverage). Update `SUPPRESSIONS.md`: delete entries whose underlying violation disappeared, add new ones with substantive `Why:`.

### Test strategy & coverage gates

This is a *refactor* — every wave is required to leave behavior byte-identical. The defenses (characterisation first, then extraction, then verify):

**A. Characterisation tests before refactoring.** For any function with C901 ≥ 12 (i.e. anything in C0c, C0e, C1a–e):
1. Run `uv run pytest --cov=src/schematika/<module> --cov-report=term-missing` to list uncovered lines in the target function.
2. Add at least one test per missing line/branch the refactor will touch. Tests live in `tests/unit/test_<module>.py`.
3. For complex output (SVG element trees, wire-tuple lists, dataclass results) use **`inline-snapshot`** — `snapshot()` placeholder fills on first run, locks behavior thereafter. The snapshot lives in the test file body; a refactor that changes output produces a visible diff in the test file, not a mystery failure.
4. Use **`pytest-subtests`** for table-driven characterisation of dispatch functions: one subtest per `case` arm so a refactor failure points at the specific arm.
5. The wave's diff must include this test addition **before** the refactor commit (or as the same commit, with a clear ordering).

**B. New `core/` helpers — mandatory unit tests.** Every function added under `src/schematika/core/` ships with at least one test in `tests/unit/test_core_<module>.py`:
- **Geometry / arithmetic helpers** (`within_tolerance`, `is_vertical_line`, `offset_point`, etc.) → **`hypothesis`** property tests asserting symmetry / reflexivity / equivalence with the inline form being replaced. Plus ≥3 example-based edge tests (zero, negative, sign-boundary, NaN-rejection where relevant).
- **Dispatch / parser helpers** (`PathCommand` parsing, `wire_orientation`, per-command rotators) → table-driven tests via `pytest-subtests`, one subtest per case arm. Round-trip property where applicable: `parse(emit(c)) == c`, `rotate(rotate(p, θ), -θ) ≈ p` (use `dirty-equals.IsApprox` for the float comparison).
- **Tagged-union / dataclass extractions** (`RealizedComponent`, option bundles) → constructor-and-`replace`-roundtrip tests; `dirty-equals.IsPartialDict`-style assertions for forward-compat.

**C. Coverage ratchet for `core/`.** Wave C0-pre adds `pytest.min_core_coverage_percent = <baseline>` to `baseline.toml` and a `collect_core_coverage()` to `ratchet_check.py`. The number rises monotonically per wave; the ratchet pre-commit hook prevents regression. Final-plan target: **≥ 90 %** on `pytest --cov=src/schematika/core`. The implementer subagent runs `just ratchet-update` after each wave that improves the number.

**D. Mutation testing on extracted helpers.** Per user direction: **post-wave quality signal, not a hard gate** (mutmut is Linux-only and off-CI per pyproject). After each wave that adds ≥ 1 core/ module, the implementer (when on a Linux machine) runs `just mutmut` scoped to the new module. Kill-rate observed is documented in the wave's PROGRESS entry. Survivors that point at obviously weak tests trigger a follow-up test-strengthening commit; survivors that are genuinely equivalent mutants are noted and ignored. mutmut 3.x is the locked version.

**E. Hard wall-clock cap on the test suite.** `pytest-timeout` is configured with a 30 s default per test in `pyproject.toml [tool.pytest.ini_options] timeout = 30`. An extracted helper that introduces an infinite loop fails fast; without this, mutmut runs would hang on the bad mutant (and so would CI on a buggy refactor). Per-test override via `@pytest.mark.timeout(N)` for legitimately slow integration tests.

**F. No test deletion without justification.** `pytest --co -q` total must not decrease across a wave. Removing a test requires either (a) the test was characterisation that's now redundant with new core/ unit tests covering the same lines (link the new test in the PROGRESS entry), or (b) explicit user approval logged in PROGRESS. Renames don't count as deletions.

**G. Test-tooling availability.** All five plugins (`hypothesis`, `pytest-subtests`, `inline-snapshot`, `pytest-timeout`, `dirty-equals`) are installed by Wave C0-pre and available from C0a onward. The implementer subagent's prompt for each wave names which plugin is the natural fit for that wave's tests.

### Hard rules for all subagents

- Touch only files needed to clear the wave's scope. No drive-by reformatting, no docstring rewrites, no test edits beyond the wave's own characterisation/extraction tests.
- New core helpers go in modules named for what they compute (`core/geometry.py` *exists* — extend it; `core/svg_path.py`, `core/dict_utils.py`, `core/connection_geometry.py`, `core/pin_resolution.py`, `core/options.py` are new). No `core/utils.py` catch-all.
- Every new top-level core function carries `@pure` (from `schematika._purity`) or `@deal.pure`. Nested closures are not gate-checked but should still be free of side effects.
- Frozen dataclasses for any new state-bearing type: `@dataclass(frozen=True, slots=True, kw_only=True)`.
- Public-API changes in Tier C2 do **not** touch the consumer project (`../auxillary_cabinet_v3/`). Each C2 wave produces `docs/ratchet/migrations/C2<x>-consumer-migration.md` listing every old-call → new-call site with file:line citations, copy-pasteable replacement snippets, and a "what to test after migration" checklist. The user merges schematika first, then applies the migration doc to the consumer project at their convenience.
- Never raise a `pyproject.toml` threshold or a `baseline.toml` peak. Never add `# noqa: C901|PLR091*` to silence a finding without a one-line justification logged in `SUPPRESSIONS.md`. Prefer extraction over suppression every time.
- Do not bypass `pre-commit run --all-files` unless the failure is documented as already-baseline and unchanged-by-this-wave (record in the implementer report).
- Untracked files in the worktree that the implementer didn't create may belong to a sibling agent — leave them alone.
- Each wave ≤ ~30 files / ~600 LoC of diff. Split if larger.
- The implementer subagent does not delete pre-existing dead code beyond what its own extraction orphans.

## Docstring tier policy (read before any code change)

Schematika has **three docstring tiers**. Subagents must classify every function they add or change and apply the matching style. Both api-style and api-docs gates run in `--strict` mode in pre-commit; getting this wrong fails the wave.

### Tier 1 — Public API (210 currently-audited symbols, 0 gaps)

A symbol is tier-1 iff its name appears in `__all__` of one of these eight packages (the list is hardcoded in `scripts/api_docs_audit.py`):

```
schematika                       (72 symbols)
schematika.electrical            (71 symbols)
schematika.electrical.symbols    (21 symbols)
schematika.pid                   (21 symbols)
schematika.pid.symbols           (15 symbols)
schematika.pcb                   (2 symbols)
schematika.cable                 (3 symbols)
schematika.catalog               (5 symbols)
```

Required docstring shape (Google convention, `pydocstyle convention = "google"`):

```python
def add_terminal(self, name: str, /, *, position: Point | None = None) -> TerminalRef:
    """Register a terminal on the circuit.

    Args:
        name: Lookup key used by callers and exported on the terminal strip.
        position: Explicit coordinates; ``None`` triggers auto-layout.

    Returns:
        ``TerminalRef`` usable in subsequent ``add_connection`` calls.

    Raises:
        TerminalReuseError: If a terminal with ``name`` is already registered.

    Examples:
        >>> from schematika.electrical import CircuitBuilder
        >>> b = CircuitBuilder()
        >>> ref = b.add_terminal("X1")
        >>> ref.name
        'X1'
    """
```

Mandatory elements: imperative first line < 80 chars with period; `Args:` listing every parameter in signature order; `Returns:` describing meaning (not type); `Raises:` if the function raises; **`Examples:` block with runnable `>>>` doctest** (Wave A2a/b backfilled these — `uv run pytest --doctest-modules src/` must still pass after the change). No paraphrase. No `Note:`.

**Stale-doc note:** `docs/API_STYLE.md` line 119 says "no Examples block" — that's outdated. The current operative rule (per `api_docs_audit.py` and the A2a/A2b commits) requires `Examples:` or `>>>` doctests for tier-1. Plan defers fixing API_STYLE.md to a separate doc commit (out of scope for the C-series).

### Tier 2 — Public, not in `__all__`

Module-level callable, no `_` prefix, but not re-exported via the package `__all__`. Subject to:
- `api_style_gate.py` rules: `add_*`/`set_*` need exactly one positional-only arg before `*`; public functions taking `x: float, y: float` must accept `position: Point`; `build()` must return non-None `*BuildResult`; do not mix `label`/`name`/`tag` in one signature.
- ruff `D` (Google convention): docstring presence, imperative first line, Args/Returns/Raises if present.
- **No** `Examples:` block required (audit script doesn't see it).

### Tier 3 — Private (`_`-prefixed) and `core/` helpers

Per the `python-coding-and-tooling` skill: **default no docstring**. One short single-line WHY only when non-obvious (invariants, units, side-effect ordering, hidden constraints). The Q1 wave shrunk these aggressively; do not re-bloat them. Forbidden: restating the signature, `Args:`/`Returns:`/`Raises:` blocks paraphrasing types.

`core/` is **never** in `PACKAGES` of `api_docs_audit.py`, so new core helpers are always tier-3 by construction. They get `@pure` (or `@deal.pure`) and at most a single-line WHY.

### Per-wave classification

| Wave | Functions touched | Tier |
| ---- | ----------------- | ---- |
| C0a `translate` | `core/transform.py:translate` is **not** in any audited `__all__`; `_render_page` is `_`-prefixed. | Both **tier 3** — short WHY-only. (No api-docs audit failures from this wave.) |
| C0b/c svg_path | `core/svg_path.py` (new); `_translate_path_d`, `_rotate_path_d` (`_`-prefixed). | All **tier 3**. |
| C0d small fish | All `_`-prefixed except `pid/builder.py:build` (tier-1 — re-exported via `pid.__all__`). | Mostly **tier 3**; `PIDBuilder.build` is **tier 1** — keep its existing tier-1 docstring intact. |
| C0e `block` | `electrical/symbols/blocks.py:block` is **tier 1** (in `electrical.symbols.__all__`). New per-kind sub-factories are `_`-prefixed (tier 3). | The public `block` keeps its tier-1 docstring with Examples; sub-factories are tier 3. |
| C1-pre `RealizedComponent` | New private module `electrical/_realized.py`. | **Tier 3.** |
| C1a–e phase-fn extractions | All `_phase*` functions are `_`-prefixed; new `core/connection_geometry.py` helpers are tier 3. `CircuitBuilder.build` is **tier 1**. | Mostly **tier 3**; `CircuitBuilder.build` keeps its tier-1 docstring (signature unchanged). |
| C2a–d option bundles | `add_terminal`, `add_symbol`, `add_spdt`, `add_reference`, `add_equipment` all **tier 1**. New `PlacementOptions`/etc. dataclasses are placed in `core/options.py` → **tier 3** (core/ is never tier-1). | Tier-1 method docstrings MUST be rewritten to match the new signature: new `Args:` block, new `Examples:` doctest, updated `Raises:`. **api_docs_audit --strict must pass.** |
| C3a–d core helpers | All in `core/` → **tier 3.** | Short WHY-only or no docstring. |
| C4a Protocols | `core/protocols.py` (new) → **tier 3.** | Short WHY-only on each Protocol class. |

## Wave order

### Wave C0-pre — Numeric-ratchet extension + test-tooling install (single commit, no worktree)

Pure infrastructure change so every subsequent wave can lock its win in `baseline.toml` and use the better test plumbing. Run inline; no implementer subagent.

**Part 1 — Ratchet collectors.** Extend `scripts/ratchet_check.py`:
- Add `collect_complexity_peaks() -> dict[str, int] | None` that mirrors the lowered-threshold ruff invocation in `metrics_snapshot.py:_extract_peaks_and_distribution` and returns `{max_complexity, max_args, max_branches, max_statements, max_returns}`.
- Add `collect_core_coverage() -> int | None` running `pytest --cov=src/schematika/core --cov-report=term --no-header -q` and parsing `TOTAL ... NN%`.
- Extend `gather()` to emit five `le`-kind Metrics (one per peak) and one `ge`-kind Metric for core coverage.
- Extend `HEADER` template + `cmd_update`'s `required` list with the new keys.

**Part 2 — Baseline file.** Extend `docs/ratchet/baseline.toml`:
- Add `[complexity]` section (peaks pinned at current 22 / 16 / 22 / 70 / 10).
- Add `[pytest] min_core_coverage_percent = <measured>` (run `pytest --cov=src/schematika/core` once, pin the floor — likely ~85 %).

**Part 3 — Test-tooling dev-deps** (all verified mutmut-3 compatible — they don't run pytest in parallel and don't change exit semantics). Add to `[dependency-groups] dev` in `pyproject.toml`:

| Plugin | Purpose | Why mutmut-safe |
| ------ | ------- | --------------- |
| `pytest-subtests>=0.13` | Clean per-arm reporting for table-driven dispatch tests (`translate`, `_rotate_path_d`, `_phase2` kind-pair). Each `match` arm becomes its own subtest; one arm failing surfaces *which* arm. | In-process, no parallelism, no exit-code change. |
| `inline-snapshot>=0.20` | Characterisation tests for complex SVG element trees. Snapshot stored as a Python literal in the test body; auto-update via `pytest --inline-snapshot=update`. Replaces the removed `snapshot_svg` fixture without re-introducing a side directory. | Pure data; mutmut runs the test, snapshot equality holds or fails like any assertion. |
| `pytest-timeout>=2.3` | Hard wall-clock cap (default 30 s, override per-test). Refactor safety net — if an extracted helper introduces an infinite loop, mutmut and CI both catch it instead of hanging. | Documented mutmut-compatible; mutmut even uses similar timeout per mutant. |
| `dirty-equals>=0.9` | Partial-equality assertions (`IsApprox(0.0, abs=1e-6)`, `IsList(length=...)`, `IsPartialDict(...)`). Useful for asserting SVG element-tree shape without specifying every coordinate exactly. | Plain assertion library, no plugin hooks beyond `__eq__`. |
| (already in deps) `hypothesis>=6.104` | Property-based tests on geometry / arithmetic / SVG-path round-trip. The `mutmut` docs explicitly support hypothesis — derandomised seeds, no flake under mutation. | Already proven in this repo's dev workflow. |

`pytest-xdist` is **excluded** — incompatible with mutmut's runner model (mutmut runs each mutant in its own pytest invocation; xdist would conflict with that scheduling). Order-randomisation (`pytest-randomly`) is also excluded — useful for catching test-coupling but a deliberate scope choice to keep test runs reproducible while we're refactoring.

Also extend `pyproject.toml [tool.pytest.ini_options]` with `timeout = 30` (default per-test wall-clock cap) and append `--inline-snapshot=disable` to `addopts` so CI runs in fail-on-stale-snapshot mode while local dev can opt into `--inline-snapshot=update` interactively.

**Part 4 — Verify.** `uv sync --all-extras` (canonical: pcb / cable / mcp / excel / pdf tests need optional deps to collect; without `--all-extras` collection drops 154 tests) → `uv run python scripts/ratchet_check.py` exits 0 with the new rows green → `uv run pytest --collect-only -q` reports the same 1 981 tests collected (no plugin breaks discovery) → mutmut sanity smoke: `uv run mutmut run --paths-to-mutate src/schematika/core/_purity.py --max-children 1` (or similar tiny scope) completes one mutant cycle without errors, proving the new plugins don't break the runner.

**Commit.** `feat(wave-C0-pre): ratchet complexity peaks + core coverage + test plumbing`.

After C0-pre, every subsequent wave's success is mechanically gated by the ratchet hook, and implementers have `inline-snapshot`/`pytest-subtests`/`hypothesis` available for the test-quality work the plan demands.

### Tier C0 — Quick wins, no public API change

**Wave C0a — `translate` → `match`/`case`.** `core/transform.py:33`. Convert the 9-arm isinstance chain to a single `match` expression. **Fallback policy** (per user direction "stricter is better, but evaluate payoff vs complexity"):
- `translate` is a public API exported from `core/transform.py` and currently emits a `RuntimeWarning` for unknown types, returning `obj` unchanged. Keep the `warnings.warn(...)` fallback in the `case _:` arm — switching to `assert_never` here would crash callers that pass new domain types before they re-export translation, with no benefit (the warning has been emitted exactly zero times in real usage per `git log`). Cost of stricter > payoff.
- `_render_page` (`rendering/typst/compiler.py:262`, PLR0911=8) is purely internal dispatch over a closed enum of page kinds — no warn-fallback today. **Use `assert_never`** here. Cost of stricter ≈ 0; payoff = ty catches missed page kinds at type-check time, not runtime.
- General rule the implementer applies in C0a and downstream waves: public-API dispatch with an existing soft-fallback → keep the fallback; private/internal closed-enum dispatch → `assert_never`.
- Drop `pyproject.toml` `max-returns = 10 → 6`.
- Targets: `max_returns` peak 10 → ≤ 6 in `baseline.toml`. `above_returns_6` distribution 2 → 0.
- **Tests:** characterisation table-driven test for `translate` over every Element subtype (one row per existing isinstance branch) using `pytest-subtests`. Round-trip property with `hypothesis`: `translate(translate(p, dx, dy), -dx, -dy) ≈ p` (use `dirty-equals.IsApprox` for the float comparison). For `_render_page`: per-page-kind table test with `pytest-subtests`.

**Wave C0b — `_translate_path_d` extraction.** `core/transform.py:113`. Introduce `core/svg_path.py` with frozen `PathCommand` union (`MoveAbs`, `MoveRel`, `LineAbs`, `LineRel`, `HLine`, `VLine`, `Curve`, `SmoothCurve`, `QuadraticCurve`, `Tee`, `Close`). The parser becomes a `match` over typed tokens. Keep `tokenize_path_d` where it is (already pure, already tested).
- Targets: C901 11 → ≤10, PLR0912 13 → ≤12 for `_translate_path_d`.
- Tests: every `PathCommand` parser arm gets a unit test in `tests/unit/test_core_svg_path.py`. Hypothesis property: `parse(emit(c)) == c` round-trip.

**Wave C0c — `_rotate_path_d` rewrite atop C0b.** `core/transform.py:271`. Replace the 63-statement state machine with `parse_path → list[PathCommand] → [rotate_command(c, angle, center) for c in cmds] → emit`. Per-command rotators (`rotate_curve`, `rotate_line`, `rotate_arc`) live in `core/svg_path.py` as small pure helpers.
- Targets: C901 13 → ≤10, PLR0912 14 → ≤12, PLR0915 63 → ≤50. `above_statements_50` 7 → 6.
- Tests: per-rotator unit tests; hypothesis property: `rotate(rotate(p, θ), -θ) ≈ p` within tolerance, for each command type.

**Wave C0d — small C901 fish (sweep, single wave).** Six functions, each one pure helper extraction:
- `core/renderer.py:48 calculate_bounds` (C901=13)
- `rendering/svg.py:25 _render_element`, `rendering/svg.py:83 to_xml_element` (C901=12 each)
- `electrical/symbols/motors.py:46 _three_pole_motor` (C901=11)
- `electrical/utils/terminal_bridges.py:59 parse_terminal_pins_from_csv` (C901=11)
- `rendering/typst/markdown_converter.py:46 _convert_lines` (C901=12)
- `project.py:1251 _add_page_to_compiler` (C901=13)
- `pid/builder.py:317 build` (C901=11)
- Targets: drop `pyproject.toml` `max-complexity = 22 → 16`. `above_complexity_10` distribution 19 → ≤8 (the four phase functions and `_rotate_path_d` post-C0c remain; that's 5; plus a couple of close ones).
- Tests: characterisation tests for any branch not currently covered. New helpers tested in their respective `tests/unit/test_*.py`.

**Wave C0e — `electrical/symbols/blocks.py:227 block`.** Three-metric concentration: C901=15, PLR0912=17, PLR0915=61. Symbol factory with deep branching on block kind / port-set / orientation. Extract per-kind sub-factories.
- Targets: C901 15 → ≤10, PLR0912 17 → ≤12, PLR0915 61 → ≤50.
- Tests: per-kind generation tests; check the SVG output dataclass tree is unchanged for each case.

End-of-tier C0 state: `max-complexity = 16`, `max-returns = 6`. Other thresholds unchanged. Five SUPPRESSIONS entries deleted.

### Tier C1 — The big four phase functions (+ `CircuitBuilder.build`)

These dominate the ratchet. The phase functions currently operate on `dict[str, Any]` ("realized_components") with field accesses like `comp["spec"].kind` and `comp["tag"]`. **Tier-C1 prerequisite (Wave C1-pre):** introduce a frozen `RealizedComponent` and frozen `RealizedSpec` dataclass in `electrical/builder_phases.py` (or a new private module `electrical/_realized.py`), refactor `_phase1` and the internal builders to produce these instead of dicts. This is a larger structural change but it's required to make the per-phase extractions pure.

**Wave C1-pre — `RealizedComponent` frozen dataclass.** No metric drops in this wave; pure structural prep.
- New types: `RealizedComponent(tag, spec, ports, ...)` and `RealizedSpec(kind, poles, connect_to_next, placed_*_of, connection_side, ...)`. Both `frozen=True, slots=True, kw_only=True`.
- Migrate every site that constructs the dict + every site that reads `["tag"]`/`["spec"]` field access.
- Tests: existing tests must continue to pass; new dataclass constructors get small unit tests.

**Wave C1a — `_phase2_register_connections`.** `electrical/builder_phases.py:144`. Extract pure helpers into new `core/connection_geometry.py`:
- `compute_wire_tuple(src_tag, src_pin, tgt_tag, tgt_pin) -> tuple[str, str, str, str]`
- `pole_pin_pairs(component: RealizedComponent, pole_count: int) -> Sequence[tuple[str, str]]` — note: `RealizedComponent` is from `electrical/`, so this helper takes primitives or moves to a new `electrical/_pure_helpers.py`. Decision: take primitives in core, keep the wrapping in `electrical/`. **The pure-core extractions only see strings and ints.**
- The kind-pair dispatch itself becomes a `match (curr.spec.kind, next_comp.spec.kind):` block — same metric count, but readable.
- Targets: C901 21 → ≤14, PLR0912 22 → ≤14, PLR0915 69 → ≤50.

**Wave C1b — `_phase4_render_graphics`.** `electrical/builder_phases.py:397`. Extract into `core/connection_geometry.py` (continuation):
- `wire_orientation(line: Line, eps: float) -> Literal["vertical", "horizontal", "diagonal"]`
- `intersect_pin_sets(a: frozenset[str], b: frozenset[str], pin_filter: frozenset[str] | None) -> frozenset[str]`
- `label_position_for_wire(line: Line, threshold: float) -> Point | None`
- Targets: C901 22 → ≤14, PLR0912 21 → ≤14, PLR0915 65 → ≤50.

**Wave C1c — `_phase1_tag_and_state`.** `electrical/builder_phases.py:36`. R7c reviewer flagged extractable sub-logic (terminal-ID resolution + Y-position computation). Extract `resolve_terminal_id(...) -> str` and `compute_y_position(...) -> float` into new helpers; the latter goes to `core/geometry.py`, the former to a small `electrical/_resolution.py`.
- Targets: PLR0912 17 → ≤12, PLR0915 51 → ≤50.

**Wave C1d — `_phase3_instantiate_symbols`.** `electrical/builder_phases.py:300`. Extract `instantiate_symbol_for_kind(...)` per kind; the function shrinks to a `match`-driven dispatch.
- Targets: C901 15 → ≤12, PLR0912 16 → ≤12, PLR0915 55 → ≤50.

**Wave C1e — `CircuitBuilder.build`.** `electrical/builder.py:908`. Extract:
- `extract_used_terminals(spec) -> Sequence[str]` (returns terminal tag IDs — primitives)
- `format_connection_log(wires: Sequence[tuple[str, str, str, str]]) -> Sequence[str]`
- The `_single_instance_gen` closure stays local — it genuinely captures and mutates outer-scope dicts; not a pure-extraction candidate.
- Targets: C901 18 → ≤12, PLR0915 51 → ≤50.

End-of-tier C1: drop `pyproject.toml` `max-complexity = 16 → 12`, `max-branches = 22 → 14`, `max-statements = 70 → 50`. Approximately 12 SUPPRESSIONS entries deleted. Distribution `above_complexity_10 = 19 → ~3`.

### Tier C2 — Argument bundling (public API)

Touches public API. **Per user direction:** no backwards compatibility. The new signature replaces the old one in a single commit per wave. No `**legacy_kwargs` shim, no `DeprecationWarning`, no transition window. The consumer project is updated by the user separately, guided by the migration document the wave produces. All changes happen in this branch only — Tier C2 does NOT touch `../auxillary_cabinet_v3/`.

This is intentional: alpha library, sole author, breaking changes are fine (per CLAUDE.md), and a one-shot replacement keeps the diff honest and reviewable.

Coordinate with `scripts/api_style_gate.py` (`add_*` / `set_*` methods need exactly one positional-only arg before `*`; public functions taking `x: float, y: float` must accept `position: Point`; `build()` must return a non-None `*BuildResult`). Re-run it locally before commit. Coordinate with `scripts/api_docs_audit.py` — the changed methods are tier-1 (CircuitBuilder is in `schematika.electrical.__all__`), so their docstrings MUST be rewritten to match the new signature: Google-style `Args:` / `Returns:` / `Raises:` block + runnable `>>>` doctest example. `uv run python scripts/api_docs_audit.py --strict` must exit 0 before the wave is DONE.

**Consumer-migration document.** Each C2 wave creates `docs/ratchet/migrations/<wave-id>-consumer-migration.md` containing:
1. **Summary** — one paragraph: which method changed, why, the new signature shape.
2. **Old → new mapping** — for every kwarg name, the new option-bundle field path. E.g. `relative_to=...` → `placement=PlacementOptions(relative_to=...)`.
3. **Call-site index** — `grep`-able list of consumer files known (or assumed) to call the changed method, with old → new replacement snippet for each. The implementer subagent greps `../auxillary_cabinet_v3/` (read-only) at wave time to populate this list — it does not edit those files, only references them.
4. **What to test after migration** — the smallest checklist of consumer behaviours that exercise the changed surface.
5. **Breakage note** — explicit: "this is a breaking change; the consumer will not import or run until updated. There is no compatibility shim."

**Wave C2a — `add_terminal` 16 → ≤5 args.** `electrical/builder.py:81`. New types in `core/options.py`:
- `PlacementOptions(relative_to, position, spacing, x_offset)` — frozen, slots, kw_only
- `TerminalDisplayOptions(label_pos, pin_label_pos)`
- `ConnectionOptions(connect_from_previous, connect_to_next, connection_side, bridge, wire_label)`

**Wave C2b — `add_symbol` 13 → ≤4 args.** Reuses `PlacementOptions`. New `SymbolConfig(poles, pins, device, wire_labels_above)`.

**Wave C2c — `add_spdt` 12 → ≤4 args.** Reuses `PlacementOptions` + small `SpdtConfig`.

**Wave C2d — remaining PLR0913 sites.** `add_reference` (9), `build_from_descriptors` (12), `add_equipment` (10), `create_horizontal_layout` (9), `_walk_loop` (9), `_route_one_cable` (9). Bundle or rename per case.

End-of-tier C2 threshold drop: **`max-args = 8`** (per user direction — the ruff default). If any public/private function still exceeds 8 args after the four waves, that's a wave failure to resolve before merging C2d, not a threshold compromise. SUPPRESSIONS R7b entries deleted.

### Tier C3 — Duplicated logic → shared core

**Wave C3a — extend `core/geometry.py` (already exists).** Add:
- `within_tolerance(a: float, b: float, eps: float) -> bool`
- `is_vertical_line(line: Line, eps: float) -> bool`
- `is_horizontal_line(line: Line, eps: float) -> bool`

Migrate ~9 sites across `pid/connections.py:61-62,142`, `pid/validation.py:51-60`, `electrical/builder_phases.py:445`, `electrical/layout/wire_labels.py:101-102`, `electrical/layout/layout.py:45,60`. Honest LoC reduction: ~15–25; the value is one canonical implementation under purity-gate enforcement.

Tests: hypothesis on `within_tolerance` (reflexivity, symmetry, equivalence with the inline form). Per-axis tests on `is_vertical_line` / `is_horizontal_line`.

**Wave C3b — bbox / text-bbox visibility.** Promote `boxes_overlap` and `text_bbox` from `core/validation.py` to `core/geometry.py` (or re-export). Migrate `pid/validation.py:_check_equipment_overlap` to use the canonical implementation. No new code, just moves and migrates.

**Wave C3c — `core/dict_utils.py::merge_dict_of_lists`.** Extract from `electrical/builder_utils.py:58-64`; migrate the 2 other sites in `electrical/utils/utils.py:16-19` and `electrical/autonumbering.py:26-27`. Hypothesis property: associativity (`merge([merge([a, b]), c]) == merge([a, b, c])`).

**Wave C3d — traversal usage audit.** Code-review-only wave (no diff if clean). Identify any domain module that hand-rolls element iteration instead of using `core/traversal.py`. The agent's report already flagged `pid/validation.py` `_check_equipment_overlap` (handled in C3b). If any new offenders surface, migrate them; otherwise document the audit result in PROGRESS and move on.

**C3e (deferred).** Port resolution unification across `electrical` / `pid` / `pcb`. The duplication agent flagged this as high-risk because semantics genuinely differ (electrical pin numbers, PID instrument tags, PCB net-IDs). Revisit only after Tier C1 lands — the phase-function refactor will reveal the actual shape of port resolution.

### Tier C4 — Lock the gate

**Wave C4a — `Protocol` types replace top `Any` boundaries.** Define in `core/protocols.py` (new module):
- `class SymbolFactory(Protocol)` — `def __call__(self, label, ...) -> Symbol: ...` and `.ports` attribute.
- `class SkidlPart(Protocol)`, `class SkidlCircuit(Protocol)` — duck-typed SKiDL surfaces.
- `class GenerationStateProto(Protocol)` — for `electrical/layout/layout.py` to break the circular import that forces `Any`.

Migrate `_should_rotate(symbol_factory)`, `template_name(template)`, `adapt(circuit)`, `build(circuit)`, `layout_horizontal(start_state)`, etc. Deletes ≥10 `# noqa: ANN401` from SUPPRESSIONS.md. Targets reduction in `[suppressions] noqa` count.

**Wave C4b — LoC-per-function gate (only after thresholds stable).** New `scripts/loc_per_function.py` AST walker:
- Counts physical LoC per top-level `def`/`async def` in `src/schematika/` (excluding `tools/cad_parser/`).
- Reads `[loc_check] max_loc = <baseline>` from `pyproject.toml`. Initial `max_loc` = current peak (from a `just metrics` run); ratcheted down on subsequent waves.
- Wired as the 10th pre-commit hook with `pass_filenames: false, always_run: true`.

Threshold drop strategy: target `max_loc = 60` long-term, but pin at observed peak first.

**Wave C4c — `code-simplifier` documented.** Add an "after-implementation review" step to `docs/TOOLING.md` referencing the `python-coding-and-tooling` skill's recommendation to dispatch `code-simplifier:code-simplifier` on the changed files after substantive feature commits. Update CLAUDE.md "Build commands" with one new line.

**Wave C4d — Final threshold sweep.** Drop `pyproject.toml` to ruff defaults: `max-complexity = 10`, `max-args = 8`, `max-branches = 12`, `max-statements = 50`, `max-returns = 6`. Verify `just ci` clean. Delete every R7b/R7c entry from `SUPPRESSIONS.md`. Pin `baseline.toml` `[complexity]` peaks at zero (defaults are now in pyproject; ratchet enforces the floor). Update CLAUDE.md if it references the old high-water marks.

End-of-plan state: ruff complexity gates at default values. Pre-commit ratchet hook prevents future regression. `pytest --cov=src/schematika/core` ≥ 90 % pinned. `just metrics` snapshot shows zero distribution counts above defaults.

### Tier C5 — Final review

**Wave C5a — `superpowers:code-reviewer` over the whole initiative.** Dispatch the final review subagent (opus) with: full SHA range from C0-pre to C4d, the original goal statement, the threshold ladder. The reviewer's job is to catch:
- Functions that grew during the plan (anti-pattern: extraction created longer chains).
- Public-API breakage that the C2 migration docs missed (verify each migration doc against current `../auxillary_cabinet_v3/` call sites — read-only grep).
- Tests that were dropped.
- New `# noqa` / `# ty: ignore` without `Why:` in `SUPPRESSIONS.md`.
- Core/ modules whose names mismatch their contents.
- Whole-initiative LoC delta vs `[codebase] src_loc` baseline.

If the reviewer flags issues, dispatch a fix subagent (haiku for mechanical, sonnet for design). Iterate until approved.

Then: `superpowers:finishing-a-development-branch` to integrate the entire C-series into `main`.

## Bookkeeping

- `docs/ratchet/COMPLEXITY_PLAN.md` — this file. Updated only when scope changes.
- `docs/ratchet/PROGRESS.md` — append-only log; one entry per merged wave (continues the existing format used through L3c).
- `docs/ratchet/baselines/C<n>.md` — frozen baseline at start of each wave; copy from latest `metrics_snapshot` excerpt.
- `docs/ratchet/baseline.toml` — extended in C0-pre with `[complexity]` peaks + `pytest.min_core_coverage_percent`. Updated after every wave that improves a peak.
- `docs/ratchet/SUPPRESSIONS.md` — every new `# noqa` introduced during a wave logged with substantive `Why:`. R7b/R7c entries deleted as their underlying violations disappear.
- `docs/ratchet/snapshots/<timestamp>.toml` — rolling `just metrics` outputs; produced ad hoc, not committed per wave.
- `docs/ratchet/migrations/<wave-id>-consumer-migration.md` — one per Tier-C2 wave; documents the consumer-project changes the user applies separately (per resolved decision 6).

## Resolved decisions

The following decisions are locked. Subagents must follow them; do not re-litigate.

1. **`assert_never` vs `warnings.warn` fallback.** Stricter where cheap. Public-API dispatch with an existing soft-fallback (e.g. `translate`) keeps `warnings.warn`. Internal closed-enum dispatch (e.g. `_render_page`) uses `assert_never`. Implementer evaluates payoff vs complexity per site and notes the choice in their report.
2. **`RealizedComponent` location.** New private module `src/schematika/electrical/_realized.py`.
3. **C2 backwards compatibility — none.** Each C2 wave makes a hard breaking change in a single commit. No `**legacy_kwargs` shim, no `DeprecationWarning`, no transition window. The consumer project breaks at import-time until updated; the migration doc tells the user exactly what to change. (Per user direction; alpha library, sole author, breaking changes are fine per CLAUDE.md.)
4. **`max-args` final target.** **8** (ruff default). Hit it or fail the wave; no compromise.
5. **Mutation testing.** Post-wave quality signal logged in PROGRESS. Not a hard gate.
6. **Cross-repo scope.** All changes in this branch only. The consumer project is not touched by any wave. Migration docs (decision 3) make the user-side update mechanical when the user is ready.
7. **Visual review.** Not used. The existing 1 981-test pytest suite + new characterisation tests + `inline-snapshot` capture of complex outputs are the contract. No `validate_pid()` step in any wave; no `pid_review.py` step in any wave.

## Out of scope

- Pytest plugins beyond the five added in C0-pre (`hypothesis`, `pytest-subtests`, `inline-snapshot`, `pytest-timeout`, `dirty-equals`) plus the existing `pytest-cov` / `pytest-examples`. Any further plugin requires a separate decision.
- Coverage tooling change (stay on `pytest-cov`; don't migrate to `coverage.py`-direct).
- Mutmut tooling change (stay on mutmut 3.x per pyproject pin; mutmut-3 compatibility constrains plugin choices in C0-pre).
- Documentation rewrites beyond what each wave's targeted code requires.
- Visual/rendering output changes — refactors must produce byte-identical SVG/PDF. If a wave intentionally changes output, that's a separate visible commit and a different plan.
- Unrelated public API changes (renames, deprecations beyond C2's option bundles).
- Adding any external runtime dependency. `core/` stays zero-deps; domain packages may use existing optional extras only.
- `tools/cad_parser/` — outside the ratchet, as in prior tiers.
- Performance work, dependency upgrades, repo restructuring.
- Ratchet machinery rewrites beyond the C0-pre extension (no migration to a different gate framework).
- Any edit to `../auxillary_cabinet_v3/`. C2 produces migration docs, not edits, per resolved decision 6.

## Order of operations once approved

1. `uv sync --all-extras` (canonical for the whole plan; never `uv sync` alone). Then `just metrics` to refresh `docs/ratchet/snapshots/<timestamp>.toml`. Confirm peaks and distribution match this plan's status table within ±1.
2. Snapshot baseline into `docs/ratchet/baselines/C0-pre.md`.
3. Execute **Wave C0-pre** inline (no worktree, no implementer subagent — controller modifies `scripts/ratchet_check.py` and `docs/ratchet/baseline.toml`, runs the script, commits).
4. Snapshot baseline into `docs/ratchet/baselines/C0a.md`.
5. Create worktree `.worktrees/complexity/C0a`. Dispatch implementer subagent (haiku) for Wave C0a (`translate` → `match`/`case` + `_render_page`). Dispatch spec reviewer (haiku) and code quality reviewer (sonnet) per protocol. Merge.
6. Continue down the wave order. Tiers may interleave only if a C1 wave naturally creates a C3 helper — record the cross-tier extraction in both PROGRESS entries.
7. After Tier C4, dispatch **Wave C5a** final review.
8. Apply `superpowers:finishing-a-development-branch` to integrate.
