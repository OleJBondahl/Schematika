# Wave C0b baseline — `_translate_path_d` → `core/svg_path` (PathCommand ADT)

Branch base: `branch1` @ `2dace97` (post-C0a).
Wave branch: `complexity/C0b` in worktree `.worktrees/complexity/C0b`.

## State at start

`docs/ratchet/baseline.toml` `[complexity]`:
```
max_complexity   = 22
max_args         = 16
max_branches     = 22
max_statements   = 69
max_returns      =  5   <- driven down in C0a
```

`pyproject.toml` `[tool.ruff.lint.pylint] max-returns = 6` (post-C0a), `max-branches = 22`, `max-statements = 70`.

C901/PLR0912 status of the two SVG path state machines (read at default `max-complexity = 10`, `max-branches = 12`):

- `src/schematika/core/transform.py:102` `_translate_path_d` — state machine over 7 SVG command groups (M/L/T, H, V, C/S/Q, z/Z, fall-through). One nested `for _ in range(pair_count)` for the C/S/Q arm. ~10 branches, ~30 statements.
- `src/schematika/core/transform.py:260` `_rotate_path_d` — same skeleton plus `last_x`/`last_y` running state and H/V → L flatten. **C0c will rewrite this atop the C0b foundation; do NOT touch it in this wave** (touching it pre-empts the C0c spec and risks merge conflicts).

`pytest`: 1887 passed (post-C0a). Repo cov 89%, core cov 93%.

## Wave scope

Single new module + one call-site rewrite, no public API change.

### New module: `src/schematika/core/svg_path.py`

Pure (every top-level function `@deal.pure`; module is in `core/`). Defines a tagged-union ADT for SVG path commands plus parse / serialize / per-command-translate primitives.

```python
# Sketch — implementer chooses exact field names, but the union shape is fixed.

@dataclass(frozen=True, slots=True)
class Move:    x: float; y: float
class Line:    x: float; y: float
class HLine:   x: float                     # absolute horizontal
class VLine:   y: float                     # absolute vertical
class Curve:   x1: float; y1: float; x2: float; y2: float; x: float; y: float  # C
class Smooth:  x2: float; y2: float; x: float; y: float                         # S
class Quad:    x1: float; y1: float; x: float; y: float                         # Q
class Tangent: x: float; y: float                                               # T
class Close: ...                                                                # Z / z (preserve case)
class PassThrough: token: str                                                   # any non-absolute token

PathCommand = Move | Line | HLine | VLine | Curve | Smooth | Quad | Tangent | Close | PassThrough
```

Required functions (all `@deal.pure`, all return frozen / immutable values):

- `parse(d: str) -> tuple[PathCommand, ...]` — tokenize via existing `tokenize_path_d` (re-import from `core.transform` or move it here in this wave; pick one and stick to it), then fold tokens into typed commands. Unknown / lowercase commands wrap their tokens in `PassThrough` so they round-trip unchanged. `Close` records the original case (`'Z'` vs `'z'`) so `serialize` can reproduce it.
- `serialize(commands: Iterable[PathCommand]) -> str` — inverse of `parse`. Same canonical " " separator the existing code uses (`" ".join(result)`).
- `translate_command(cmd: PathCommand, dx: float, dy: float) -> PathCommand` — single-arm-per-command match. `PassThrough` and `Close` return self.

The wave does NOT introduce a `rotate_command` — that's C0c's job. Adding it now would couple the spec.

### Rewrite: `src/schematika/core/transform.py:102` `_translate_path_d`

Replace the 30-line state machine with a one-liner:

```python
@deal.pure
def _translate_path_d(d: str, dx: float, dy: float) -> str:
    """Shifts absolute SVG path coords; relative (lowercase) commands pass through."""
    from schematika.core.svg_path import parse, serialize, translate_command
    return serialize(translate_command(c, dx, dy) for c in parse(d))
```

