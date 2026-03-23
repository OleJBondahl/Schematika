# Contributing to Schematika

## Dev Setup

```bash
uv sync
```

## Running Tests

```bash
uv run pytest
```

## Linting & Formatting

```bash
uv run ruff check     # lint
uv run ruff format    # auto-format
uv run ty check       # type checking
```

## Pull Request Expectations

- All tests must pass
- No ruff lint errors
- No ty type errors
- Keep changes focused — one concern per PR
