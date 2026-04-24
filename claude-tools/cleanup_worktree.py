"""Robustly remove a git worktree on Windows.

Windows file handles from IDEs, indexers, and AV briefly hold worktree
files after an agent exits. `git worktree remove -f` then fails with
EACCES. This script retries with exponential backoff, falls back to
PowerShell's `Remove-Item -Force -Recurse`, and finishes with
`git worktree prune` so git metadata stays clean.

Usage:
    uv run python claude-tools/cleanup_worktree.py <worktree-path> [branch-name]
"""

from __future__ import annotations

import subprocess  # nosec B404 - invokes git + PowerShell with list args, no shell
import sys
import time
from pathlib import Path


def run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)  # nosec B603 - list args, no shell


def git_worktree_remove(path: Path) -> bool:
    r = run(["git", "worktree", "remove", "-f", str(path)])
    return r.returncode == 0


def powershell_force_remove(path: Path) -> bool:
    ps_cmd = f"Remove-Item -LiteralPath '{path}' -Recurse -Force -ErrorAction Stop"
    r = run(["powershell.exe", "-NoProfile", "-Command", ps_cmd])
    return r.returncode == 0


def cleanup(path: Path, branch: str | None = None) -> int:
    if not path.exists() and branch is None:
        return 0

    delays = [0, 1, 2, 4, 8]
    for i, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        if not path.exists():
            break
        if git_worktree_remove(path):
            break
        if i == len(delays) - 1:
            # last resort
            powershell_force_remove(path)

    run(["git", "worktree", "prune"])

    if branch:
        r = run(["git", "branch", "-D", branch])
        if r.returncode != 0 and "not found" not in (r.stderr or "").lower():
            sys.stderr.write(f"branch delete warning: {r.stderr}")

    if path.exists():
        sys.stderr.write(f"worktree path still exists: {path}\n")
        return 1
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    path = Path(sys.argv[1]).resolve()
    branch = sys.argv[2] if len(sys.argv) > 2 else None
    return cleanup(path, branch)


if __name__ == "__main__":
    sys.exit(main())
