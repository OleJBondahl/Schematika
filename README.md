# Schematika

**AI can generate your electrical schematics.**

Schematika is a Python library that generates IEC 60617-compliant electrical schematic diagrams programmatically. Describe your circuit in Python — get standards-compliant SVG/PDF output. Define once, generate 100 variants. Version-control your schematics like code.

> **Status:** Alpha (v0.1.7). API is stabilizing toward beta.

## Features

- Zero runtime dependencies
- IEC 60617 electrical schematics
- ISO 14617 P&ID diagrams
- Block diagrams
- Cable harness drawing export
- PDF compilation (optional, via Typst)
- AI/LLM-friendly: consistent types, helpful error messages, flat imports

## Installation

```bash
pip install schematika          # Core library
pip install schematika[pdf]     # With PDF compilation
pip install schematika[mcp]     # With MCP server for AI integration
```

Development:
```bash
uv sync
```

## Quick Start

### Minimal Circuit (6 lines)

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

### 3-Phase DOL Starter

```python
from schematika import (
    CircuitBuilder, create_initial_state, render_system,
    breaker, contactor, thermal_overload, motor,
)

state = create_initial_state()
builder = CircuitBuilder(state)
builder.set_layout(x=0, y=0, spacing=150)
builder.add_terminal(tm_id="X1", poles=3)
builder.add_symbol(breaker, tag_prefix="F", poles=3)
builder.add_symbol(contactor, tag_prefix="Q", poles=3)
builder.add_symbol(thermal_overload, tag_prefix="FT", poles=3)
builder.add_symbol(motor, tag_prefix="M", poles=3)
builder.add_terminal(tm_id="X2", poles=3)
result = builder.build(count=1)
render_system(result.circuit, "dol_starter.svg")
```

See [`examples/`](examples/) for 5 progressive examples from single relay to full cabinet PDF.

## For AI/LLM Users

Schematika is designed to be used by LLMs. See:
- [`docs/LLM_REFERENCE.md`](docs/LLM_REFERENCE.md) — Complete cheat sheet: all symbols, pin conventions, patterns
- [`examples/`](examples/) — 5 progressive examples (copy-paste starting points)
- [`llms.txt`](llms.txt) — Machine-readable documentation index

## Modules

| Module | Description |
|--------|-------------|
| `schematika.electrical` | IEC 60617 electrical symbols and circuit builder |
| `schematika.pid` | ISO 14617 / ISA 5.1 P&ID diagram builder |
| `schematika.block` | Block diagram layout and rendering |
| `schematika.cable` | Cable harness drawing export |
| `schematika.mcp` | MCP server for AI integration (optional) |

## Development

```bash
uv sync               # Install dependencies
uv run pytest          # Run tests (1334 tests, ~5s)
uv run ruff check      # Lint
uv run ruff format     # Format
uv run ty check        # Type check
```

## License

MIT
