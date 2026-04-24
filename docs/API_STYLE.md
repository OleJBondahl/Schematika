# API Style

Rules for the public API surface and docstrings. Read before designing a new module or method. For package layering see [ARCHITECTURE.md](ARCHITECTURE.md).

## Verbs

One verb per concept. No synonyms.

| Verb | Meaning | Example |
|---|---|---|
| `add_<noun>` | Register a new component on a mutable builder | `builder.add_terminal`, `project.add_circuit` |
| `set_<noun>` | Configure a single-valued property on a builder | `builder.set_layout` |
| `build()` | Produce a frozen `*BuildResult` from a builder | `CircuitBuilder.build()` |
| `render(target)` | Produce output bytes/string, no I/O | `renderer.render(diagram) -> str` |
| `write(path)` | Shell operation that calls `render` then writes to disk | `project.write(Path("out.pdf"))` |
| `compile(project, path)` | End-to-end pipeline run (e.g. `TypstCompiler.compile`) | — |

Banned: any `get_`/`fetch_`/`load_`/`retrieve_` pair for the same operation; free-function `build_<noun>s(...)` when a builder already exists for that domain.

## Method naming rules

1. Every mutable-builder method that *registers* a thing is `add_<noun>`. Never `pipe()`, `cable()`, `circuit()`, `block()`, `field_devices()`.
2. Every mutable-builder method that *configures* is `set_<property>`.
3. Every builder produces a `*BuildResult` frozen dataclass via `build() -> *BuildResult`. No builder returns a bare list, `None`, or a `Project`.
4. `Project` methods that register are `add_<domain>`. Methods that act are `write` / `compile` / `export_<format>`.
5. One method per concept. If both `Project.circuit` and `add_circuit` exist, pick one and delete the other.

## Parameter glossary

Same concept, same name. If your new parameter is conceptually one of these, use the name in this table.

| Name | Type | Meaning |
|---|---|---|
| `name` | `str` | User-supplied lookup key (e.g. dict key on `Project`) |
| `label` | `str` | Rendered text shown on the diagram |
| `tag` | `str` | Autonumbered reference (`"K1"`, `"F2"`). Generated, not user-provided |
| `ref` | `ComponentRef` | Structural reference returned from `add_*` for later use |
| `position` | `Point \| None` | Diagram coordinates. `None` means auto-layout |
| `spacing` | `float` (mm) | Layout-axis distance between adjacent items |
| `gap` | `float` (mm) | Minimum clearance required between items |
| `offset` | `Vector` | Vector displacement |
| `port_id` | `str` | Port identifier on a symbol. Convention varies per symbol type; document at the symbol factory |
| `now` | `datetime \| None` | Clock read. Passed in, never called from inside |
| `state` | `GenerationState` | Functional-state thread. First arg of any state-reading fn |

Do not accept `x, y` as separate scalar kwargs on public APIs. Use `position: Point | None`. Internal helpers can still take scalars.

## Parameter ordering

One positional arg (identity). Everything else keyword-only after `*`. Positional-only marker `/` after the identity arg.

```python
def add_thing(
    self,
    name: str,                  # primary identity (required, positional-only)
    /,
    *,
    label: str | None = None,   # rendered text
    position: Point | None = None,
    pins: tuple[str, ...] = (),
) -> ComponentRef: ...
```

Call sites read as `builder.add_thing("K1", label="motor start")`. Adding a new kwarg never breaks positional callers.

## Return types

- Every domain builder returns a dedicated frozen `*BuildResult` dataclass. Never `list[...]`, never `None`, never `Project`.
- Free functions return a value or raise. Do not return `None` on failure; use the exception hierarchy.

## Exception hierarchy

One base per domain.

| Domain | Base |
|---|---|
| `electrical` | `CircuitValidationError` |
| `pid` | `PIDError` |
| `pcb` | `PCBBuildError` |
| `cable` | `CableError` |

All module-local errors inherit from the domain base. `ValueError` is reserved for programmer errors on stdlib boundaries; do not raise it for domain validation.

## Docstring format

Google style. One shape for every public function, method, and class.

```python
def add_terminal(
    self,
    name: str,
    /,
    *,
    poles: int = 1,
    position: Point | None = None,
) -> TerminalRef:
    """Register a terminal on the circuit.

    Args:
        name: Lookup key used by callers and exported on the terminal strip.
        poles: Number of poles (1 for single, 2+ for multi-pole blocks).
        position: Explicit coordinates; `None` triggers auto-layout.

    Returns:
        `TerminalRef` that can be used in subsequent `add_connection` calls.

    Raises:
        TerminalReuseError: If a terminal with `name` is already registered.
    """
```

Rules:

1. **First line** is imperative mood, <80 chars, period at end.
2. **Blank line**, then optional prose for non-obvious WHY (invariants, units, coordinate convention).
3. **Args:** block if the function has args. Every parameter, in signature order.
4. **Returns:** block if the return is not `None`. Describe the *meaning*, not the type.
5. **Raises:** block if the function raises. One line per exception class with the triggering condition.
6. **No** `Examples:` (use `pytest-examples` on markdown instead), **no** `Note:` (use inline prose), **no** multi-paragraph Args entries (>2 lines signals the parameter does too much).
7. **No paraphrase.** If the docstring only restates the signature, delete it.

Private functions (`_`-prefixed): one-line docstring if non-obvious, otherwise nothing.

## Enforcement

Four tools, wired into pre-commit and `just ci`.

| Tool | Catches |
|---|---|
| `ruff` with `D` rules (`convention = "google"`) | Docstring style: imperative first line, periods, Args/Returns/Raises blocks present, Google format |
| `ruff` with `N` | Class/function/variable name drift (`add_` prefix, snake_case) |
| `interrogate` | Docstring *coverage*. Fails if <80% of public symbols have any docstring |
| `darglint` | Docstring/signature *consistency*. Fails if Args lists params that don't exist in the signature or omits params that do |
| `scripts/api_style_gate.py` | The repo-specific AST rules that off-the-shelf linters don't know about: (a) any public `add_*`/`set_*` takes more than one positional-only arg, (b) any public function takes `x: float, y: float` without a `position: Point` alternative, (c) any method named `build` returns `None`, (d) a single public fn mixes `label`/`name`/`tag` |

The api_style_gate is the only tool that encodes Schematika's own rules. The rest are off-the-shelf lint. Run in report mode by default; `--strict` fails the build.
