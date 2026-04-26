# Wave C2a baseline — `add_terminal` 16 args → ≤ 5 args via option bundles

Branch base: `branch1` @ `889db01` (post-C1e).
Wave branch: `complexity/C2a` in worktree `.worktrees/complexity/C2a`.

## State at start

`CircuitBuilder.add_terminal` at `src/schematika/electrical/builder.py:94` is the **most parameter-rich public method** in the repo: 16 keyword-only kwargs plus `**kwargs` passthrough plus `tm_id` positional. Pre-`max-args=16` ruff threshold accommodates exactly this method.

### Current signature

```python
def add_terminal(
    self,
    tm_id: "str | Terminal",
    /,
    *,
    poles: int = 1,
    pins: list[str] | tuple[str, ...] | None = None,
    relative_to: "ComponentRef | PortRef | None" = None,
    position: "Position" = "below",
    connect_from_previous: bool = True,
    spacing: float | None = None,
    pin_prefixes: tuple[str, ...] | None = None,
    label_pos: "LabelPosition | None" = None,
    pin_label_pos: "LabelPosition | None" = None,
    logical_name: str | None = None,
    x_offset: float = 0.0,
    connect_to_next: bool = True,
    connection_side: "Side | None" = None,
    bridge: BridgeMode = BridgeMode.NONE,
    wire_label: str | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> "ComponentRef":
```

### Target signature (post-C2a)

```python
def add_terminal(
    self,
    tm_id: "str | Terminal",
    /,
    *,
    config: TerminalConfig | None = None,
    placement: PlacementOptions | None = None,
    display: TerminalDisplayOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> "ComponentRef":
```

5 params (excluding `self`). Hits the plan's `≤ 5` target for C2a. **No `**kwargs`** — every consumer call site uses only the explicitly named kwargs (verified by grep across `../auxillary_cabinet_v3/src/`); the `**kwargs` passthrough is unused load.

## Wave scope

**This is a hard breaking change.** No back-compat shim, no `**legacy_kwargs` adapter, no `DeprecationWarning`. Single commit replaces the signature. The migration doc tells the consumer exactly what to change.

### New file: `src/schematika/core/options.py`

Four frozen dataclasses, all `@dataclass(frozen=True, slots=True, kw_only=True)`. **Tier-3 docstrings** — single-line WHY, no Args/Returns blocks (core/ is never tier-1 per `api_docs_audit.py:PACKAGES`).

```python
"""Frozen option-bundle dataclasses for CircuitBuilder.add_* / build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.electrical.builder_models import BridgeMode, ComponentRef, PortRef
    from schematika.electrical.model.constants import LabelPosition, Position, Side


@dataclass(frozen=True, slots=True, kw_only=True)
class PlacementOptions:
    """Where a new component sits relative to the chain head or another component."""

    relative_to: ComponentRef | PortRef | None = None
    position: Position = "below"
    spacing: float | None = None
    x_offset: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalDisplayOptions:
    """Label-position knobs for a terminal's text labels."""

    label_pos: LabelPosition | None = None
    pin_label_pos: LabelPosition | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectionOptions:
    """Chain-wiring knobs: previous/next, side, bridge, optional wire label."""

    connect_from_previous: bool = True
    connect_to_next: bool = True
    connection_side: Side | None = None
    bridge: "BridgeMode | None" = None  # None means "use BridgeMode.NONE"
    wire_label: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalConfig:
    """Pin layout + logical mapping for a Terminal."""

    poles: int = 1
    pins: tuple[str, ...] | None = None
    pin_prefixes: tuple[str, ...] | None = None
    logical_name: str | None = None
```

### Defaults policy

When a bundle is `None` (caller did not pass it), the body uses the bundle's default-constructed instance: `placement = placement or PlacementOptions()`. This is the equivalent of the old "default kwargs" — no behaviour change.

For `ConnectionOptions.bridge`, the field default is `None` rather than `BridgeMode.NONE` because importing the enum at module top would create a cycle (`core/options.py` → `electrical/builder_models.py` → ... → `core`). The body unpacks with `bridge=connection.bridge or BridgeMode.NONE` — semantically identical, no observable behaviour change. Document this in the bundle's class docstring.

