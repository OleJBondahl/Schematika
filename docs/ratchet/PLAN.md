# Quality Ratchet Plan

Goal: drive every quality tool to **strict config + zero violations**, one tool at a time, via subagent-driven development in isolated worktrees.

Status as of 2026-04-25 (pre-ratchet baseline, post-Wave-6):

| Tool          | Baseline                    | Target          |
| ------------- | --------------------------- | --------------- |
| ruff lint     | 385 violations, 15 rule sets | 0, ~25 rule sets |
| ruff format   | 5 files dirty (tools/)      | 0               |
| ty            | 191 diagnostics             | 0, strict rules |
| import-linter | 0 broken                    | 0 (hold)        |
| darglint      | 835 DAR violations          | 0               |
| docstr-coverage | 80.6% (661/820)           | ≥95%            |
| vulture       | 88 findings (post whitelist) | 0              |
| radon cc      | 1 C-grade                   | 0               |
| bandit        | passing                     | strict + 0      |
| api_style_gate | 0                           | 0 (hold)        |
| fp_purity_gate | 0                           | 0 (hold)        |
| pytest        | 1582 passing, 84% cov       | (testing agent owns) |
| mutmut        | 66% kill rate               | (testing agent owns) |

The testing-focused work (pytest expansion, mutmut survivors, coverage) is owned by a separate agent; this plan **does not touch tests** beyond what individual ratchet fixes incidentally require.

---

## Working model

### Subagent-driven development in worktrees

Every wave below is executed as a **subagent dispatch**, never inline:

1. **Controller (this session)** maintains plan, dispatches subagents, collects status, commits ratchet config bumps.
2. **Implementer subagent** runs in a dedicated git worktree. One subagent per wave.
3. **Spec reviewer subagent** confirms the wave's rule set / fix scope was honored.
4. **Code quality reviewer subagent** approves the implementation diff before merge.

Worktree convention (per `using-git-worktrees`):

```bash
git worktree add .worktrees/ratchet/<wave-id> -b ratchet/<wave-id>
# .worktrees/ is already gitignored — verified.
```

Each wave creates one branch off the current `branch1` HEAD, lands as a single squash-merge into `branch1` once all reviews pass, then the worktree is removed.

### Per-wave protocol

For each wave the controller does, in order:

1. Snapshot baseline (numbers from `just stats` + relevant tool output) into `docs/ratchet/baselines/<wave-id>.md`.
2. Dispatch implementer with: full wave spec, current baseline, list of files allowed to touch, "no scope creep" reminder.
3. Implementer: branch in worktree → loosen-then-tighten loop:
   - Add the new rule(s) to config.
   - Run the tool, record violations.
   - Fix violations (smallest, most local change).
   - Re-run, the **wave's gate** must hit zero.
   - Run the controller-supplied "no-regression" check: every other tool's count must not be worse than the wave-start baseline. (Baseline `just ci` is broken until the ratchet finishes — that's the whole point. We can't demand `just ci` pass; we demand "this wave's gate newly green AND nothing else regressed".)
   - Bypass pre-commit hooks for the wave commit if (and only if) baseline pre-commit fails on debt that this wave isn't tasked with fixing. Note this in the implementer report.
   - Commit; report DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED.
4. Dispatch spec reviewer: only the rules in scope were enabled, no other config changes, no unrelated diffs.
5. Dispatch code quality reviewer: diff is minimal, no new dead code, no abstractions added "for later".
6. On approval: squash-merge into `branch1`, remove worktree, update `docs/ratchet/PROGRESS.md`.

### Hard rules for all subagents

- Touch only files needed to clear the wave's violations. No drive-by reformatting, no docstring tone changes, no test edits.
- Never add `# noqa`, `# type: ignore`, or `# fmt: off` to silence a finding without a one-line `Why:` comment justifying it; collect all justified suppressions in `docs/ratchet/SUPPRESSIONS.md` so the next wave can revisit.
- Never weaken an existing rule to clear a different rule.
- Each wave is a single commit's worth of logical change; if a wave grows past ~30 files or ~600 LoC of diff, stop and split.

---

## Wave order

Each wave is a self-contained ratchet step. Order is chosen so cheap, mostly-mechanical wins land first and lock state before harder semantic work.

### Tier 1 — Format & low-friction lint

**Wave R0 — Format clean.** Reformat the 5 dirty `tools/cad_parser/` files; add `ruff format --check` to the pre-commit `fail_fast` set if not already there.

**Wave R1 — Ruff baseline truth.** Run `ruff check --fix --unsafe-fixes` once on src/ + tests/, commit only the fixes that pass `just ci`. Pure mechanical reduction of the 385 number.

**Wave R2 — Enable RUF + PERF + PIE + SIM extensions + ICN + ISC.** Mostly auto-fixable. Drive each to zero before enabling next.

**Wave R3 — Enable T20 (no print), LOG (logging), G (logging-format), PT enforcement, Q (quotes).** All mechanical.

### Tier 2 — Ruff semantic

**Wave R4 — D-series to zero.** 147 docstring violations. Strategy: write missing docstrings rather than add per-file ignores. Section reviewer can demand actual content, not "TODO".

