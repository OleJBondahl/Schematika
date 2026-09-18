"""git_commit_stamp — short-hash provenance stamp for build artifacts."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def git_commit_stamp(root: Path) -> str:
    """Short hash of HEAD at `root`, with a `+dirty` suffix if uncommitted.

    Args:
        root: Path inside the git working tree to stamp.

    Returns:
        The short commit hash, e.g. "a1b2c3d", or "a1b2c3d+dirty" if the
        tracked-file working tree has uncommitted changes.

    Examples:
        >>> callable(git_commit_stamp)
        True
    """
    commit = subprocess.run(  # noqa: S603 -- fixed git argv, no untrusted input
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],  # noqa: S607 -- git on PATH
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    status = subprocess.run(  # noqa: S603 -- fixed git argv, no untrusted input
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return f"{commit}+dirty" if status else commit
