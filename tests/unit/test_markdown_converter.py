"""Tests for the Markdown to Typst converter."""

import tempfile
from pathlib import Path

from schematika.rendering.typst.markdown_converter import (
    markdown_to_typst,
)


def _write_md(tmpdir, content):
    """Helper to write a temporary MD file."""
    path = str(Path(tmpdir) / "test.md")
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_missing_file_returns_empty():
    """Missing MD file should return empty string."""
    result = markdown_to_typst("/nonexistent/file.md")
    assert result == ""


def test_heading_conversion():
    """Markdown headings should convert to Typst headings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_md(tmpdir, "# Title\n\n## Subtitle\n\n### Section\n")
        result = markdown_to_typst(path)
        assert "= Title" in result
        assert "== Subtitle" in result
        assert "=== Section" in result


def test_paragraph_conversion():
    """Plain text should convert to Typst paragraphs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_md(tmpdir, "Hello world\n")
        result = markdown_to_typst(path)
        assert "Hello world" in result
        assert "#parbreak()" in result


def test_table_conversion():
    """Markdown tables should convert to Typst tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        path = _write_md(tmpdir, md)
        result = markdown_to_typst(path)
        assert "#table(" in result
        assert "[A]," in result
        assert "[1]," in result


def test_pagebreak_appended():
    """Output should end with a pagebreak."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_md(tmpdir, "Hello\n")
        result = markdown_to_typst(path)
        assert "#pagebreak()" in result


def test_notice_block():
    """Notice parameter should add a notice block."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_md(tmpdir, "Hello\n")
        result = markdown_to_typst(path, notice="CONFIDENTIAL")
        assert "CONFIDENTIAL" in result
        assert "luma(240)" in result  # notice block styling


def test_no_notice_by_default():
    """No notice should be added when not specified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_md(tmpdir, "Hello\n")
        result = markdown_to_typst(path)
        assert "luma(240)" not in result


def test_custom_width():
    """Custom width parameter should be used."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_md(tmpdir, "Hello\n")
        result = markdown_to_typst(path, width="80%")
        assert "80%" in result
