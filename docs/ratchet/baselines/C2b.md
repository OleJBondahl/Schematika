# Wave C2b baseline — `add_symbol` 13 args → ≤ 4 args via option bundles

Branch base: `branch1` @ `c1b5247` (post-C2a).
Wave branch: `complexity/C2b` in worktree `.worktrees/complexity/C2b`.

## State at start

`CircuitBuilder.add_symbol` at `src/schematika/electrical/builder.py:291` has 13 keyword/positional-or-keyword args plus `**kwargs` factory passthrough. C2a established the option-bundle pattern (PlacementOptions, ConnectionOptions); C2b reuses both and adds one new bundle.

### Current signature

```python
def add_symbol(
    self,
    symbol_func: SymbolFactory,
    /,
    tag_prefix: str,
    poles: int = 1,
    pins: list[str] | tuple[str, ...] | None = None,
    relative_to: "ComponentRef | PortRef | None" = None,
    position: "Position" = "below",
    *,
    connect_from_previous: bool = True,
    spacing: float | None = None,
    x_offset: float = 0.0,
    y_increment: float | None = None,
    connect_to_next: bool = True,
    device: "InternalDevice | None" = None,
    wire_labels_above: list[str] | tuple[str, ...] | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> "ComponentRef":
```

### Target signature (post-C2b)

```python
def add_symbol(
    self,
    symbol_func: SymbolFactory,
    /,
    *,
    config: SymbolConfig,
    placement: PlacementOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> "ComponentRef":
```

4 params (excluding `self`). Hits the plan's `≤ 4` target. **No `**kwargs`** — symbol-factory passthrough kwargs move into `SymbolConfig.factory_kwargs`. **No `y_increment`** — the `spacing`/`y_increment` aliasing is removed; consumers use `PlacementOptions.spacing`.

## Wave scope

**Hard breaking change** — no back-compat shim, no DeprecationWarning. Single commit replaces the signature. Migration doc lists every consumer call site.

### Extend `src/schematika/core/options.py` (file already exists post-C2a)

Add ONE new dataclass (the others — `PlacementOptions`, `ConnectionOptions` — already exist and are reused as-is):

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolConfig:
    """Tag prefix + pin layout + device + wire labels + factory passthrough for a Symbol."""

    tag_prefix: str  # required
    poles: int = 1
    pins: tuple[str, ...] | None = None
    device: InternalDevice | None = None
    wire_labels_above: tuple[str, ...] | None = None
    factory_kwargs: Mapping[str, Any] | None = None
