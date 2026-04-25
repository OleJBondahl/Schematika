# Wave C1-pre baseline — `RealizedComponent` frozen dataclass intro

Branch base: `branch1` @ `9c2e8ab` (post-C0 tier).
Wave branch: `complexity/C1-pre` in worktree `.worktrees/complexity/C1-pre`.

## State at start

`docs/ratchet/baseline.toml`:
```
[complexity]
max_complexity   = 22  ← held by _phase4_render_graphics; drops in C1d
max_args         = 16
max_branches     = 22
max_statements   = 69
max_returns      =  0
[pytest]
min_passing               = 1951
min_coverage_percent      =   90
min_core_coverage_percent =   94
```

11 C901 violators remain in `src/`:
- `core/svg_path.py`: parse, serialize, rotate_commands (inherent match dispatch — accepted)
- `electrical/builder.py`: add_terminal, add_symbol, add_spdt, build (tier C2)
- `electrical/builder_phases.py`: `_phase[1234]_*` (tier C1 — this wave + C1a-d-e)

## Wave scope

**No behavioural change. No phase function modified.** Just introduce the typed model that C1a-d will migrate to.

### Add: `electrical/builder_models.py` — `RealizedComponent` dataclass

Today, `realized_components` in `builder_phases.py` is `list[dict[str, Any]]` with these keys:

- `"spec"` — `ComponentSpec` (the input declaration; immutable)
- `"tag"` — `str` (instance identifier, allocated in phase 1)
- `"pins"` — `list[str]` (resolved pin labels, allocated in phase 1)
- `"y"` — `float` (placement Y, refined in phase 3)
- `"symbol"` — `Symbol` (placed symbol, populated in phase 3, absent before)

The new dataclass:

```python
@dataclass(frozen=True, slots=True)
class RealizedComponent:
    """An in-flight build artifact tracked across the four-phase pipeline.

    Phase 1 populates spec/tag/pins/y; phase 3 places the Symbol and
    refines Y (via dataclasses.replace).
    """

    spec: ComponentSpec
    tag: str
    pins: tuple[str, ...]              # tuple, not list — frozen-friendly
    y: float
    symbol: Symbol | None = None        # populated by phase 3
```