(Top-of-file import is fine too — pick whichever doesn't break import-linter / cycle checks.)

### `tokenize_path_d` location

Currently lives in `src/schematika/core/transform.py:27` as `@deal.pure`. The implementer's call: either move it into `core/svg_path` (cleaner) or import from transform. **Recommendation: move it.** It's a path-tokenizer, not a transform. If moved, leave a re-export shim (`from schematika.core.svg_path import tokenize_path_d`) in `core/transform.py` so `tests/unit/test_transform_path_d.py` still imports it from the old location without modification.

## Done condition

- New file `src/schematika/core/svg_path.py` exists, `@deal.pure` on every top-level function, fp-purity-gate green.
- `src/schematika/core/transform.py` `_translate_path_d` is ≤ 5 lines of body (excluding docstring).
- `_rotate_path_d` body **unchanged** in this wave (verify via `git diff branch1..HEAD -- src/schematika/core/transform.py` — only `_translate_path_d` and possibly `tokenize_path_d` should change in this file).
- `uv run ruff check src --select C901,PLR0912 --config 'lint.mccabe.max-complexity=8' --config 'lint.pylint.max-branches=10'` → no NEW violations beyond the pre-wave set (`_rotate_path_d` survives this wave; everything else stays the same or improves).
- `pyproject.toml` `[tool.ruff.lint.pylint] max-branches = 22 → 20`. Document the new threshold in the comment block (cite this wave by ID).
- `docs/ratchet/baseline.toml` `[complexity] max_branches = <new peak>` (must be ≤ 20 if dropping the threshold). Implementer reports the actual new peak.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1887 passed (no regression). Adding the new module's tests will push this UP; record actual count.
- `uv run pytest --cov=src/schematika/core --cov-report=term-missing` core TOTAL ≥ 93% (the floor; aim for ≥ 95% on the new svg_path module).
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps. The new functions in `core/svg_path.py` are tier-3 (private — they're imported, not in `__all__`); a one-line docstring is fine. Do **not** add Examples doctests on tier-3.
- `uv run pre-commit run --all-files` → exit 0 in worktree.
- `uv run python scripts/ratchet_check.py` → exit 0; `complexity.max_branches` cell reports the new peak (or `complexity.max_complexity` if branches doesn't budge).

## Test strategy

Add `tests/unit/core/test_svg_path.py` (new file). Coverage:

- **Per-command parse round-trip** (`pytest.mark.parametrize`, one row per command type): for each canonical input string (`"M 1 2"`, `"L 3 4"`, `"H 5"`, `"V 6"`, `"C 1 2 3 4 5 6"`, `"S 1 2 3 4"`, `"Q 1 2 3 4"`, `"T 1 2"`, `"Z"`, `"z"`, `"l 1 2"` (relative passes through), `"M 1,2"` (comma separator)), assert `serialize(parse(s)) == s_canonical` (allow tokenizer normalization — e.g. trailing/leading space differences are fine; numeric formatting differences are fine if the parsed command sequence matches).
- **Hypothesis property**: `serialize(parse(d))` parses to the same command sequence as `parse(d)` (round-trip stability). Generator: `hypothesis.strategies.from_type(PathCommand)` if you can; otherwise hand-roll a strategy over the 10 command types.
- **Hypothesis property**: `translate_command(translate_command(c, dx, dy), -dx, -dy) ≈ c` for every non-`PassThrough` command. Use `dirty_equals.IsApprox(rel=1e-9)` for float comparisons (matches the C0a precedent).
- **PassThrough round-trip**: a `PassThrough("l")` followed by `PassThrough("5")` `PassThrough("5")` serializes back to `"l 5 5"`.
- **Equivalence with the old `_translate_path_d`**: parametrized table that runs the legacy strings (M, L, H, V, C, S, Q, T, Z, mixed, comma-separated, no-space, scientific notation) through both the old and new code paths and asserts equal output. Since `_translate_path_d` is the new code path, "old" must be a frozen reference table — write the expected outputs by hand from a known-good run on `branch1` (use `git show branch1:src/schematika/core/transform.py` to reproduce, or just snapshot the current outputs before refactoring).

The existing `tests/unit/test_transform_path_d.py` tests `_rotate_path_d` only and stays untouched in this wave. The existing `tests/unit/test_transform.py` characterisation tests for `translate` (which exercises the `Path` arm via `_translate_path_d`) must continue to pass — that's the regression net.

## Out of scope

- Touching `_rotate_path_d` or any function other than `_translate_path_d` and (optionally) `tokenize_path_d`.
- Adding a `rotate_command` to `core/svg_path` (C0c's job).
- Changing the `_translate_path_d` signature or the `Path` dataclass.
- Updating `docs/API_STYLE.md`.
- Optimizing for performance (parse → serialize round-trip is fine even if a few % slower than the old state machine; correctness > microbenchmark).
- Public-API changes — `core/svg_path` symbols are NOT added to any `__all__`.

## Notes for the implementer

- `tokenize_path_d` is already `@deal.pure` — preserve that.
- `Close` must distinguish `'Z'` vs `'z'` because the existing test `test_lowercase_z_preserved` (in `test_transform_path_d.py`, not your responsibility but inherited contract) asserts case is preserved through `_rotate_path_d`. Apply the same discipline to `_translate_path_d` — even though no test currently asserts it, do the right thing.
- The "C/S/Q can be interrupted by an unexpected letter mid-pair" defensive case in the existing code (the `else: result.append(tokens[i]); i += 1; break` block) must be preserved. Translate it to: parser emits a `PassThrough` for the orphan token and stops collecting that arm; serialize still round-trips.
- Whether `parse` returns a `tuple` or a generator is up to you. Tuple is safer (re-iterable; matches frozen-dataclass spirit); generator is more memory-efficient. Tuple unless you have a reason.
- Don't `assert_never` in `core/svg_path` — the union is closed, but a `case _:` arm in the per-command match should `raise TypeError(f"unhandled PathCommand: {type(cmd).__name__}")` if the implementer is paranoid, OR be omitted entirely if ty proves exhaustiveness. Don't add `assert_never` here — it imports from typing and the cost > benefit for this small module.
