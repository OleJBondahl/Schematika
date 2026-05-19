"""CLI: run claude-CLI vision rubric over rendered PCB schematic pages.

This module is exposed as a console script via pyproject.toml:
    schematika-pcb-review <pdf-or-png>

Does NOT import anthropic. Invokes the `claude` binary via subprocess.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity

_MIN_LEGIBILITY = 2
_MAX_DENSITY = 2
_MIN_DENSITY = 1


_RUBRIC = """\
You are reviewing a single page of an electrical schematic. Answer in JSON only.

Provide your response as JSON with these fields exactly:

{
  "PCBV01_legibility": <0-3>,
  "PCBV02_occlusions": [<list of strings>],
  "PCBV03_title_block": "yes" | "no",
  "PCBV04_density": <0-3>,
  "PCBV05_connectors_unified": "yes" | "no",
  "PCBV05_violations": [<list of strings>]
}

Do not output any text outside the JSON.
"""


def run_vision_check(png_path: Path, rubric: str) -> str:
    """Invoke `claude -p "<prompt>"` against a rendered PNG and return stdout.

    Args:
        png_path: Path to the rendered schematic PNG.
        rubric: The JSON rubric the model must answer.

    Returns:
        The raw stdout of the claude CLI invocation (expected to be JSON).
    """
    prompt = (
        f"Review the schematic image at {png_path} against this rubric: {rubric}. "
        "Return JSON only with PCBV01..V05 results."
    )
    result = subprocess.run(  # noqa: S603
        ["claude", "-p", prompt],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    return result.stdout


def parse_vision_response(raw: str) -> list[Finding]:
    """Parse the claude CLI's JSON response into 5 Findings (PCBV01..V05)."""
    # Extract JSON from markdown code blocks if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove markdown code block delimiters
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[0].startswith("```") else text
    data: dict[str, Any] = json.loads(text)
    findings: list[Finding] = []
    v01 = data.get("PCBV01_legibility", 3)
    findings.append(
        Finding(
            code="PCBV01",
            severity=Severity.WARNING if v01 < _MIN_LEGIBILITY else Severity.INFO,
            message=f"Legibility score: {v01}/3",
            location=FindingLocation(),
        )
    )
    v02 = data.get("PCBV02_occlusions", [])
    findings.append(
        Finding(
            code="PCBV02",
            severity=Severity.ERROR if v02 else Severity.INFO,
            message=f"Occlusions: {v02 or 'none'}",
            location=FindingLocation(),
        )
    )
    v03 = data.get("PCBV03_title_block", "yes")
    findings.append(
        Finding(
            code="PCBV03",
            severity=Severity.ERROR if v03 != "yes" else Severity.INFO,
            message=f"Title block: {v03}",
            location=FindingLocation(),
        )
    )
    v04 = data.get("PCBV04_density", 2)
    findings.append(
        Finding(
            code="PCBV04",
            severity=(
                Severity.WARNING
                if v04 < _MIN_DENSITY or v04 > _MAX_DENSITY
                else Severity.INFO
            ),
            message=f"Density score: {v04}/3",
            location=FindingLocation(),
        )
    )
    v05 = data.get("PCBV05_connectors_unified", "yes")
    v05_violations = data.get("PCBV05_violations", [])
    v05_msg = f"Connectors unified: {v05}. Violations: {v05_violations or 'none'}"
    findings.append(
        Finding(
            code="PCBV05",
            severity=Severity.ERROR if v05 != "yes" else Severity.INFO,
            message=v05_msg,
            location=FindingLocation(),
        )
    )
    return findings


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="PDF or PNG schematic page")
    args = parser.parse_args()
    raw = run_vision_check(args.input, _RUBRIC)
    findings = parse_vision_response(raw)
    for f in findings:
        print(  # noqa: T201
            f"[{f.severity.value.upper()}] {f.code}: {f.message}"
        )
    if any(f.severity is Severity.ERROR for f in findings):
        sys.exit(1)


if __name__ == "__main__":
    main()
