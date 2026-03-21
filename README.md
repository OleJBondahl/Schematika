# Schematika

Python library for programmatically generating IEC 60617-compliant electrical schematic diagrams as SVG.

> **Status:** Alpha. The API is subject to change.

## Features

- Zero runtime dependencies
- IEC 60617 electrical schematics
- ISO 14617 P&ID diagrams
- Block diagrams
- Cable harness drawing export
- PDF compilation (optional, via Typst)

## Installation

```bash
# Development
uv sync

# Standard
pip install -e .
```

## Quick Start

```python
from schematika.electrical.builder import CircuitBuilder
from schematika.core.state import GenerationState

# Create a simple circuit with a contactor and motor
state = GenerationState()
cb = CircuitBuilder(state=state)
cb.add_terminal(terminal="X1", label="-X1")
cb.add_symbol(symbol="no_contact", label="-K1")
cb.add_terminal(terminal="X2", label="-X2")
result = cb.build()
```

## Modules

| Module | Description |
|--------|-------------|
| `schematika.core` | Geometry primitives, SVG rendering, transforms |
| `schematika.electrical` | IEC 60617 electrical symbols and circuit builder |
| `schematika.pid` | ISO 14617 / ISA 5.1 P&ID diagram builder |
| `schematika.block` | Block diagram layout and rendering |
| `schematika.cable` | Cable harness drawing export |

## Development

```bash
uv sync               # Install dependencies
uv run pytest          # Run tests
uv run ruff check      # Lint
uv run ruff format     # Format
uv run ty check        # Type check
```

## License

MIT
