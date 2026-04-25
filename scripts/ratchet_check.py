"""Numeric ratchet — verify locked metrics in docs/ratchet/baseline.toml.

Three modes:
  --check  (default) compare current metrics against baseline; exit 1 on regression.
  --update rewrite baseline.toml in place from current metrics (preserves header).
  --fast   --check minus pytest run + coverage (used by pre-commit hook).

Other gates (ruff, ty, vulture, import-linter) are independently enforced by
their own pre-commit hooks; this script is a configuration-drift backstop.

Usage:
    uv run python scripts/ratchet_check.py
    uv run python scripts/ratchet_check.py --fast
    uv run python scripts/ratchet_check.py --update
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "docs" / "ratchet" / "baseline.toml"
_VULTURE_FOUND = 2  # vulture exit code when findings exist


def _emit(line: str) -> None:
    sys.stdout.write(line + "\n")


def _warn(line: str) -> None:
    sys.stderr.write(line + "\n")


@dataclass(frozen=True)
class Metric:
    """One ratchet metric. `kind` is "le" (≤baseline) or "ge" (≥baseline)."""

    section: str
    key: str
    current: int
    baseline: int
    kind: str
    note: str = ""

    @property
    def passed(self) -> bool:
        """True iff current respects the comparison direction set by `kind`."""
        if self.kind == "le":
            return self.current <= self.baseline
        return self.current >= self.baseline

    @property
    def op(self) -> str:
        """Comparison glyph for display."""
        return "≤" if self.kind == "le" else "≥"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a fully-formed argv. `errors="replace"` survives Windows cp1252 mojibake."""
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        encoding="utf-8",
        errors="replace",
    )


def collect_ruff() -> int | None:
    """Count ruff errors via JSON output (independent of console formatting)."""
    r = _run(["uv", "run", "ruff", "check", "src", "tests", "--output-format=json"])
    try:
        return len(json.loads(r.stdout or "[]"))
    except json.JSONDecodeError:
        _warn(f"ratchet: failed to parse ruff JSON: {r.stdout[:200]!r}")
        return None


def collect_ty() -> int | None:
    """Count ty diagnostics. Clean output is "All checks passed!"."""
    r = _run(["uv", "run", "ty", "check"])
    out = r.stdout + r.stderr
    if "All checks passed" in out:
        return 0
    m = re.search(r"Found (\d+) diagnostic", out)
    if m:
        return int(m.group(1))
    return sum(
        1 for line in out.splitlines() if re.match(r"^\s*(error|warning):", line)
    )


def collect_vulture() -> int | None:
    """Count vulture findings (one per output line)."""
    r = _run(["uv", "run", "vulture", "src", "--min-confidence", "80"])
    if r.returncode == 0:
        return 0
    if r.returncode == _VULTURE_FOUND:
        return sum(1 for line in r.stdout.splitlines() if line.strip())
    _warn(f"ratchet: vulture exit {r.returncode}: {r.stderr[:200]!r}")
    return None


def collect_import_linter() -> tuple[int, int] | None:
    """Return (kept, broken) parsed from "Contracts: N kept, M broken." line."""
    r = _run(["uv", "run", "lint-imports"])
    out = r.stdout + r.stderr
    m = re.search(r"Contracts:\s*(\d+)\s*kept,\s*(\d+)\s*broken", out)
    if not m:
        _warn(f"ratchet: failed to parse lint-imports summary: {out[-200:]!r}")
        return None
    return int(m.group(1)), int(m.group(2))


def collect_pytest_and_cov() -> tuple[int, int] | None:
    """Run pytest with coverage; return (passing, coverage_percent)."""
    r = _run(
        [
            "uv",
            "run",
            "pytest",
            "--cov=src/schematika",
            "--cov-report=term",
            "--continue-on-collection-errors",
            "-q",
        ]
    )
    out = r.stdout
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_total = re.search(r"^TOTAL\s+.*?(\d+)%\s*$", out, flags=re.MULTILINE)
    if not m_pass or not m_total:
        _warn(f"ratchet: failed to parse pytest output. tail={out[-300:]!r}")
        return None
    return int(m_pass.group(1)), int(m_total.group(1))


def load_baseline() -> dict:
    """Parse the locked-metrics TOML."""
    return tomllib.loads(BASELINE.read_text(encoding="utf-8"))


def gather(*, fast: bool) -> list[Metric] | None:
    """Collect every metric. Returns None if any collector hard-fails."""
    base = load_baseline()
    out: list[Metric] = []

    ruff = collect_ruff()
    if ruff is None:
        return None
    out.append(Metric("ruff", "max_errors", ruff, base["ruff"]["max_errors"], "le"))

    ty = collect_ty()
    if ty is None:
        return None
    out.append(Metric("ty", "max_diagnostics", ty, base["ty"]["max_diagnostics"], "le"))

    vult = collect_vulture()
    if vult is None:
        return None
    out.append(
        Metric("vulture", "max_findings", vult, base["vulture"]["max_findings"], "le")
    )

    il = collect_import_linter()
    if il is None:
        return None
    kept, broken = il
    # Broken contracts force a regression by inflating the synthetic baseline.
    il_baseline = base["import_linter"]["min_contracts_kept"]
    note = f"({broken} broken)" if broken == 0 else f"({broken} BROKEN)"
    if broken != 0:
        il_baseline += 1
    out.append(
        Metric("import_linter", "min_contracts_kept", kept, il_baseline, "ge", note)
    )

    if not fast:
        pc = collect_pytest_and_cov()
        if pc is None:
            return None
        passing, cov = pc
        out.append(
            Metric(
                "pytest", "min_passing", passing, base["pytest"]["min_passing"], "ge"
            )
        )
        out.append(
            Metric(
                "pytest",
                "min_coverage_percent",
                cov,
                base["pytest"]["min_coverage_percent"],
                "ge",
            )
        )

    return out


