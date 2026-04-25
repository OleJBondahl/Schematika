# Wave C0c baseline — `_rotate_path_d` rewrite atop `core/svg_path`

Branch base: `branch1` @ `0834ab5` (post-C0b).
Wave branch: `complexity/C0c` in worktree `.worktrees/complexity/C0c`.

## State at start

`docs/ratchet/baseline.toml` `[complexity]`:
```
max_complexity   = 22
max_args         = 16
max_branches     = 22
max_statements   = 69
max_returns      =  5
```

`pyproject.toml` `[tool.ruff.lint.pylint]`: `max-args = 16`, `max-branches = 22`, `max-statements = 70`, `max-returns = 6`.

C0b shipped `core/svg_path.py` with the `PathCommand` ADT + `parse` / `serialize` / `translate_command`. Tests 1920, core coverage 94%, svg_path module 100%.

`_rotate_path_d` at `src/schematika/core/transform.py:260` is unchanged from before C0a/C0b — still a 70-line state machine. Per `metrics_snapshot.py`, this function is the `max_statements = 69` peak holder (closely followed by `_phase2_register_connections = 22 max_branches`). Driving its statement count down is what unlocks the threshold drop.

## Wave scope

Two changes in `core/svg_path.py` + one rewrite in `core/transform.py`. Same shape as C0b; this wave reuses C0b's `parse` and `serialize`.

### Add: `core/svg_path.py` — `rotate_commands(commands, angle_deg, center) -> tuple[PathCommand, ...]`

**This wave's primary deliverable.** A pure function that takes parsed commands and rotates absolute coordinates around `center`. Stateful internally (tracks running `last_x`, `last_y` for H/V flattening) but pure to the caller.

```python
@deal.pure
def rotate_commands(
    commands: Iterable[PathCommand],
    angle_deg: float,
    center: Point,
) -> tuple[PathCommand, ...]:
    """Rotate absolute coords; H/V flatten to L; relatives pass through."""
    ...
```

Behaviour requirements (matching the existing `_rotate_path_d`, byte-identical for canonical inputs):

- `Move(x, y)`, `Line(x, y)`, `Tangent(x, y)` → rotate `(x, y)` around `center`. Update `last_x = x, last_y = y` (PRE-rotation values — matches old code).
- `HLine(x)` → flatten to `Line(rotate(x, last_y))`. Update `last_x = x` (pre-rot).
- `VLine(y)` → flatten to `Line(rotate(last_x, y))`. Update `last_y = y` (pre-rot).
- `Curve(x1, y1, x2, y2, x, y)` → rotate all three pairs around `center`. Update `last_x, last_y` to the **endpoint** `(x, y)` (pre-rot).
- `Smooth(x2, y2, x, y)`, `Quad(x1, y1, x, y)` → rotate all pairs. Update `last_x, last_y` to endpoint pre-rot.
- `Close()`, `PassThrough()` → unchanged. Don't touch `last_x` / `last_y` (matches old code, which doesn't reset state on Z/z).

Imports: must use `core.geometry.Point` for `center`. Use `math.radians`/`math.cos`/`math.sin` for rotation (or import `rotate_point` from `core.transform` if it doesn't create a cycle — verify with import-linter).

Internal structure: a `_rotate_one(cmd, rot_fn, last_x, last_y) -> tuple[PathCommand, float, float]` helper is acceptable (returns `(new_cmd, new_last_x, new_last_y)`), or inline the per-command logic. Pick whichever keeps `rotate_commands` ≤ 30 statements and `_rotate_one` ≤ 30 statements. **Match arms with single return per arm IS allowed inside `_rotate_one`** — it's a pure helper, the spec convention is to suppress PLR0911 only when the noqa would require justification *inside* the wave (which it does NOT here, because `# ty: ignore`-style match dispatch is acceptable per the C0a/C0b precedent — but prefer the `result` variable single-return pattern when it's not awkward).

### Rewrite: `src/schematika/core/transform.py:260` `_rotate_path_d`

Replace the 70-line state machine with:

```python
@deal.pure
def _rotate_path_d(d: str, angle_deg: float, center: Point) -> str:
    """H/V become L after rotation; relative commands pass through."""
    return serialize(rotate_commands(parse(d), angle_deg, center))
```

