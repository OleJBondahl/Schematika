# Contributing

Run `just ci` before pushing. It covers ruff, ty, and pytest with the same settings the pre-commit hooks use.

If you are adding a public API, read `docs/API_STYLE.md` first. Darglint + `scripts/api_style_gate.py` will reject drift in pre-commit.
