# Wave C2a consumer migration guide — `add_terminal` bundling

## Summary

`CircuitBuilder.add_terminal` previously accepted 16 keyword-only arguments plus a
`**kwargs` passthrough (17 parameters total including `tm_id`). In wave C2a, all kwargs
are bundled into 4 frozen dataclasses imported from `schematika.core.options`:
`TerminalConfig`, `PlacementOptions`, `TerminalDisplayOptions`, and `ConnectionOptions`.
The `**kwargs` passthrough is **removed** — no call site in the consumer used it.

The new signature is:

```python
def add_terminal(
    self,
    tm_id: str | Terminal,
    /,
    *,
    config: TerminalConfig | None = None,
    placement: PlacementOptions | None = None,
    display: TerminalDisplayOptions | None = None,
    connection: ConnectionOptions | None = None,
) -> ComponentRef: ...
```

This is a **single hard breaking commit**. There is no compatibility shim.

---

## Old → new mapping table

| Old kwarg | New bundle + field |
|---|---|
| `poles` | `config=TerminalConfig(poles=...)` |
| `pins` | `config=TerminalConfig(pins=...)` — must be `tuple`, not `list` |
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
| `**kwargs` | **REMOVED.** No consumer call site used passthrough kwargs (verified). |

### Note on `pins`

`pins` on `TerminalConfig` is `tuple[str, ...] | None`. If your code passes a list,
convert it: `pins=["a", "b"]` → `pins=("a", "b")`.

### Note on `bridge`

`ConnectionOptions.bridge` defaults to `None`, which the builder treats identically to
`BridgeMode.NONE`. Pass any `BridgeMode` value as before:
`connection=ConnectionOptions(bridge=BridgeMode.AUTO)`.

---

## Call-site index

Grepped `../auxillary_cabinet_v3/src/circuits/` for `.add_terminal(`. 40 call sites
across 10 files. Representative before/after examples follow.

### `circuits/plc_power.py:38` — bare call (no kwargs)

```python
# Before
builder.add_terminal(Terminals.FUSED_24V)
builder.add_terminal(Terminals.GND)

# After — no change needed; all defaults are preserved
builder.add_terminal(Terminals.FUSED_24V)
builder.add_terminal(Terminals.GND)
```

### `circuits/power_supply.py:106` — multi-kwarg form

```python
# Before
tm = builder.add_terminal(
    Terminals.SWITCHED_230V,
    logical_name="INPUT",
    poles=2,
    pin_prefixes=("L1", "N"),
    x_offset=0,
    spacing=SPACING_NARROW,
    label_pos="left",
    connect_to_next=False,
)

# After
from schematika.core.options import (
    ConnectionOptions, PlacementOptions, TerminalConfig, TerminalDisplayOptions
)

tm = builder.add_terminal(
    Terminals.SWITCHED_230V,
    config=TerminalConfig(
        logical_name="INPUT",
        poles=2,
        pin_prefixes=("L1", "N"),
    ),
    placement=PlacementOptions(x_offset=0, spacing=SPACING_NARROW),
    display=TerminalDisplayOptions(label_pos="left"),
    connection=ConnectionOptions(connect_to_next=False),
)
```

### `circuits/internal_distribution.py:67,72` — dict-spread (`**kwargs`) form

This is the only non-mechanical migration in the consumer. The existing code
constructs `dict` objects and passes them as `**top_kwargs` / `**bot_kwargs`:

```python
# Before — dict-spread (will break immediately; **kwargs removed)
top_kwargs: dict = {"poles": poles, "label_pos": "left", "connect_to_next": False}
if top_prefixes:
    top_kwargs["pin_prefixes"] = top_prefixes
top = builder.add_terminal(internal_term, **top_kwargs)

bot_kwargs: dict = {"poles": poles, "label_pos": "left", "connect_to_next": False}
if bot_prefixes:
    bot_kwargs["pin_prefixes"] = bot_prefixes
bot = builder.add_terminal(external_term, **bot_kwargs)
```

```python
# After — construct dataclass objects directly
from schematika.core.options import (
    ConnectionOptions, TerminalConfig, TerminalDisplayOptions
)

top = builder.add_terminal(
    internal_term,
    config=TerminalConfig(poles=poles, pin_prefixes=top_prefixes or None),
    display=TerminalDisplayOptions(label_pos="left"),
    connection=ConnectionOptions(connect_to_next=False),
)
bot = builder.add_terminal(
    external_term,
    config=TerminalConfig(poles=poles, pin_prefixes=bot_prefixes or None),
    display=TerminalDisplayOptions(label_pos="left"),
    connection=ConnectionOptions(connect_to_next=False),
)
```