(Top-of-file import or inline import — pick whichever doesn't break import-linter.)

## Done condition

- `core/svg_path.py` has a new `rotate_commands` function, `@deal.pure`, fp-purity-gate green.
- `_rotate_path_d` body ≤ 5 lines (excluding docstring).
- `_rotate_path_d` is byte-identical to `branch1` for the canonical test inputs in `tests/unit/test_transform_path_d.py` (the existing 50+ tests must pass UNCHANGED).
- `pyproject.toml` `[tool.ruff.lint.pylint] max-statements = 70 → 60`. Update the comment block (cite this wave by ID).
- `docs/ratchet/baseline.toml` `[complexity] max_statements = <new peak>` (must be ≤ 60). Implementer reports actual peak.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1920 (no regression). Adding new tests pushes it up; record actual.
- `uv run pytest --cov=src/schematika/core` core TOTAL ≥ 94% (current floor; aim ≥ 98% on `svg_path.py` since `rotate_commands` is added there).
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps.
- `uv run pre-commit run --all-files` → exit 0.
- `uv run python scripts/ratchet_check.py` → exit 0; `complexity.max_statements` cell reports the new peak.

## Test strategy

Add to `tests/unit/core/test_svg_path.py` (extending the C0b-introduced file):

- **Per-command rotation table** (`pytest.mark.parametrize`): for each canonical input `(d_string, angle, center, expected_output)`, assert `serialize(rotate_commands(parse(d_string), angle, center)) == expected_output` (or comparable dirty_equals comparison if floating-point output drifts). Cover M, L, H→L, V→L, C, S, Q, T, Z (preserved), z (preserved), mixed.
- **Hypothesis: rotate by 0° is identity** — `serialize(rotate_commands(parse(d), 0, center)) ≈ d` for canonical absolute paths (use `dirty_equals.IsApprox(delta=1e-9)`).
- **Hypothesis: 4×90° rotations cancel** — `rotate_commands ∘ ... ∘ rotate_commands` (4 times by 90°) ≈ identity. Already exists for `_rotate_path_d` in `test_transform_path_d.py`; add the equivalent property at the `rotate_commands` level.
- **H/V flatten test**: explicit `assert "H" not in letters_of(rotate_commands(parse("M 0 0 H 5"), 90, origin))` and same for V; `"L"` should be present.
- **last_x/last_y propagation**: `M 3 4 H 7` rotated 180° → `M -3 -4 L -7 -4` (per the existing `test_h_uses_running_last_y` test for `_rotate_path_d`).

The existing `tests/unit/test_transform_path_d.py` tests `_rotate_path_d` directly and is the regression net — DO NOT modify that file. After C0c, all those tests must continue to pass byte-identical.

## Out of scope

- Changing `_rotate_path_d`'s signature or any caller (the singledispatch `@rotate.register` for `Path` at `core/transform.py:254` stays the same).
- Adding new public API to `core/svg_path.py` beyond `rotate_commands` (no `rotate_command` per-command primitive — the fold is internal).
- Touching `_translate_path_d`, `translate`, `translate_command`, or any C0b-introduced code other than adding `rotate_commands`.
- Refactoring the existing `_rotate_path_d` tests (they're the regression net).
- Updating `docs/API_STYLE.md`.

## Notes for the implementer

- The `dirty_equals.IsApprox` API is `IsApprox(approx, *, delta=None)` — NOT `rel=`. Use `delta=1e-9` for absolute tolerance (matches C0b precedent and the existing tests' `math.isclose(..., abs_tol=1e-9)` semantics).
- Verify byte-identity with the existing `_rotate_path_d` tests BEFORE running the full ratchet. Run `cd .worktrees/complexity/C0c && uv run pytest tests/unit/test_transform_path_d.py -v` and check every test passes unmodified.
- `Close` and `PassThrough` are no-ops in `rotate_commands`. Don't track them in `last_x`/`last_y` — that matches the original behaviour of not resetting state on Z/z.
- For PassThrough: don't update last_x/last_y from PassThrough(token) — matches old "lowercase passes through unchanged, position state untouched" behaviour.
- The existing `_rotate_path_d` has a `_rot()` inner closure — the new `rotate_commands` can do the same OR factor `_rot` out as a top-level `@deal.pure` helper at module scope. Inner closure is fine; if pulled out, name it `_rotate_xy` (NOT `_rot` — avoid clashing with existing `rotate_*` names in `core.transform`).
- The malformed-input case (orphan token in C/S/Q) is already handled by C0b's `parse` (emits `PassThrough` for letter + raw tokens). `rotate_commands` sees these as `PassThrough` and passes them through. No special-case logic needed — the C0b parser does the right thing.
- The `# ty: ignore[type-assertion-failure]` pattern is NOT needed here — there's no `assert_never` in `rotate_commands`. The match should cover all 10 PathCommand kinds (no `case _:` arm needed if ty proves exhaustiveness; if ty doesn't, use `case _:` with `raise TypeError(...)` rather than `assert_never`).