### Why a fourth bundle (`TerminalConfig`)

The plan spells out 3 bundles (PlacementOptions, TerminalDisplayOptions, ConnectionOptions) covering 11 of the 16 kwargs. The remaining 5 (`poles`, `pins`, `pin_prefixes`, `logical_name`, plus the implicit `tm_id` positional) need somewhere to live to hit the **≤ 5** binding target. `tm_id` stays as the positional identity arg (per `api_style_gate.py:check_add_set_positional` — exactly one positional-only arg before `*`). The remaining 4 (poles, pins, pin_prefixes, logical_name) form a coherent "pin layout + logical mapping" group — that is `TerminalConfig`.

### Why drop `pins: list[str] | tuple[str, ...]` to `pins: tuple[str, ...]`

Frozen dataclass field. List would be a footgun (mutable, breaks `__hash__`). Migration is mechanical: `pins=["a", "b"]` → `pins=("a", "b")`. Document in migration doc.

### Body changes in `add_terminal`

The function body unpacks each bundle into local variables, then runs the existing flow. No behaviour change. The unpacking is a 4-line preamble:

```python
def add_terminal(
    self,
    tm_id: "str | Terminal",
    /,
    *,
    config: TerminalConfig | None = None,
    placement: PlacementOptions | None = None,
    display: TerminalDisplayOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> "ComponentRef":
    """<tier-1 docstring — see below>"""
    self._check_not_frozen()
    cfg = config or TerminalConfig()
    plc = placement or PlacementOptions()
    dsp = display or TerminalDisplayOptions()
    con = connection or ConnectionOptions()

    if cfg.logical_name:
        self._spec.terminal_map[cfg.logical_name] = tm_id

    # ... same code as before, but reading from cfg.poles, plc.relative_to,
    # dsp.label_pos, con.connect_from_previous, etc.
```

### Tier-1 docstring rewrite (mandatory)

`CircuitBuilder` is in `schematika.electrical.__all__`, so `add_terminal` is tier-1. The new docstring is full Google with runnable doctest:

```python
def add_terminal(self, tm_id, /, *, config=None, placement=None, display=None, connection=None):
    """Register a terminal in the chain; freezes nothing.

    Args:
        tm_id: Terminal identity — either a ``str`` or a :class:`Terminal`. Used as the
            symbol-factory's ``tm_id`` kwarg and as the chain key.
        config: Pin layout + logical name. ``None`` means single-pole, no pins, no
            mapping. See :class:`TerminalConfig`.
        placement: Where to place this terminal. ``None`` means below the previous
            chain head with default spacing. See :class:`PlacementOptions`.
        display: Label-position knobs. ``None`` means use the symbol-factory defaults.
            See :class:`TerminalDisplayOptions`.
        connection: Chain-wiring knobs. ``None`` means auto-connect from previous and to
            next. See :class:`ConnectionOptions`.

    Returns:
        ``ComponentRef`` to this terminal — usable as ``relative_to`` for subsequent
        components and as a source/target in :meth:`connect`.

    Raises:
        RuntimeError: If the builder has been frozen by :meth:`build`.

    Examples:
        >>> from schematika.electrical import CircuitBuilder, create_initial_state
        >>> from schematika.core.options import PlacementOptions, TerminalConfig
        >>> b = CircuitBuilder(state=create_initial_state())
        >>> ref = b.add_terminal("X1", config=TerminalConfig(poles=2, pins=("L", "N")))
        >>> ref._index
        0
    """
```

The doctest runs via `uv run pytest --doctest-modules src/`. **It MUST pass before commit.** The dummy `Terminal` import in the existing docstring's example resolves at runtime — the new doctest stays minimal (no `Terminal` lookup) so it doesn't depend on the consumer-side enum.

## Done condition

