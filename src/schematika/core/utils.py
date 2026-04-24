"""General-purpose utility functions with no domain-specific dependencies."""

from __future__ import annotations

import re

import deal


@deal.pure
def natural_sort_key(tag: str) -> list[int | str]:
    """Return a sort key that orders numeric suffixes naturally.

    Splits the tag into alternating text and number parts so that
    ``"K4"`` sorts before ``"K10"``.

    Args:
        tag: A string tag to generate a sort key for.

    Returns:
        A list of ``str`` and ``int`` parts suitable for use as a sort key.

    Example::

        sorted(["K10", "K2", "K1"], key=natural_sort_key)
        # → ["K1", "K2", "K10"]
    """
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", tag)]
