"""Robustly remove a git worktree on Windows.

Windows file handles from IDEs, indexers, and AV briefly hold worktree
files after an agent exits. `git worktree remove -f` then fails with
EACCES. This script unlocks the worktree, retries removal with
exponential backoff, falls back to PowerShell's `Remove-Item -Force
-Recurse`, manually scrubs the `.git/worktrees/<name>` metadata dir
if git prune can't, and finally drops the branch.

Usage:
    uv run python scripts/cleanup_worktree.py <worktree-path> [branch-name]
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - invokes git + PowerShell with list args, no shell
import sys
import time
from pathlib import Path


def run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)  # nosec B603 - list args, no shell


def unlock_worktree(path: Path) -> None:
    run(["git", "worktree", "unlock", str(path)])


def git_worktree_remove(path: Path) -> bool:
    r = run(["git", "worktree", "remove", "-f", str(path)])
    return r.returncode == 0 and not path.exists()


def powershell_force_remove(path: Path) -> bool:
    ps_cmd = (
        f"try {{ Remove-Item -LiteralPath '{path}' -Recurse -Force -ErrorAction Stop }} "
        "catch { exit 1 }"
    )
    r = run(["powershell.exe", "-NoProfile", "-Command", ps_cmd])
    return r.returncode == 0 and not path.exists()


def scrub_git_metadata(worktree_name: str) -> bool:
    git_dir = run(["git", "rev-parse", "--git-common-dir"]).stdout.strip()
    if not git_dir:
        return False
    meta = Path(git_dir) / "worktrees" / worktree_name
    if not meta.exists():
        return True
    try:
        shutil.rmtree(meta, ignore_errors=False)
    except OSError:
        return powershell_force_remove(meta)
    return not meta.exists()


def cleanup(path: Path, branch: str | None = None) -> int:
    worktree_name = path.name
    unlock_worktree(path)

    for delay in [0, 1, 2, 4, 8, 15]:
        if delay:
            time.sleep(delay)
        if not path.exists() or git_worktree_remove(path):
            break
    else:
        powershell_force_remove(path)

    run(["git", "worktree", "prune", "-v"])
    scrub_git_metadata(worktree_name)

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
