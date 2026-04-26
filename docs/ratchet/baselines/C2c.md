# Wave C2c baseline — `add_spdt` 12 args → ≤ 4 args via option bundles

Branch base: `branch1` @ `06f7153` (post-C2b).
Wave branch: `complexity/C2c` in worktree `.worktrees/complexity/C2c`.

## State at start

`CircuitBuilder.add_spdt` at `src/schematika/electrical/builder.py` (post-C2b line numbers will shift; the function is the same one) has 12 keyword-or-positional args. Unlike `add_terminal` and `add_symbol`, `add_spdt` has **no `**kwargs`** passthrough — the SPDT factory is fixed to `spdt_contact`.

### Current signature

```python
def add_spdt(
    self,
    tag_prefix: str = "K",
    /,
    *,
    poles: int = 1,
    pins: list[str] | tuple[str, ...] | None = None,
    inverted: bool = False,
    relative_to: "ComponentRef | PortRef | None" = None,
    position: "Position" = "below",
    connect_from_previous: bool = False,  # NOTE: defaults to False, not True
    spacing: float | None = None,
    x_offset: float = 0.0,
    y_increment: float | None = None,
    device: "InternalDevice | None" = None,
    wire_labels_above: list[str] | tuple[str, ...] | None = None,
) -> "ComponentRef":
```

### Target signature (post-C2c)

```python
def add_spdt(
    self,
    tag_prefix: str = "K",
    /,
    *,
    config: SpdtConfig | None = None,
    placement: PlacementOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> "ComponentRef":
```

4 params (excluding `self`). Hits the plan's `≤ 4` target. **`tag_prefix` stays as the positional-only identity arg** (with its existing default `"K"`) — simpler than collapsing into `SpdtConfig`, since it has a default and many calls just pass it as the first arg. **No `y_increment`** — fully removed (use `PlacementOptions.spacing`).

## Wave scope

Hard breaking change. Single commit replaces the signature.

### Extend `src/schematika/core/options.py` (already exists)

Add ONE new dataclass — `SpdtConfig`. Reuse the existing `PlacementOptions` and `ConnectionOptions` from C2a/b unchanged:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SpdtConfig:
    """Pin layout + IEC inversion + device + wire labels for an SPDT contact."""

    poles: int = 1
    pins: tuple[str, ...] | None = None
    inverted: bool = False
    device: InternalDevice | None = None
    wire_labels_above: tuple[str, ...] | None = None