- `add_terminal` parameter count **= 5** (excluding `self`, including all keyword-only).
- `core/options.py` exists with the 4 dataclasses spelled out above.
- All 4 dataclasses have a tier-3 docstring (one-line WHY, no Args/Returns).
- `add_terminal` tier-1 docstring rewritten as above (Args/Returns/Raises/Examples).
- **No `**kwargs`** on `add_terminal`.
- **No back-compat shim** — single commit changes the signature.
- `uv run pytest --doctest-modules src/schematika/electrical/builder.py` → exit 0 (the new Examples doctest runs).
- `uv run python scripts/api_style_gate.py --strict` → exit 0 (rule 1 — exactly 1 positional-only — still satisfied via `tm_id`).
- `uv run python scripts/api_docs_audit.py --strict` → exit 0 (no new gaps; `CircuitBuilder` class docstring untouched).
- `uv run pytest --continue-on-collection-errors` → ≥ pre-wave passing count (**floor: 2018**, the post-C1e baseline).
- `uv run python scripts/ratchet_check.py` → exit 0 (no metric drops; `max_args` peak does not regress).
- `uv run pre-commit run --all-files` → exit 0.
- `docs/ratchet/migrations/C2a-consumer-migration.md` exists (see "Migration doc" below).
- `add_terminal` no longer in `uv run ruff check src --select PLR0913 --no-fix` output (had been the **sole holder** of the 16-arg peak; new arg count of 5 is well below ANY current threshold).
- All existing tests pass UNCHANGED — no test deletion, no test edits beyond construction-site updates (any test that called `add_terminal` with old kwargs is updated to the new bundle form).

## Migration doc

Create `docs/ratchet/migrations/C2a-consumer-migration.md` with the structure the plan mandates (decision 6 + plan §"Consumer-migration document"):

1. **Summary** — one paragraph: `add_terminal`'s 16 kwargs are bundled into 4 frozen dataclasses (`TerminalConfig`, `PlacementOptions`, `TerminalDisplayOptions`, `ConnectionOptions`) imported from `schematika.core.options`. `**kwargs` removed. Single hard breaking commit.
2. **Old → new mapping table** — for every old kwarg, the new bundle and field path:

   | Old kwarg | New |
   | --------- | --- |
   | `poles` | `config=TerminalConfig(poles=...)` |
   | `pins` | `config=TerminalConfig(pins=...)` (must be `tuple`, not `list`) |
   | `pin_prefixes` | `config=TerminalConfig(pin_prefixes=...)` |
   | `logical_name` | `config=TerminalConfig(logical_name=...)` |
   | `relative_to` | `placement=PlacementOptions(relative_to=...)` |
   | `position` | `placement=PlacementOptions(position=...)` |
   | `spacing` | `placement=PlacementOptions(spacing=...)` |
   | `x_offset` | `placement=PlacementOptions(x_offset=...)` |
   | `label_pos` | `display=TerminalDisplayOptions(label_pos=...)` |
   | `pin_label_pos` | `display=TerminalDisplayOptions(pin_label_pos=...)` |
   | `connect_from_previous` | `connection=ConnectionOptions(connect_from_previous=...)` |
   | `connect_to_next` | `connection=ConnectionOptions(connect_to_next=...)` |
   | `connection_side` | `connection=ConnectionOptions(connection_side=...)` |
   | `bridge` | `connection=ConnectionOptions(bridge=...)` |
   | `wire_label` | `connection=ConnectionOptions(wire_label=...)` |
   | `**kwargs` | **REMOVED.** No consumer call site uses passthrough kwargs (verified). If you somehow do, file a bug. |

3. **Call-site index.** Implementer greps `../auxillary_cabinet_v3/src/` (read-only) for `.add_terminal(` and lists every file:line. Format each as a before/after snippet pair. Spot-check examples (the implementer fills the full list):

   - `circuits/power_supply.py:106` — multi-kwarg form (`logical_name`, `poles`, `pin_prefixes`, `x_offset`, `spacing`, `label_pos`, `connect_to_next`)
   - `circuits/internal_distribution.py:67,72` — uses `**top_kwargs`/`**bot_kwargs` dict-spread; consumer must restructure to bundle dataclass kwargs (call out as the only non-mechanical migration in the file)
   - `circuits/plc_power.py:38` — bare call (no kwargs); migration is no-op for this call