**Wave R5 — N-series + naming.** 24 N806 + scattered other naming. Rename or per-symbol justify.

**Wave R6 — B (bugbear) + BLE + RET + RSE + TRY.** Real semantic checks. Most B018 (65) and ARG (11) sit here.

**Wave R7 — PLR + C90 complexity.** PLR2004 (32 magic values) → named constants; PLR0913 (11 too-many-args) → dataclass / kwargs object; C901 → split functions. Coordinate with `api_style_gate.py` so signatures still pass.

**Wave R8 — S (bandit-equivalent ruff) + DTZ + PTH + ERA + FBT + EM + TCH + TID.** Final ruff sweep. After this, ruff config is "strict" and `ignore = []`.

### Tier 3 — Type checker

**Wave T0 — Ty noise reduction.** Remove the 22 `unused-type-ignore-comment` first (each one is a free win and exposes whatever was hidden). Then audit `scripts/vulture_whitelist.py` (65 unresolved-import) — that file is a vulture artifact and should be excluded from ty rather than fixed.

**Wave T1 — Ty: unresolved-attribute / unresolved-import in src/.** The 82+31 from the audit. Real type fixes; may require adding `py.typed`, stubs, or correcting actual bugs.

**Wave T2 — Ty: argument-type errors.** 25 missing-argument + 27 invalid-argument-type, concentrated in `electrical/builder.py` and examples. Likely surfaces real API drift between core and consumer call sites.

**Wave T3 — Ty strict mode.** Add explicit `[tool.ty.rules]` table promoting all default-warn rules to error. Re-run; fix or justify in `SUPPRESSIONS.md`.

**Wave T4 — Annotation completeness.** Enable ruff `ANN` rule set. Annotate the ~22 unannotated `core/` functions plus rest of public API. `core/` first, then domain packages, then scripts/tools last.

### Tier 4 — Other gates

**Wave Q1 — Darglint to zero.** 835 DAR violations. Largest single ratchet; will require either (a) fixing docstring/signature mismatches everywhere, or (b) tightening `darglint` config in waves of severity (DAR101 → DAR201 → DAR401 → …). Default plan: per-error-code sub-waves Q1a, Q1b, ... since 835 is unmanageable as a single PR.

**Wave Q2 — docstr-coverage ≥95%.** Raise `fail_under` in `.docstr.yaml` from 80 to 95. Add the missing module/class/init docstrings flagged in R4 fallout.

**Wave Q3 — Vulture to zero (confidence 60).** 88 findings. Either delete dead code or extend `scripts/vulture_whitelist.py` with a documented reason per entry.

**Wave Q4 — Radon cc=B and mi=A.** Tighten threshold past current C/B; refactor the one C901 hotspot.

**Wave Q5 — Bandit strict.** Move from default profile to `--severity-level low --confidence-level low`, fix or justify.

**Wave Q6 — Codespell / typos.** Not currently configured; add it as a new pre-commit hook, drive to zero on first pass. Minor, slot in opportunistically.

### Tier 5 — Lock the gate

**Wave L1 — Pre-commit `fail_fast = false` + all hooks `always_run`.** Make sure no hook silently skips on partial commits.

**Wave L2 — `just ci` is the canonical gate.** Ensure `ruff check`, `ruff format --check`, `ty check --error-on-warning`, `lint-imports`, `interrogate`, `darglint`, `bandit -ll`, `vulture`, `radon cc -na`, all custom gates (`api_style_gate.py`, `fp_purity_gate.py`) are wired. Fail loudly if any tool is configured-but-not-invoked. **CI is local-only via `just ci` — no GitHub Actions** (per project preference).

**Wave L3 — Ratchet enforcement.** Add a `scripts/ratchet_check.py` that reads `docs/ratchet/current.json` (counts per tool, expected zero after this plan) and fails `just ci` if any number regresses. Cheap insurance against backsliding once the ratchet has no slack left.

---

## Bookkeeping

- `docs/ratchet/PLAN.md` — this file. Updated only when scope changes.
- `docs/ratchet/PROGRESS.md` — append-only log of completed waves with commit SHA, before/after numbers.
- `docs/ratchet/baselines/<wave-id>.md` — frozen baseline at start of each wave.
- `docs/ratchet/SUPPRESSIONS.md` — every `# noqa`, `# type: ignore`, vulture whitelist entry added during the ratchet, with justification and the wave id that introduced it. Reviewed before each Tier-end review.
- `docs/ratchet/current.json` — machine-readable counts for `ratchet_check.py` (created by Wave L4).

## Out of scope

- Pytest / coverage / mutmut work (parallel testing agent).
- Documentation rewrites beyond docstring stubs needed by R4 / Q2.
- Public API changes that aren't already required by an existing gate (`api_style_gate.py`, `fp_purity_gate.py` already hold at zero — keep them there).
- Performance work, dependency upgrades, repo restructuring.

## Order of operations once approved

1. Wait for testing agent to land its work.
2. Rebase `branch1` onto whatever testing agent produced; re-snapshot baseline.
3. Begin Wave R0.
