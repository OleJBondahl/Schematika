# Post-Wave-5 snapshot — 2026-04-24

Intermediate snapshot after Waves 1–5. Mutmut **not** re-run; see
`../2026-04-24/mutmut_results.txt` for the pre-refactor reference.

## Delta table — pre-refactor → post-Wave-4 → post-Wave-5

| Tool | Pre | Post-W4 | Post-W5 | Total Δ | Note |
|---|---:|---:|---:|---:|---|
| pytest | 1459 pass / 4 xfail | 1582 / 4 | **1582 / 4** | +123 | Wave 3 safety net; stable through W5 |
| coverage | 84 % (1177 missed) | 84 % (1161) | 84 % (1167 / 7354) | ~ | test code growth slightly diluted pct |
| scc LoC (Python) | 29 537 / 170 | 30 636 / 174 | ~30 700 / ~180 | +1 200 / +10 | new error modules + tests |
| ruff errors (src+tests) | 615 | 602 | **241** | −374 | Wave 5 auto-fixes + rule bumps |
| ruff errors (workspace) | — | — | 385 | — | includes examples/, scripts/ not previously measured |
| ty diagnostics (src/) | ~35 | ~45 | **15** | −20 | Wave 5 API cleanup cascade |
| ty diagnostics (workspace) | 39 | 54 | 146 | +107 | includes examples/, scripts/ now |
| interrogate | 80.3 % | 80.1 % | **80.4 %** | +0.1 pp | docstring additions offset deletions |
| vulture (conf 60, no whitelist) | 163 | 162 | 162 | −1 | |
| vulture (conf 60, WITH whitelist) | — | — | **88** | — | new `scripts/vulture_whitelist.py` |
| import-linter | 1 broken | **0 broken** | 0 broken | ✓ | Wave 4 fix held |
| fp-purity-gate | 54 missing | 54 | 54 | 0 | Wave 6 target |
| api-style-gate | 18 | 17 | **0** | −18 | Wave 5 target met |
| `raise ValueError` in src/ | 59 | 59 | **3** | −56 | domain bases now used |
| darglint (lines) | 890 | 885 | — | — | |

## Key wins (Wave 5)

- **api_style_gate: 17 → 0** — positional-only `/` markers on `set_layout`, `add_terminal`, `add_symbol`, `add_spdt`, `add_reference`, `add_connection`, PID equivalents. `Point` kwarg alternatives on x/y scalar methods. `Project.build() → None` explicitly exempted (documented rationale: top-level PDF compile, not a data builder).
- **Error hierarchy**: 59 raw `ValueError` → domain bases. New modules: `src/schematika/pid/errors.py`, `cable/errors.py`, `block/errors.py`, `catalog/errors.py`. Domain bases still inherit from `ValueError` for backward-compat — allows `except CircuitValidationError` precision AND keeps `except ValueError` working for tests.
- **ty library-code diagnostics: 54 → 15** — 72 % reduction in src/. Most were quoted-annotation cleanup from ruff auto-fix + tighter signatures.

## Breaking changes (all kwargs-safe)

All signatures still accept the old positional form IF callers used kwargs for secondary args (which they did in both schematika tests and `auxillary_cabinet_v3`). The agent's grep of the consumer project confirmed **zero breaking call sites**.

Specific migration snippets for any future caller that DID use positional secondary args:
- `builder.set_layout(0, 0, 150, 50)` → `builder.set_layout(x=0, y=0, spacing=150, symbol_spacing=50)`
- `builder.add_terminal("X1", 3)` → `builder.add_terminal("X1", poles=3)`

New preferred form uses `Point`: `builder.set_layout(Point(0, 0), spacing=150, symbol_spacing=50)`.

## Consumer impact (`../auxillary_cabinet_v3/`)

**Zero** breaking call sites. Every consumer call was already kwargs-after-first-positional, which is exactly the form Wave 5 enforces. Documented stale references live only in consumer-project `docs/superpowers/plans/` markdown.

## Worktree base note

The Wave 5 agent's worktree was initially checked out at `8ca4e07` (stale), not `5942dd9` (current branch1 tip). The agent self-corrected with `git merge --ff-only branch1` before starting work. Future worktree dispatch mechanism may want to ensure worktrees start at the current branch tip rather than an ancestor. Not blocking for this wave.

## Commits

| SHA | Title |
|---|---|
| `69ec04e` | refactor(wave-5-1): api_style_gate — 0 findings |
| `04dd35d` | refactor(wave-5-4): ruff auto-fixes + config bumps |
| `5e5f296` | refactor(wave-5-2): error hierarchy — 59 ValueError → domain bases |
| `a1e279d` | refactor(wave-5-5): vulture whitelist for public API + dynamic access |

## What was NOT done (by design)

- **Category 5-3 (narrow `except Exception` in pcb/)** — agent found 0 such patterns in `pcb/`. MCP server had 2 broad catches, deemed legitimate (user-code execution handler); left intact.
- **Vulture deletions** — agent whitelisted 74 symbols (all verified public API / dynamic access) and deleted 0. Conservative; future waves can prune once each module stabilizes.
- **ValueError inheritance removal** — domain bases still inherit from `ValueError`. Changing this would require rewriting ~44 test catches; deferred as lower priority.

## Remaining debt heading into Wave 6

- fp-purity-gate: 54 unmarked `core/` functions (Wave 6 scope)
- ruff src+tests: 241 errors (mostly docstring D-rules, acceptable)
- ty src/: 15 diagnostics (remaining library type issues, manageable)
- darglint: unmeasured this wave (was 885 lines post-W4)
- 3 legit `ValueError` in `core/parts.py` (numeric programmer errors at stdlib boundaries, per API_STYLE)