```

5 fields. Tier-3 single-line docstring. Same TYPE_CHECKING-guarded `InternalDevice` import as `SymbolConfig`. **No `tag_prefix` field** — it stays as the method's positional arg.

### `connect_from_previous` default behaviour

The old `add_spdt` defaulted `connect_from_previous=False`, while `ConnectionOptions().connect_from_previous` is `True`. To preserve the old default:

```python
con = connection or ConnectionOptions(
    connect_from_previous=False, connect_to_next=False,
)
```

The body's `or`-chain default is `connect_from_previous=False, connect_to_next=False` (matching the old hard-coded `connect_to_next=False` and old default `connect_from_previous=False`). Callers who want `connect_from_previous=True` pass an explicit `ConnectionOptions(connect_from_previous=True)` — with that, `connect_to_next` will silently default to `True` from the bundle BUT add_spdt's body still hard-overrides it (per the existing precedent: `add_spdt` always sets `connect_to_next=False` regardless of caller intent — see `src/schematika/electrical/builder.py` `connect_to_next=False` at the spec construction).

Document this asymmetry in the SpdtConfig class docstring isn't necessary (tier-3 single-line WHY only) — instead, mention it in the migration doc and in `add_spdt`'s tier-1 docstring under `Args:` for `connection`.

### Body changes in `add_spdt`

Same pattern as C2a/b — 2-line bundle-unpack preamble:

```python
def add_spdt(
    self,
    tag_prefix: str = "K",
    /,
    *,
    config: SpdtConfig | None = None,
    placement: PlacementOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> "ComponentRef":
    """<tier-1 docstring>"""
    self._check_not_frozen()
    cfg = config or SpdtConfig()
    plc = placement or PlacementOptions()
    con = connection or ConnectionOptions(
        connect_from_previous=False, connect_to_next=False,
    )

    # ... rest of body reads from cfg.poles, cfg.pins, cfg.inverted, ...,
    #     plc.relative_to, plc.position, plc.spacing, plc.x_offset,
    #     con.connect_from_previous (NOTE: con.connect_to_next is ignored —
    #     spec.connect_to_next is hard-coded to False, preserving old
    #     behaviour).
```

`_resolve_placement` signature unchanged — body unpacks `placement` before calling.

### Tier-1 docstring rewrite (mandatory)

`add_spdt` is tier-1. Rewrite per C2a/b precedent:

```python
def add_spdt(self, tag_prefix="K", /, *, config=None, placement=None, connection=None):
    """Register an SPDT contact (default IEC pins 11/12/14: COM/NC/NO).

    Args:
        tag_prefix: Tag prefix for autonumbering. Defaults to ``"K"``.
        config: Pin layout + IEC inversion + device + wire labels. ``None`` means
            single-pole, default IEC pins, not inverted. See :class:`SpdtConfig`.
        placement: Where to place this SPDT. ``None`` means below the previous
            chain head with default spacing. See :class:`PlacementOptions`.
        connection: Chain-wiring knobs. ``None`` means **do not connect from previous**
            (SPDT default differs from other ``add_*`` methods). ``connect_to_next``
            in this bundle is IGNORED — ``add_spdt`` always sets the spec's
            ``connect_to_next`` to ``False`` because SPDTs branch the chain.
            See :class:`ConnectionOptions`.

    Returns:
        ``ComponentRef`` to this SPDT — usable as ``relative_to`` for subsequent
        components and as a source/target via :meth:`ComponentRef.pin`.

    Raises:
        RuntimeError: If the builder has been frozen by :meth:`build`.

    Examples:
        >>> from schematika.electrical import CircuitBuilder, create_initial_state
        >>> b = CircuitBuilder(state=create_initial_state())
        >>> ref = b.add_spdt("K")
        >>> ref._index
        0
    """
```

The doctest must run via `uv run pytest --doctest-modules src/schematika/electrical/builder.py`.

## Done condition

- `add_spdt` parameter count **= 4** (excluding `self`).
- `core/options.py` extended with `SpdtConfig`. Tier-3 single-line docstring.
- `add_spdt` tier-1 docstring rewritten per the template above.
- **No `y_increment`** field anywhere — fully removed.
- **No `**kwargs`** added (none was there before).
- **No back-compat shim**.
- `con` default-construction in body uses `connect_from_previous=False, connect_to_next=False` to preserve old default behaviour.
- `uv run pytest --doctest-modules src/schematika/electrical/builder.py` → exit 0.
- `uv run python scripts/api_style_gate.py --strict` → exit 0.
- `uv run python scripts/api_docs_audit.py --strict` → exit 0.
- `uv run pytest --continue-on-collection-errors` → ≥ **2044** (post-C2b baseline).
- `uv run python scripts/ratchet_check.py` → exit 0.
- `uv run pre-commit run --all-files` → exit 0.
- `docs/ratchet/migrations/C2c-consumer-migration.md` exists.
- All existing tests pass UNCHANGED — mechanical kwarg → bundle edits only.

## Migration doc

Create `docs/ratchet/migrations/C2c-consumer-migration.md` with the same 5 sections.

Mapping table:

| Old kwarg | New |
| --------- | --- |
| `tag_prefix` | (positional, unchanged — still defaults to `"K"`) |
| `poles` | `config=SpdtConfig(poles=...)` |
| `pins` | `config=SpdtConfig(pins=...)` (must be `tuple`, not `list`) |
| `inverted` | `config=SpdtConfig(inverted=...)` |
| `device` | `config=SpdtConfig(device=...)` |
| `wire_labels_above` | `config=SpdtConfig(wire_labels_above=...)` (must be `tuple`) |
| `relative_to` | `placement=PlacementOptions(relative_to=...)` |
| `position` | `placement=PlacementOptions(position=...)` |
| `spacing` | `placement=PlacementOptions(spacing=...)` |
| `x_offset` | `placement=PlacementOptions(x_offset=...)` |
| `y_increment` | **REMOVED.** Use `placement=PlacementOptions(spacing=...)`. |
| `connect_from_previous` | `connection=ConnectionOptions(connect_from_previous=...)`. **Note**: `add_spdt` defaults `connect_from_previous` to **False** (different from `add_terminal`/`add_symbol`). To preserve old behaviour, omit `connection=` entirely. |

**Special note for the migration doc**: `connect_to_next` in `ConnectionOptions` is silently ignored by `add_spdt` (always set to False internally). Document this clearly.

Call-site index: implementer greps `../auxillary_cabinet_v3/src/circuits/` for `.add_spdt(`. Approximately 4-5 call sites across ~3 files. Before/after snippets per file.

What to test: same checklist as C2a/b.

Breakage note: explicit, including the `connect_from_previous=False` default asymmetry.

## Test strategy

Existing tests cover `add_spdt` through the public API. Mechanical update of test call sites to use bundles. Extend `tests/unit/core/test_options.py` with 1-2 small `SpdtConfig` smoke tests (defaults construction; add to existing parameterised lists for frozen/slots/kw_only checks).

## Out of scope

- `add_terminal` (C2a), `add_symbol` (C2b), `add_reference`, `add_equipment`, `build_from_descriptors`, `_walk_loop`, `create_horizontal_layout` — those are C2d.
- Refactoring `_resolve_placement`.
- Touching `../auxillary_cabinet_v3/`. Migration doc only.
- Dropping `max-args` ratchet threshold (C2d's job).
- `CircuitBuilder` class docstring.

## Notes for the implementer

- **Model: sonnet.**
- **First action: `uv sync --all-extras`.** Then read `src/schematika/electrical/builder.py` for the `add_spdt` body (post-C2a/b line numbers; find via `git grep -n "def add_spdt"`).
- **`tag_prefix` stays positional**. Do NOT collapse it into `SpdtConfig`. The simple `b.add_spdt()` (uses default "K") call must still work.
- **`con` default-construction is the cycle-safe spot for the old `connect_from_previous=False` default**. Use the `or ConnectionOptions(connect_from_previous=False, connect_to_next=False)` pattern from the spec, NOT a separate guard clause.
- **Spec body keeps `connect_to_next=False` hard-coded** in `ComponentSpec(...)` regardless of `con.connect_to_next` value. This is the pre-existing behaviour — preserve it.
- **Sym factory selection**: the existing `from schematika.electrical.symbols.contacts import spdt_contact` inline import in `add_spdt`'s body — leave it. (It avoids a top-level cycle.) Do not refactor.
- **Test edits**: `git grep -n "\.add_spdt(" tests/` and `git grep -n "\.add_spdt(" examples/`. Mechanical wraps.
- **Do NOT remove `Returns:` or `Raises:` sections from the new tier-1 docstring** — those are mandated by CLAUDE.md / the C2a-b precedent. The reviewer may complain about length; ignore them on this point.
- **No new noqa, no new ty: ignore.**
- **Two commits**:
  - `refactor(wave-C2c): add_spdt — bundle 12 kwargs into SpdtConfig + reuse PlacementOptions/ConnectionOptions`
  - `docs(wave-C2c): consumer migration guide for add_spdt bundling`