Place it in `src/schematika/electrical/builder_models.py` directly after `ComponentSpec`. Add `Symbol` to the `TYPE_CHECKING` block at the top of the file (don't import at runtime — `Symbol` lives in `electrical.model.core` and importing it at module top would create a cycle).

### Add: dict↔dataclass converters

Two helpers, also in `builder_models.py`:

```python
@deal.pure
def realized_from_dict(d: dict[str, Any]) -> RealizedComponent:
    """Bridge: convert a phase-pipeline dict to a RealizedComponent. Used during C1a-d migration."""
    return RealizedComponent(
        spec=d["spec"],
        tag=d["tag"],
        pins=tuple(d["pins"]),
        y=d["y"],
        symbol=d.get("symbol"),
    )


@deal.pure
def realized_to_dict(rc: RealizedComponent) -> dict[str, Any]:
    """Bridge: convert RealizedComponent back to dict for unmigrated phases."""
    d: dict[str, Any] = {
        "spec": rc.spec,
        "tag": rc.tag,
        "pins": list(rc.pins),  # list because phases mutate
        "y": rc.y,
    }
    if rc.symbol is not None:
        d["symbol"] = rc.symbol
    return d
```

(`@deal.pure` is fine here because pure functions; if `deal` isn't already imported in `builder_models.py`, add it.)

### NO changes to `builder_phases.py` in this wave

The phase functions still operate on `list[dict[str, Any]]`. The new dataclass is unused at runtime — but it's exercised by tests (next section), so vulture won't complain.

If vulture DOES complain about `RealizedComponent`, `realized_from_dict`, or `realized_to_dict` despite the tests, add `# noqa: ERA001` (or whichever rule fires) with a comment "introduced in C1-pre for the C1a-d migration."

## Done condition

- New file: `src/schematika/electrical/builder_models.py` updated with `RealizedComponent` + 2 converter helpers. NOTHING ELSE in src/ changes.
- New tests in `tests/unit/electrical/test_realized_component.py` (create the dir if it doesn't exist) covering:
  - Construction from valid args (default `symbol=None`).
  - `dataclasses.replace(rc, y=...)` produces a new instance with updated y.
  - `frozen=True` enforcement: `rc.y = 5.0` raises `dataclasses.FrozenInstanceError`.
  - Round-trip: `realized_to_dict(realized_from_dict(d)) == d` for a representative dict (with and without `symbol`).
  - `realized_from_dict({"spec": ..., "tag": "T1", "pins": ["1", "2"], "y": 0.0})` (no symbol) produces `RealizedComponent(symbol=None)`.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1951 (will go up by ~5 with the new tests; record actual).
- `uv run pytest --cov=src/schematika/core` core TOTAL ≥ 94%.
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps. The 3 new symbols (`RealizedComponent`, `realized_from_dict`, `realized_to_dict`) are tier-3 — NOT in `electrical.__all__` or any other audited package's `__all__`. Don't add Examples doctests.
- `uv run python scripts/fp_purity_gate.py` → 0 violations (the converters are `@deal.pure`).
- `uv run pre-commit run --all-files` → exit 0.
- `uv run python scripts/ratchet_check.py` → exit 0; all 12 metrics still green; complexity peaks UNCHANGED.

## Test strategy

5-7 small unit tests in `tests/unit/electrical/test_realized_component.py`:

```python
import pytest
from dataclasses import FrozenInstanceError, replace
from schematika.electrical.builder_models import (
    ComponentSpec,
    RealizedComponent,
    realized_from_dict,
    realized_to_dict,
)


def _spec():
    return ComponentSpec(func=None, kind="terminal")  # adjust to whatever ComponentSpec accepts


def test_construct_with_defaults():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1", "2"), y=10.0)
    assert rc.symbol is None


def test_replace_updates_y():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1",), y=0.0)
    rc2 = replace(rc, y=5.0)
    assert rc2.y == 5.0
    assert rc.y == 0.0  # original untouched


def test_frozen_blocks_mutation():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1",), y=0.0)
    with pytest.raises(FrozenInstanceError):
        rc.y = 5.0


def test_roundtrip_without_symbol():
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1", "2"), y=10.0)
    rt = realized_from_dict(realized_to_dict(rc))
    assert rt == rc


def test_roundtrip_with_symbol():
    sym = ...  # construct or import a Symbol fixture
    rc = RealizedComponent(spec=_spec(), tag="T1", pins=("1",), y=0.0, symbol=sym)
    rt = realized_from_dict(realized_to_dict(rc))
    assert rt == rc


def test_from_dict_omits_symbol_when_absent():
    d = {"spec": _spec(), "tag": "T1", "pins": ["1", "2"], "y": 0.0}
    rc = realized_from_dict(d)
    assert rc.symbol is None
    assert rc.pins == ("1", "2")  # converted to tuple
```

Adapt the `_spec()` constructor to whatever `ComponentSpec` actually accepts — read its definition first. Same for the `Symbol` fixture in `test_roundtrip_with_symbol` (use whatever's already constructible; if Symbol needs many args, extract a minimal builder).

Hypothesis is overkill for this wave; skip.

## Out of scope

- Touching `builder_phases.py` or any `_phase*` function.
- Touching `builder.py` (`CircuitBuilder` and its `add_*`/`build` methods — those are tier C2).
- Adding `RealizedComponent` to any `__all__`.
- Threshold drops on any complexity rule.
- Updating `docs/API_STYLE.md`.

## Notes for the implementer

- `Symbol` import: in `builder_models.py`, `Symbol` should be in the `TYPE_CHECKING` block — don't import at runtime to avoid circular imports. Use a forward reference (`"Symbol"`) or `from __future__ import annotations` (already at the top of the file).
- `ComponentSpec` already has `pins: list[str] | tuple[str, ...] | None` — meaning callers can pass either. `RealizedComponent.pins` is strictly `tuple[str, ...]` (frozen-friendly). The converter normalizes via `tuple(d["pins"])`.
- The `Symbol | None = None` default is fine on a frozen+slots dataclass.
- Don't introduce a `RealizedComponent.from_dict` classmethod and `to_dict` method — the spec uses standalone functions because they're tier-3 and convention here is module-level pure helpers, not methods on data types.
- vulture might complain about the new symbols since they're not yet imported by any production code. If so, the noqa is acceptable IF the comment cites C1a-d as the consumer. But TRY first to satisfy vulture by ensuring the test file imports them all (which it should).
