"""git_commit_stamp(): short-hash provenance stamp for build artifacts."""

import subprocess
from pathlib import Path

from schematika.git_stamp import git_commit_stamp


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)  # noqa: S607
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],  # noqa: S607
        cwd=path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)  # noqa: S607


def test_git_commit_stamp_clean_tree(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)  # noqa: S607
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)  # noqa: S607

    stamp = git_commit_stamp(tmp_path)

    assert "+dirty" not in stamp
    assert len(stamp) >= 7


def test_git_commit_stamp_dirty_tree(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)  # noqa: S607
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)  # noqa: S607
    (tmp_path / "a.txt").write_text("changed", encoding="utf-8")

    stamp = git_commit_stamp(tmp_path)

    assert stamp.endswith("+dirty")
