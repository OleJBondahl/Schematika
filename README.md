# Schematika

Generate IEC 60617 electrical schematics (plus ISO 14617 P&ID, block diagrams, and cable harness drawings) from Python. Describe the circuit as data, render to SVG or PDF.

Alpha. API is not stable.

## Install

```bash
pip install schematika          # core
pip install schematika[pdf]     # + Typst PDF compilation
pip install schematika[mcp]     # + MCP server
```

## Minimal example

```python
from schematika import CircuitBuilder, coil, create_initial_state, render_system

state = create_initial_state()
builder = CircuitBuilder(state)
builder.set_layout(x=0, y=0)
builder.add_terminal(tm_id="X1", poles=1)
builder.add_symbol(coil, tag_prefix="K", poles=1)
builder.add_terminal(tm_id="X2", poles=1)
result = builder.build(count=1)
render_system(result.circuit, "relay.svg")
```

More examples: [`examples/`](examples/). API reference: [`docs/`](docs/).

## Develop

```bash
uv sync
uv run pytest
just ci        # lint + type-check + tests
```

MIT.