```

- `tag_prefix` is required (no default) — `SymbolConfig` must always be passed by the caller.
- `pins` and `wire_labels_above` are `tuple[str, ...] | None` — frozen-friendly. Lists are NOT accepted (migration tells consumers to switch).
- `factory_kwargs` is `Mapping[str, Any] | None` (use `from collections.abc import Mapping`) — optional bundle of opaque kwargs that get spread into the symbol-factory call. Most call sites don't need it. Used by e.g. `block(top_pins=..., bottom_pins=...)`.

`InternalDevice` and `Mapping` imports need TYPE_CHECKING-guarded for `InternalDevice` (domain type, follows existing pattern) and runtime for `Mapping` (stdlib, no cycle).

### Why `tag_prefix` collapsed into `SymbolConfig`

To hit `≤ 4` args, `tag_prefix` must move into a bundle (otherwise count is 5: `symbol_func`, `tag_prefix`, `config`, `placement`, `connection`). `tag_prefix` is conceptually part of the symbol's identity/configuration, so it lives in `SymbolConfig` as a required field. This makes `config=` always required at the call site.

### Why `**kwargs` collapsed into `SymbolConfig.factory_kwargs`

`**kwargs` was load-bearing for symbol factories that accept extra params (e.g. `block(top_pins=..., bottom_pins=...)`). Cannot be deleted; must be bundled. `factory_kwargs: Mapping[str, Any] | None = None` provides the same passthrough cleanly. Body unpacks: `kwargs_for_factory = dict(cfg.factory_kwargs) if cfg.factory_kwargs else {}`.

### Body changes in `add_symbol`

Pattern matches C2a — 3-line bundle-unpack preamble, then existing flow reading from locals:

```python
def add_symbol(
    self,
    symbol_func: SymbolFactory,
    /,
    *,
    config: SymbolConfig,
    placement: PlacementOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> "ComponentRef":
    """<tier-1 docstring — see below>"""
    self._check_not_frozen()
    plc = placement or PlacementOptions()
    con = connection or ConnectionOptions()

    # ... rest of body reads from config.tag_prefix, config.poles, ...,
    #     plc.relative_to, plc.position, ...,
    #     con.connect_from_previous, con.connect_to_next, ...
    # _resolve_placement is called with unpacked positional args (unchanged signature).
    # spec.kwargs is set from `dict(config.factory_kwargs) if config.factory_kwargs else {}`.
```

`_resolve_placement` signature is **unchanged** (deferred to a later wave) — `add_symbol` unpacks `placement.relative_to`, `placement.position`, etc. before calling.

### Tier-1 docstring rewrite (mandatory)

`add_symbol` is tier-1 (CircuitBuilder is in `schematika.electrical.__all__`). Rewrite per the C2a precedent:

```python
def add_symbol(self, symbol_func, /, *, config, placement=None, connection=None):
    """Register a symbol-factory-built component in the chain.

    Args:
        symbol_func: Factory callable producing a :class:`Symbol`. Receives ``tag``,
            optional ``poles``, optional ``pins``, plus any ``factory_kwargs``.
        config: Required tag/pin/device/wire-label/factory-kwargs bundle. See
            :class:`SymbolConfig`.
        placement: Where to place this component. ``None`` means below the previous
            chain head with default spacing. See :class:`PlacementOptions`.
        connection: Chain-wiring knobs. ``None`` means auto-connect from previous and
            to next. See :class:`ConnectionOptions`.

    Returns:
        ``ComponentRef`` to this symbol — usable as ``relative_to`` for subsequent
        components and as a source/target in :meth:`connect`.

    Raises:
        RuntimeError: If the builder has been frozen by :meth:`build`.

    Examples:
        >>> from schematika.electrical import CircuitBuilder, create_initial_state
        >>> from schematika.electrical.symbols.contacts import no_contact
        >>> from schematika.core.options import SymbolConfig
        >>> b = CircuitBuilder(state=create_initial_state())
        >>> ref = b.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K"))
        >>> ref._index
        0
    """
```

The doctest must run via `uv run pytest --doctest-modules src/schematika/electrical/builder.py`.

## Done condition

- `add_symbol` parameter count **= 4** (excluding `self`).
- `core/options.py` extended with `SymbolConfig`. Tier-3 single-line docstring.
- `add_symbol` tier-1 docstring rewritten as above.
- **No `**kwargs`** on `add_symbol`.
- **No `y_increment` field** anywhere in the new signature or `SymbolConfig` — fully removed.
- **No back-compat shim**.
- `uv run pytest --doctest-modules src/schematika/electrical/builder.py` → exit 0.
- `uv run python scripts/api_style_gate.py --strict` → exit 0 (1 positional-only `symbol_func` ✓).
- `uv run python scripts/api_docs_audit.py --strict` → exit 0.
- `uv run pytest --continue-on-collection-errors` → ≥ **2039** (post-C2a baseline).
- `uv run python scripts/ratchet_check.py` → exit 0.
- `uv run pre-commit run --all-files` → exit 0.
- `docs/ratchet/migrations/C2b-consumer-migration.md` exists.
- All existing tests pass UNCHANGED (mechanical kwarg → bundle edits only).

## Migration doc

Create `docs/ratchet/migrations/C2b-consumer-migration.md` with the same 5 sections as C2a's:

1. **Summary** — `add_symbol`'s 13 kwargs are bundled. `tag_prefix` is now a required field of `SymbolConfig`. `**kwargs` factory passthrough moved to `SymbolConfig.factory_kwargs`. `y_increment` removed (use `PlacementOptions.spacing`). Single hard breaking commit.
2. **Old → new mapping table**:

   | Old kwarg | New |
   | --------- | --- |
   | `tag_prefix` | `config=SymbolConfig(tag_prefix=...)` (required) |
   | `poles` | `config=SymbolConfig(poles=...)` |
   | `pins` | `config=SymbolConfig(pins=...)` (must be `tuple`, not `list`) |
   | `device` | `config=SymbolConfig(device=...)` |
   | `wire_labels_above` | `config=SymbolConfig(wire_labels_above=...)` (must be `tuple`) |
   | `**kwargs` | `config=SymbolConfig(factory_kwargs={"key": value, ...})` |
   | `relative_to` | `placement=PlacementOptions(relative_to=...)` |
   | `position` | `placement=PlacementOptions(position=...)` |
   | `spacing` | `placement=PlacementOptions(spacing=...)` |
   | `x_offset` | `placement=PlacementOptions(x_offset=...)` |
   | `y_increment` | **REMOVED.** Use `placement=PlacementOptions(spacing=...)`. |
   | `connect_from_previous` | `connection=ConnectionOptions(connect_from_previous=...)` |
   | `connect_to_next` | `connection=ConnectionOptions(connect_to_next=...)` |

3. **Call-site index** — implementer greps `../auxillary_cabinet_v3/src/circuits/` for `.add_symbol(`. Approximately 25 call sites across ~12 files. One representative before/after per file.

4. **What to test after migration** — same checklist as C2a (run consumer entry-point, diff SVG output).

5. **Breakage note** — explicit.

## Test strategy

Existing tests cover `add_symbol` through the public API. Update test call sites mechanically (kwargs → bundle). NO new tests beyond extending `tests/unit/core/test_options.py` with smoke tests for the new `SymbolConfig` dataclass:

- `test_symbol_config_required_tag_prefix` — `SymbolConfig()` raises `TypeError` (missing required `tag_prefix`).
- `test_symbol_config_with_defaults` — `SymbolConfig(tag_prefix="K")` constructs with all other fields at defaults.
- `test_symbol_config_factory_kwargs_passthrough` — `SymbolConfig(tag_prefix="K", factory_kwargs={"a": 1}).factory_kwargs == {"a": 1}`.

Add these to the existing `TestConstructorSmoke` / parameterised tests in `test_options.py`. Don't duplicate frozen/slots/kw_only checks — `SymbolConfig` joins the existing parameterise lists for those.

## Out of scope

- `add_terminal` (done in C2a), `add_spdt`, `add_reference`, `add_equipment`, `build_from_descriptors`, `_walk_loop`, `create_horizontal_layout` — those are C2c/d.
- Refactoring `_resolve_placement`. Body still unpacks `placement` before calling.
- Touching `../auxillary_cabinet_v3/`. Migration doc only.
- Dropping `max-args` ratchet threshold from current peak. Threshold drop happens in C2d.
- `CircuitBuilder` class docstring.
- Any unrelated formatting / docstring rewrites.

## Notes for the implementer

- **Model: sonnet.**
- **First action: `uv sync --all-extras`.** Then read `src/schematika/electrical/builder.py:291-435` (the `add_symbol` body).
- **`SymbolConfig.factory_kwargs` type**: `Mapping[str, Any] | None = None`. `Mapping` lives in `collections.abc` (no cycle, runtime import OK). `Any` is from `typing`. The frozen dataclass shallowly freezes — the `Mapping` itself can still be mutated (caveat noted in the docstring comment if you want to be explicit, but don't add an Args: block).
- **`InternalDevice` import**: under `if TYPE_CHECKING:`, same pattern as the existing `core/options.py` imports.
- **The body's `if pins is None: pins = _infer_default_pins(symbol_func)` block**: preserve this. Move it to operate on `cfg.pins`. The fallback to sequential pins (`[str(i) for i in range(1, poles*2 + 1)]`) also preserved. These mutations of pins are computed and stored in `spec.pins` — they don't mutate `config`.
- **`spec.y_increment`**: this is a `ComponentSpec` field, not a builder kwarg. The field stays in `ComponentSpec`. The builder used to receive it from `y_increment` kwarg OR fall back from `spacing`. Now: receive from `placement.spacing` only.
- **No `# noqa: ANN401`** in the new signature (the old one had it for `**kwargs: Any`).
- **Test edits**: `tests/unit/test_builder.py` and any test calling `add_symbol`. Use `git grep -n "\.add_symbol(" tests/`. Mechanical bundle wraps.
- **Examples updates**: `examples/*.py` may also call `add_symbol`. Use `git grep -n "\.add_symbol(" examples/`. Same mechanical pattern.
- **No new noqa, no new ty: ignore.**
- **Commit message**: `refactor(wave-C2b): add_symbol — bundle 13 kwargs into SymbolConfig + reuse PlacementOptions/ConnectionOptions`. Then a separate commit for the migration doc: `docs(wave-C2b): consumer migration guide for add_symbol bundling`.