Note: `pin_prefixes` on `TerminalConfig` accepts `tuple[str, ...] | None`. The
conditional `top_prefixes or None` handles the empty-tuple case.

### `circuits/fan_singlepole.py:72` — poles + pin_prefixes

```python
# Before
builder.add_terminal(Terminals.SWITCHED_230V, poles=2, pin_prefixes=("L2", "N"))

# After
builder.add_terminal(
    Terminals.SWITCHED_230V,
    config=TerminalConfig(poles=2, pin_prefixes=("L2", "N")),
)
```

### `circuits/fan_singlepole.py:96` — poles + pins + connection_side

```python
# Before
tm_bot = builder.add_terminal(
    FAN_TERMINALS[i], poles=2, pins=("L", "N"), connection_side="bottom"
)

# After
tm_bot = builder.add_terminal(
    FAN_TERMINALS[i],
    config=TerminalConfig(poles=2, pins=("L", "N")),
    connection=ConnectionOptions(connection_side="bottom"),
)
```

### `circuits/pump_circuit.py:118-119` — relative_to + position + label_pos

```python
# Before
builder.add_terminal(Terminals.FUSED_24V, relative_to=ct.pin("53"), position="above")
builder.add_terminal(
    Terminals.GND, relative_to=ct.pin("54"), position="above", label_pos="right"
)

# After
builder.add_terminal(
    Terminals.FUSED_24V,
    placement=PlacementOptions(relative_to=ct.pin("53"), position="above"),
)
builder.add_terminal(
    Terminals.GND,
    placement=PlacementOptions(relative_to=ct.pin("54"), position="above"),
    display=TerminalDisplayOptions(label_pos="right"),
)
```

### `circuits/valve_control.py:79` — pin_prefixes + label_pos

```python
# Before
contact_builder.add_terminal(
    Terminals.SWITCHED_230V, pin_prefixes=("L3",), label_pos="right"
)

# After
contact_builder.add_terminal(
    Terminals.SWITCHED_230V,
    config=TerminalConfig(pin_prefixes=("L3",)),
    display=TerminalDisplayOptions(label_pos="right"),
)
```

### `circuits/fan_controll.py:122` — poles + connection flags

```python
# Before
tm_bot_block = block_builder.add_terminal(
    Terminals.IO_EXT,
    poles=2,
    connect_to_next=False,
    connect_from_previous=False,
)

# After
tm_bot_block = block_builder.add_terminal(
    Terminals.IO_EXT,
    config=TerminalConfig(poles=2),
    connection=ConnectionOptions(connect_to_next=False, connect_from_previous=False),
)
```

### `circuits/power_switching.py:90` — pin_prefixes + poles + connection_side

```python
# Before
k1_builder.add_terminal(
    Terminals.MAIN_400V,
    pin_prefixes=("N",),
    poles=1,
    connection_side="bottom",
)

# After
k1_builder.add_terminal(
    Terminals.MAIN_400V,
    config=TerminalConfig(pin_prefixes=("N",), poles=1),
    connection=ConnectionOptions(connection_side="bottom"),
)
```

### `circuits/pump_controll.py:91` — relative_to + position + label_pos + wire_label

```python
# Before
b.add_terminal(
    Terminals.IO_EXT,
    relative_to=spdt.pin(pins[1]),
    position="below",
    label_pos="left",
    wire_label=WireLabels.WH_0_5,
)

# After
b.add_terminal(
    Terminals.IO_EXT,
    placement=PlacementOptions(relative_to=spdt.pin(pins[1]), position="below"),
    display=TerminalDisplayOptions(label_pos="left"),
    connection=ConnectionOptions(wire_label=WireLabels.WH_0_5),
)
```

### `circuits/feedback.py` — bare calls (no kwargs)

All 3 calls in this file pass only the terminal ID. No migration needed beyond the
mechanical rename — bare calls are unaffected by the signature change.

```python
# Before (and After — no change needed)
q_builder.add_terminal(Terminals.GND)
ft_builder.add_terminal(Terminals.GND)
builder.add_terminal(Terminals.GND)
```

---

## What to test after migration

```bash
cd ../auxillary_cabinet_v3
uv run python src/main.py
```

Diff the resulting SVG output against the pre-migration version — it should be
byte-identical because the behaviour of `add_terminal` is preserved exactly.

---

## Breakage note

**This is a breaking change.** The consumer will not import or run until updated.
There is no compatibility shim. Every `.add_terminal(` call site with old kwargs
will raise `TypeError: add_terminal() got an unexpected keyword argument`.
