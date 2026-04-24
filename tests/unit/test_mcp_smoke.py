"""MCP module smoke tests.

Audit H10: schematika.mcp.server + __main__ ship with 0% coverage. This file
imports the public MCP module and checks that the FastMCP server instance
is constructed at import time — no network, no server loop start.

If the optional `mcp` extra is not installed, the whole file is skipped.
"""

from __future__ import annotations

import pytest

mcp_ext = pytest.importorskip(
    "mcp.server.fastmcp",
    reason="optional 'mcp' extra not installed",
)


def test_server_module_imports() -> None:
    """Importing schematika.mcp.server must not raise."""
    from schematika.mcp import server  # noqa: F401 — import is the test


def test_fastmcp_instance_is_built() -> None:
    """The module-level `mcp` object is a live FastMCP instance."""
    from schematika.mcp.server import mcp

    assert isinstance(mcp, mcp_ext.FastMCP)


def test_symbol_catalog_non_empty() -> None:
    """_SYMBOL_NAMES is populated at import time (catches module-level errors)."""
    from schematika.mcp.server import _SYMBOL_NAMES

    assert isinstance(_SYMBOL_NAMES, list)
    assert len(_SYMBOL_NAMES) > 0


# NOTE: `schematika.mcp.__main__` is intentionally NOT smoke-imported — it
# lacks an `if __name__ == "__main__":` guard, so import would call `mcp.run()`
# and block on stdio. The 2 lines stay at 0% via a coverage.run omit below.
