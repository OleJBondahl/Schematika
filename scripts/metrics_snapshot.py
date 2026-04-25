"""Non-blocking metrics snapshot — capture every measurement for trend tracking.

Always exits 0. Records all metrics (ruff, ty, vulture, complexity peaks,
suppressions, pytest, scc) into a timestamped TOML under docs/ratchet/snapshots/.
Failed collectors set their keys to -1 and add an error log entry.

Usage:
    uv run python scripts/metrics_snapshot.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = ROOT / "docs" / "ratchet" / "snapshots"

# Complexity thresholds for distribution counting
COMPLEXITY_THRESHOLD = 10
ARGS_THRESHOLD = 8
BRANCHES_THRESHOLD = 12
STATEMENTS_THRESHOLD = 50
RETURNS_THRESHOLD = 6


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run fully-formed argv. errors='replace' survives Windows cp1252 mojibake."""
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        encoding="utf-8",
        errors="replace",
    )


def _git_info() -> dict[str, str | bool]:
    """Extract branch, short SHA, and dirty status."""
    r_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    r_sha = _run(["git", "rev-parse", "--short", "HEAD"])
    r_dirty = _run(["git", "status", "--porcelain"])
    return {
        "git_branch": r_branch.stdout.strip() or "unknown",
        "git_sha": r_sha.stdout.strip() or "unknown",
        "git_dirty": bool(r_dirty.stdout.strip()),
    }


def _collect_ruff_errors() -> int:
    """Count total ruff errors."""
    r = _run(["uv", "run", "ruff", "check", "src", "tests", "--output-format=json"])
    try:
        return len(json.loads(r.stdout or "[]"))
    except (json.JSONDecodeError, ValueError):
        return -1


def _collect_ruff_format_dirty() -> int:
    """Count files needing ruff format."""
    r = _run(["uv", "run", "ruff", "format", "--check", "src", "tests"])
    if r.returncode == 0:
        return 0
    return sum(1 for line in r.stdout.splitlines() if "would reformat" in line)


def _collect_ty() -> int:
    """Count ty diagnostics."""
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


def _collect_vulture(confidence: int) -> int:
    """Count vulture findings at given confidence level."""
    r = _run(["uv", "run", "vulture", "src", "--min-confidence", str(confidence)])
    if r.returncode == 0:
        return 0
    if r.returncode in (2, 3):  # exit codes when findings exist
        return sum(1 for line in r.stdout.splitlines() if line.strip())
    return -1