def _label(m: Metric) -> str:
    return f"{m.section}.{m.key}"


def cmd_check(metrics: list[Metric]) -> int:
    """Print the pass/fail table; exit 1 if anything regressed."""
    _emit(f"Ratchet check (baseline: {BASELINE.relative_to(ROOT).as_posix()})")
    _emit("─" * 53)
    width = max(len(_label(m)) for m in metrics)
    for m in metrics:
        status = "✓" if m.passed else "✗ REGRESSED"
        note = f" {m.note}" if m.note else ""
        line = (
            f"{_label(m):<{width}} {m.current:>5} {m.op} {m.baseline:<5} {status}{note}"
        )
        _emit(line)
    _emit("─" * 53)
    passed = sum(1 for m in metrics if m.passed)
    regressed = len(metrics) - passed
    _emit(f"{len(metrics)} metrics, {passed} passed, {regressed} regressed")
    return 0 if regressed == 0 else 1


HEADER = """\
# Numeric ratchet baseline — locked metrics that must never regress.
#
# Updated only via `just ratchet-update` after a deliberate improvement.
# Read by `scripts/ratchet_check.py` (run by `just ratchet` and pre-commit).
#
# When a metric improves, run `just ratchet-update` to re-pin and commit the
# new baseline as part of that improvement's PR.

[ruff]
# `uv run ruff check src tests` — total error count
max_errors = {ruff_max_errors}

[ty]
# `uv run ty check` — total diagnostic count across the repo
max_diagnostics = {ty_max_diagnostics}

[vulture]
# `uv run vulture src --min-confidence 80` — strict gate
max_findings = {vulture_max_findings}

[pytest]
# `uv run pytest --co -q` — minimum passing test count.
# Drops only allowed when tests are deliberately removed.
min_passing = {pytest_min_passing}
# `uv run pytest --cov=src/schematika --cov-report=term` — minimum coverage %.
min_coverage_percent = {pytest_min_coverage_percent}

[import_linter]
# `uv run lint-imports` — minimum kept-contracts count.
min_contracts_kept = {import_linter_min_contracts_kept}
"""


def cmd_update(metrics: list[Metric]) -> int:
    """Rewrite baseline.toml from current values; print per-key diff."""
    base = load_baseline()
    by_key = {(m.section, m.key): m for m in metrics}

    required = [
        ("ruff", "max_errors"),
        ("ty", "max_diagnostics"),
        ("vulture", "max_findings"),
        ("pytest", "min_passing"),
        ("pytest", "min_coverage_percent"),
        ("import_linter", "min_contracts_kept"),
    ]
    missing = [k for k in required if k not in by_key]
    if missing:
        _warn(f"ratchet --update needs full mode (missing: {missing})")
        return 2

    _emit(f"Ratchet update (baseline: {BASELINE.relative_to(ROOT).as_posix()})")
    for section, key in required:
        old = base[section][key]
        m = by_key[(section, key)]
        new = m.current
        if old == new:
            tag = "(unchanged)"
        else:
            improved = (m.kind == "le" and new < old) or (m.kind == "ge" and new > old)
            tag = "(improved)" if improved else "(REGRESSED)"
        _emit(f"  {section}.{key}: {old} → {new} {tag}")

    body = HEADER.format(
        ruff_max_errors=by_key[("ruff", "max_errors")].current,
        ty_max_diagnostics=by_key[("ty", "max_diagnostics")].current,
        vulture_max_findings=by_key[("vulture", "max_findings")].current,
        pytest_min_passing=by_key[("pytest", "min_passing")].current,
        pytest_min_coverage_percent=by_key[("pytest", "min_coverage_percent")].current,
        import_linter_min_contracts_kept=by_key[
            ("import_linter", "min_contracts_kept")
        ].current,
    )
    BASELINE.write_text(body, encoding="utf-8")
    return 0


def main() -> int:
    """Dispatch on mode flag."""
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--check", action="store_true", help="(default) compare against baseline."
    )
    g.add_argument(
        "--update", action="store_true", help="rewrite baseline.toml from current."
    )
    g.add_argument("--fast", action="store_true", help="--check, skip pytest+coverage.")
    args = p.parse_args()

    if not BASELINE.is_file():
        _warn(f"ratchet: missing {BASELINE}")
        return 2

    metrics = gather(fast=args.fast)
    if metrics is None:
        return 2

    if args.update:
        return cmd_update(metrics)
    return cmd_check(metrics)


if __name__ == "__main__":
    sys.exit(main())
