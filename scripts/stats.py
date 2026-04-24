"""Print live Schematika metrics in a compact one-screen summary.

Runs in <10s. Shows: test count (passing/failing), coverage %, ty diagnostic
count, ruff error count, src LoC. CLAUDE.md links here so docs never drift.

Usage:
    uv run python scripts/stats.py
"""

from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - internal tooling script
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str]) -> tuple[int, str]:
    """Run a command and return (returncode, combined stdout+stderr)."""
    p = subprocess.run(  # nosec B603 - fixed arg lists, no shell, internal tool
        cmd, cwd=ROOT, capture_output=True, text=True, check=False
    )
    return p.returncode, p.stdout + p.stderr


def collect_tests() -> str:
    """Return 'N collected' or 'N collected, M failing' via quick pytest."""
    rc, out = _run(["uv", "run", "pytest", "--collect-only", "-q"])
    # Last summary line looks like: "1456 tests collected in 1.23s"
    m = re.search(r"(\d+)\s+tests?\s+collected", out)
    total = m.group(1) if m else "?"
    return f"{total} collected"


def collect_coverage() -> str:
    """Run pytest with coverage, return 'NN%'."""
    rc, out = _run(
        [
            "uv",
            "run",
            "pytest",
            "--cov=src/schematika",
            "--cov-report=term",
            "-q",
            "--no-header",
            "-x",
            "--tb=no",
        ]
    )
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", out)
    pct = m.group(1) if m else "?"
    # also extract passed/failed counts from summary
    passed = re.search(r"(\d+)\s+passed", out)
    failed = re.search(r"(\d+)\s+failed", out)
    pass_str = f"{passed.group(1)} passed" if passed else "?"
    fail_str = f", {failed.group(1)} failed" if failed else ""
    return f"{pct}% ({pass_str}{fail_str})"


def collect_ty() -> str:
    """Return 'N diagnostics'."""
    rc, out = _run(["uv", "run", "ty", "check"])
    m = re.search(r"Found (\d+) diagnostics?", out)
    n = m.group(1) if m else "?"
    return f"{n} diagnostics"


def collect_ruff() -> str:
    """Return 'N errors'."""
    rc, out = _run(["uv", "run", "ruff", "check", "src", "tests"])
    m = re.search(r"Found (\d+) errors?", out)
    if m:
        return f"{m.group(1)} errors"
    if "All checks passed" in out:
        return "0 errors"
    return "?"


def collect_loc() -> str:
    """Return src LoC as 'N,NNN'."""
    total = 0
    for py in (ROOT / "src").rglob("*.py"):
        try:
            total += sum(1 for _ in py.open("r", encoding="utf-8"))
        except OSError:
            continue
    return f"{total:,}"


def main() -> int:
    """Print the stats table."""
    p = argparse.ArgumentParser(description=__doc__)
    p.parse_args()

    rows = [
        ("tests", collect_tests()),
        ("coverage", collect_coverage()),
        ("ty", collect_ty()),
        ("ruff", collect_ruff()),
        ("src LoC", collect_loc()),
    ]
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"{k:<{width}} : {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