def _collect_import_linter() -> tuple[int, int]:
    """Return (kept, broken) contracts."""
    r = _run(["uv", "run", "lint-imports"])
    out = r.stdout + r.stderr
    m = re.search(r"Contracts:\s*(\d+)\s*kept,\s*(\d+)\s*broken", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return -1, -1


def _extract_peaks_and_distribution() -> dict:
    """Run lowered-threshold ruff checks; parse peaks and distributions."""
    rules = [
        ("C901", "mccabe.max-complexity", "10"),
        ("PLR0913", "pylint.max-args", "8"),
        ("PLR0912", "pylint.max-branches", "12"),
        ("PLR0915", "pylint.max-statements", "50"),
        ("PLR0911", "pylint.max-returns", "6"),
    ]
    peaks = {
        "max_complexity": -1,
        "max_complexity_function": "",
        "max_args": -1,
        "max_args_function": "",
        "max_branches": -1,
        "max_branches_function": "",
        "max_statements": -1,
        "max_statements_function": "",
        "max_returns": -1,
        "max_returns_function": "",
    }
    distribution = {
        "above_complexity_10": 0,
        "above_args_8": 0,
        "above_branches_12": 0,
        "above_statements_50": 0,
        "above_returns_6": 0,
    }

    for rule, config_key, threshold in rules:
        cmd = [
            "uv",
            "run",
            "ruff",
            "check",
            "src",
            f"--select={rule}",
            f"--config=lint.{config_key}={threshold}",
            "--output-format=json",
        ]
        r = _run(cmd)
        try:
            data = json.loads(r.stdout or "[]")
        except (json.JSONDecodeError, ValueError):
            continue

        for entry in data:
            msg = entry.get("message", "")
            m_val = re.search(r"\((\d+)\s*>", msg)
            if not m_val:
                continue
            val = int(m_val.group(1))

            # Distribution count
            dist_map = {
                "C901": ("above_complexity_10", COMPLEXITY_THRESHOLD),
                "PLR0913": ("above_args_8", ARGS_THRESHOLD),
                "PLR0912": ("above_branches_12", BRANCHES_THRESHOLD),
                "PLR0915": ("above_statements_50", STATEMENTS_THRESHOLD),
                "PLR0911": ("above_returns_6", RETURNS_THRESHOLD),
            }
            if rule in dist_map:
                dist_key, dist_threshold = dist_map[rule]
                if val > dist_threshold:
                    distribution[dist_key] += 1

            # Peak tracking
            peak_key = {
                "C901": "max_complexity",
                "PLR0913": "max_args",
                "PLR0912": "max_branches",
                "PLR0915": "max_statements",
                "PLR0911": "max_returns",
            }.get(rule)
            if peak_key and val > int(peaks[peak_key]):
                peaks[peak_key] = val
                # Extract function name from source file
                file_path = ROOT / entry["filename"]
                row = entry["location"]["row"]
                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    for i in range(row - 1, -1, -1):
                        if re.match(r"^\s*(async\s+)?def\s+(\w+)", lines[i]):
                            m_func = re.search(r"def\s+(\w+)", lines[i])
                            peaks[f"{peak_key}_function"] = (
                                m_func.group(1) if m_func else ""
                            )
                            break
                except (OSError, IndexError, AttributeError):
                    pass

    return {"peaks": peaks, "distribution": distribution}


def _count_suppressions() -> dict[str, int]:
    """Count suppression markers in .py files."""
    counts = {
        "noqa": 0,
        "ty_ignore": 0,
        "type_ignore_legacy": 0,
        "todo_markers": 0,
    }
    for py_file in ROOT.rglob("*.py"):
        if "/.git/" in str(py_file) or "/__pycache__/" in str(py_file):
            continue
        if not any(
            str(py_file).startswith(str(d))
            for d in [ROOT / "src", ROOT / "tests", ROOT / "scripts"]
        ):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
            counts["noqa"] += len(re.findall(r"# noqa:?", text))
            counts["ty_ignore"] += len(re.findall(r"# ty: ignore", text))
            counts["type_ignore_legacy"] += len(re.findall(r"# type: ignore", text))
            counts["todo_markers"] += len(
                re.findall(r"\b(TODO|FIXME|HACK|XXX)\b", text)
            )
        except OSError:
            pass
    return counts


def _collect_pytest_and_cov() -> tuple[int, int, int]:
    """Run pytest; return (collected, passed, coverage_percent)."""
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
    m_collected = re.search(r"(\d+)\s+collected", out)
    m_passed = re.search(r"(\d+)\s+passed", out)
    m_cov = re.search(r"^TOTAL\s+.*?(\d+)%\s*$", out, flags=re.MULTILINE)

    collected = int(m_collected.group(1)) if m_collected else -1
    passed = int(m_passed.group(1)) if m_passed else -1
    cov = int(m_cov.group(1)) if m_cov else -1
    return collected, passed, cov


def _collect_scc() -> tuple[int, int, int]:
    """Run scc; return (src_loc, src_complexity, total_loc)."""
    import shutil

    if not shutil.which("scc"):
        return -1, -1, -1

    r = _run(["scc", "src", "tests", "scripts", "--format=json"])
    try:
        data = json.loads(r.stdout or "[]")
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        return -1, -1, -1

    if not data:
        return -1, -1, -1

    # scc returns a list of language entries. Python is the main language.
    python_entry = next((e for e in data if e.get("Name") == "Python"), None)
    if not python_entry:
        return -1, -1, -1

    src_loc = python_entry.get("Code", -1)
    src_complex = python_entry.get("Complexity", -1)
    total_loc = sum(int(e.get("Code", 0)) for e in data)
    return src_loc, src_complex, total_loc


def _count_all_declarations() -> int:
    """Count __all__ = ... lines in src/."""
    count = 0
    for py_file in (ROOT / "src").rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
            count += len(re.findall(r"^__all__\s*=", text, re.MULTILINE))
        except OSError:
            pass
    return count


def _count_python_files(subdir: str) -> int:
    """Count .py files in a subdirectory."""
    return len(list((ROOT / subdir).rglob("*.py")))


def _build_toml_content(
    meta_timestamp: str,
    git_info: dict,
    errors: list[str],
    metrics: dict,
) -> str:
    """Build TOML content from collected metrics."""
    dist = metrics["complexity"]["distribution"]
    peaks = metrics["complexity"]["peaks"]
    lines = [
        "[meta]",
        f'timestamp = "{meta_timestamp}"',
        f'git_branch = "{git_info["git_branch"]}"',
        f'git_sha = "{git_info["git_sha"]}"',
        f"git_dirty = {str(git_info['git_dirty']).lower()}",
    ]
    if errors:
        error_list = '", "'.join(errors)
        lines.append(f'errors = ["{error_list}"]')

    lines.append("")
    lines.append("[lint]")
    lines.append(f"ruff_errors = {metrics['ruff_err']}")
    lines.append(f"ruff_format_dirty_files = {metrics['ruff_fmt']}")
    lines.append(f"ty_diagnostics = {metrics['ty']}")
    lines.append(f"vulture_findings_at_80 = {metrics['vult_80']}")
    lines.append(f"vulture_findings_at_60 = {metrics['vult_60']}")
    lines.append(f"import_linter_contracts_kept = {metrics['il_kept']}")
    lines.append(f"import_linter_contracts_broken = {metrics['il_broken']}")

    lines.append("")
    lines.append("[complexity.distribution]")
    lines.append(f"above_complexity_10 = {dist['above_complexity_10']}")
    lines.append(f"above_args_8 = {dist['above_args_8']}")
    lines.append(f"above_branches_12 = {dist['above_branches_12']}")
    lines.append(f"above_statements_50 = {dist['above_statements_50']}")
    lines.append(f"above_returns_6 = {dist['above_returns_6']}")

    lines.append("")
    lines.append("[complexity.peaks]")
    lines.append(f"max_complexity = {peaks['max_complexity']}")
    lines.append(f'max_complexity_function = "{peaks["max_complexity_function"]}"')
    lines.append(f"max_args = {peaks['max_args']}")
    lines.append(f'max_args_function = "{peaks["max_args_function"]}"')
    lines.append(f"max_branches = {peaks['max_branches']}")
    lines.append(f'max_branches_function = "{peaks["max_branches_function"]}"')
    lines.append(f"max_statements = {peaks['max_statements']}")
    lines.append(f'max_statements_function = "{peaks["max_statements_function"]}"')
    lines.append(f"max_returns = {peaks['max_returns']}")
    lines.append(f'max_returns_function = "{peaks["max_returns_function"]}"')

    lines.append("")
    lines.append("[suppressions]")
    lines.append(f"noqa = {metrics['suppressions']['noqa']}")
    lines.append(f"ty_ignore = {metrics['suppressions']['ty_ignore']}")
    lines.append(
        f"type_ignore_legacy = {metrics['suppressions']['type_ignore_legacy']}"
    )
    lines.append(f"todo_markers = {metrics['suppressions']['todo_markers']}")

    lines.append("")
    lines.append("[tests]")
    lines.append(f"collected = {metrics['collected']}")
    lines.append(f"passed = {metrics['passed']}")
    lines.append(f"coverage_percent = {metrics['cov']}")

    lines.append("")
    lines.append("[codebase]")
    lines.append(f"src_loc = {metrics['src_loc']}")
    lines.append(f"src_complexity_scc = {metrics['src_complex']}")
    lines.append(f"total_loc = {metrics['total_loc']}")
    lines.append(f"python_files_src = {metrics['python_files']}")
    lines.append(f"all_declarations = {metrics['all_decls']}")

    return "\n".join(lines) + "\n"


def generate_snapshot() -> str:
    """Collect all metrics and write TOML snapshot."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=UTC).astimezone()
    timestamp = ts.strftime("%Y-%m-%dT%H%M%S")
    meta_timestamp = ts.strftime("%Y-%m-%dT%H:%M:%S")

    git_info = _git_info()
    errors: list[str] = []

    # Collect lint metrics
    ruff_err = _collect_ruff_errors()
    ruff_fmt = _collect_ruff_format_dirty()
    ty = _collect_ty()
    vult_80 = _collect_vulture(80)
    vult_60 = _collect_vulture(60)
    il_kept, il_broken = _collect_import_linter()

    if ruff_err == -1:
        errors.append("ruff check: parse error")
    if ruff_fmt == -1:
        errors.append("ruff format check: parse error")
    if ty == -1:
        errors.append("ty check: parse error")
    if vult_80 == -1:
        errors.append("vulture @80: exit error")
    if vult_60 == -1:
        errors.append("vulture @60: exit error")
    if il_kept == -1 or il_broken == -1:
        errors.append("import-linter: parse error")

    complexity = _extract_peaks_and_distribution()
    suppressions = _count_suppressions()
    collected, passed, cov = _collect_pytest_and_cov()

    if collected == -1:
        errors.append("pytest: collection error")
    if passed == -1:
        errors.append("pytest: parse error")
    if cov == -1:
        errors.append("coverage: parse error")

    src_loc, src_complex, total_loc = _collect_scc()
    if src_loc == -1:
        errors.append("scc: missing or parse error")

    python_files = _count_python_files("src")
    all_decls = _count_all_declarations()

    metrics_dict = {
        "ruff_err": ruff_err,
        "ruff_fmt": ruff_fmt,
        "ty": ty,
        "vult_80": vult_80,
        "vult_60": vult_60,
        "il_kept": il_kept,
        "il_broken": il_broken,
        "complexity": complexity,
        "suppressions": suppressions,
        "collected": collected,
        "passed": passed,
        "cov": cov,
        "src_loc": src_loc,
        "src_complex": src_complex,
        "total_loc": total_loc,
        "python_files": python_files,
        "all_decls": all_decls,
    }

    toml_content = _build_toml_content(meta_timestamp, git_info, errors, metrics_dict)
    snapshot_path = SNAPSHOTS_DIR / f"{timestamp}.toml"
    snapshot_path.write_text(toml_content, encoding="utf-8")

    return str(snapshot_path)


def main() -> int:
    """Generate snapshot and print path. Always exit 0."""
    try:
        path = generate_snapshot()
        sys.stdout.write(f"{path}\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"metrics_snapshot: {e}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