4. **What to test after migration.** Smallest checklist: `cd ../auxillary_cabinet_v3 && uv run python src/main.py` (or the consumer's canonical entrypoint) — generates the cabinet diagram. Diff the resulting SVG against the pre-migration version (should be byte-identical because behaviour is preserved).

5. **Breakage note.** Explicit: "This is a breaking change. The consumer will not import or run until updated. There is no compatibility shim."

## Test strategy

Existing CircuitBuilder integration tests cover `add_terminal` through every realistic call shape. Update the tests' construction sites to use the bundles (mechanical edit). No new behaviour, no new test cases needed.

For the new `core/options.py` dataclasses, add `tests/unit/core/test_options.py`:

- Constructor smoke: each of the 4 dataclasses constructs with all defaults.
- `frozen=True` smoke: assigning to a field raises `dataclasses.FrozenInstanceError`.
- `slots=True` smoke: instances do not have `__dict__`.
- `kw_only=True` smoke: passing positional args raises `TypeError`.
- `bridge` field default check: `ConnectionOptions().bridge is None` (the cycle-avoidance pattern).
- One round-trip-with-`replace` test per dataclass to lock in dataclass semantics.

(These are 6 small parametrised tests over 4 dataclasses. ~24 test cases. Each passes in <1ms.)

## Out of scope

- Touching `add_symbol`, `add_spdt`, `add_reference`, `add_equipment`, `build_from_descriptors`, `_walk_loop`, `create_horizontal_layout` — those are C2b/c/d.
- Refactoring `_resolve_placement` to take `PlacementOptions` directly. (It currently takes the unbundled args. Body of `add_terminal` unpacks `placement` before calling `_resolve_placement`. C2b/c will share this pattern. A future wave can refactor `_resolve_placement` itself.)
- Touching `../auxillary_cabinet_v3/`. Migration doc only — per resolved decision 6.
- Dropping the `max-args` ruff threshold from 16. C2a is one method out of four — drop happens in C2d after all four are migrated.
- Renaming any existing API symbols.
- Touching the `CircuitBuilder` class docstring (the existing tier-1 class docstring is unchanged).

## Notes for the implementer

- **Model: sonnet** (per plan; touches public surface, breaking change, judgment matters).
- **First action: `uv sync --all-extras`.** Then read `src/schematika/electrical/builder.py:94-239` (the whole `add_terminal` body) and `src/schematika/electrical/builder.py:241-289` (`_resolve_placement`, which `add_terminal` calls).
- **Cycle-avoidance for `core/options.py`.** Domain types (`ComponentRef`, `PortRef`, `BridgeMode`, `Position`, `Side`, `LabelPosition`) are imported under `if TYPE_CHECKING:` only. At runtime, the dataclass fields are typed by string forward refs. This is the standard pattern in `core/` modules.
- **`bridge` field**: default `None` (NOT `BridgeMode.NONE`) for cycle reasons noted above. Body unpacks `bridge=con.bridge if con.bridge is not None else BridgeMode.NONE`.
- **Test edits**: `tests/unit/test_builder.py` and any other test that calls `add_terminal` with old kwargs must be updated. Use `git grep -n "add_terminal(" tests/` to find them all. Edit mechanically — same call shape, just bundled kwargs.
- **The doctest in the new `Examples:` block must run.** Verify with `uv run pytest --doctest-modules src/schematika/electrical/builder.py -v` before commit.
- **Don't add helpers**, don't extract intermediate variables for "readability" beyond the 4-line bundle-unpack preamble. The point of this wave is the signature change, not body reorganisation.
- **Tier-1 docstring on `add_terminal`**: required Args/Returns/Raises/Examples block (the audit script doesn't check methods directly, but the plan and CLAUDE.md tier-1 spec require it).
- **Tier-3 docstrings on the dataclasses**: one short line each. No Args/Returns block. Default-no-docstring is also fine for the dataclass `__init__` (which is auto-generated).
- **Migration doc**: write the call-site index by greping `../auxillary_cabinet_v3/src/circuits/` for `.add_terminal(` — there are ~30 call sites. Group by file. For each, write the before/after snippet. The doc lives at `docs/ratchet/migrations/C2a-consumer-migration.md`.
- **No new noqa**, no `# ty: ignore` additions. The dataclasses are pure data — should type-check cleanly.
- **Commit message**: `refactor(wave-C2a): add_terminal — bundle 16 kwargs into 4 frozen option dataclasses`. Then a separate commit for the migration doc: `docs(wave-C2a): consumer migration guide for add_terminal bundling`.
