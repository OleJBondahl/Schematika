"""Tests for the claude-CLI-based visual reviewer (PCBV01..V05)."""

import json
import shutil
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.drawing_review.pcb_review import (
    parse_vision_response,
    run_vision_check,
)

SAMPLE_RESPONSE = json.dumps(
    {
        "PCBV01_legibility": 2,
        "PCBV02_occlusions": [],
        "PCBV03_title_block": "yes",
        "PCBV04_density": 2,
        "PCBV05_connectors_unified": "yes",
        "PCBV05_violations": [],
    }
)


def test_parse_vision_response_produces_five_findings() -> None:
    findings = parse_vision_response(SAMPLE_RESPONSE)
    codes = [f.code for f in findings]
    assert set(codes) == {"PCBV01", "PCBV02", "PCBV03", "PCBV04", "PCBV05"}


def test_run_vision_check_calls_claude_binary(tmp_path: Path) -> None:
    png = tmp_path / "page.png"
    png.write_bytes(b"fake")
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_RESPONSE
    with patch(
        "tools.drawing_review.pcb_review.subprocess.run", return_value=mock_result
    ) as mock_run:
        output = run_vision_check(png, rubric="test rubric")
    call_args = mock_run.call_args
    assert call_args[0][0][0] == "claude"
    assert call_args[0][0][1] == "-p"
    assert str(png) in call_args[0][0][2]
    assert output == SAMPLE_RESPONSE


def _make_tiny_png() -> bytes:
    """Build a minimal 1x1 white PNG without external dependencies."""
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = b"IHDR" + ihdr_data
    ihdr_crc = struct.pack(">I", zlib.crc32(ihdr))
    idat_raw = b"\x00\xff\xff\xff"
    idat_comp = zlib.compress(idat_raw)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + idat_comp))
    iend = b"IEND"
    iend_crc = struct.pack(">I", zlib.crc32(iend))

    def chunk(name: bytes, data: bytes, crc: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + crc

    return (
        header
        + chunk(b"IHDR", ihdr_data, ihdr_crc)
        + chunk(b"IDAT", idat_comp, idat_crc)
        + chunk(b"IEND", b"", iend_crc)
    )


@pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="claude CLI binary not in PATH",
)
def test_visual_review_live_call_against_fixture_png(tmp_path: Path) -> None:
    """Smoke test: render a tiny PNG through the real claude binary."""
    png = tmp_path / "fixture.png"
    png.write_bytes(_make_tiny_png())
    raw = run_vision_check(
        png,
        rubric=(
            "Return JSON with PCBV01_legibility=2, PCBV02_occlusions=[], "
            "PCBV03_title_block='yes', PCBV04_density=2, "
            "PCBV05_connectors_unified='yes', PCBV05_violations=[]."
        ),
    )
    findings = parse_vision_response(raw)
    assert len(findings) == 5
