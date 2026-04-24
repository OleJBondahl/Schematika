"""Tests for the Typst rendering modules: compiler, frame_generator, markdown_converter."""

import os
import tempfile
from unittest.mock import patch

import pytest

from schematika.electrical.model.primitives import Line, Text
from schematika.rendering.typst.compiler import (
    TypstCompiler,
    TypstCompilerConfig,
    _Page,
)
from schematika.rendering.typst.frame_generator import (
    A3_HEIGHT,
    A3_WIDTH,
    CONTENT_HEIGHT,
    CONTENT_WIDTH,
    INNER_FRAME_X1,
    INNER_FRAME_X2,
    INNER_FRAME_Y1,
    INNER_FRAME_Y2,
    generate_frame,
)
from schematika.rendering.typst.markdown_converter import (
    _convert_lines,
    _flush_table,
    _notice_block,
    markdown_to_typst,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_compiler(tmpdir, **config_kwargs):
    """Create a TypstCompiler with a temp root_dir and template in place."""
    defaults = {
        "drawing_name": "Test",
        "drawing_number": "T-001",
        "author": "Author",
        "project": "Project",
        "root_dir": tmpdir,
        "temp_dir": "temp",
    }
    defaults.update(config_kwargs)
    config = TypstCompilerConfig(**defaults)
    compiler = TypstCompiler(config)

    # Prepare temp dir and copy template so _build_typst_content works
    temp_dir = os.path.join(tmpdir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    frame_path = os.path.join(temp_dir, "A3_frame.svg")
    template_src = compiler._get_template_path()
    template_dest = os.path.join(temp_dir, "a3_drawing.typ")
    with open(template_src, encoding="utf-8") as f:
        content = f.read()
    with open(template_dest, "w", encoding="utf-8") as f:
        f.write(content)

    return compiler, frame_path, template_dest


# ===========================================================================
# TypstCompilerConfig tests
# ===========================================================================


class TestTypstCompilerConfig:
    def test_config_defaults(self):
        """TypstCompilerConfig should have sensible defaults."""
        config = TypstCompilerConfig()
        assert config.drawing_name == ""
        assert config.drawing_number == ""
        assert config.font_family == "Times New Roman"
        assert config.root_dir == "."
        assert config.temp_dir == "temp"
        assert config.logo_path is None

    def test_config_custom_values(self):
        """TypstCompilerConfig should accept custom values."""
        config = TypstCompilerConfig(
            drawing_name="Test Drawing",
            drawing_number="TST-001",
            author="Test Author",
            project="Test Project",
            revision="A1",
            logo_path="/path/to/logo.png",
            font_family="Arial",
        )
        assert config.drawing_name == "Test Drawing"
        assert config.drawing_number == "TST-001"
        assert config.font_family == "Arial"
        assert config.logo_path == "/path/to/logo.png"

    def test_config_default_revision(self):
        """Default revision should be '00'."""
        config = TypstCompilerConfig()
        assert config.revision == "00"

    def test_config_default_author(self):
        """Default author should be empty string."""
        config = TypstCompilerConfig()
        assert config.author == ""

    def test_config_default_project(self):
        """Default project should be empty string."""
        config = TypstCompilerConfig()
        assert config.project == ""


# ===========================================================================
# Page registration tests
# ===========================================================================


class TestPageRegistration:
    def test_add_schematic_page(self):
        """Adding a schematic page should be recorded."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_schematic_page("Test Page", "test.svg", "test_terminals.csv")
        assert len(compiler._pages) == 1
        assert compiler._pages[0].page_type == "schematic"
        assert compiler._pages[0].title == "Test Page"

    def test_add_schematic_page_without_csv(self):
        """Schematic page without CSV should store empty terminals_csv_path."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_schematic_page("Page", "test.svg")
        assert compiler._pages[0].terminals_csv_path == ""

    def test_add_schematic_page_with_csv(self):
        """Schematic page with CSV should store the path."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_schematic_page("Page", "test.svg", "terms.csv")
        assert compiler._pages[0].terminals_csv_path == "terms.csv"

    def test_add_front_page(self):
        """Adding a front page should be recorded."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_front_page("test.md")
        assert len(compiler._pages) == 1
        assert compiler._pages[0].page_type == "front"

    def test_add_front_page_with_notice(self):
        """Front page should store the notice parameter."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_front_page("test.md", notice="Important notice")
        assert compiler._pages[0].notice == "Important notice"

    def test_add_front_page_without_notice(self):
        """Front page without notice should have None."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_front_page("test.md")
        assert compiler._pages[0].notice is None

    def test_add_terminal_report(self):
        """Adding a terminal report should be recorded."""
        descriptions = {"X1": "Main Power", "X2": "AC Input"}
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_terminal_report("system.csv", descriptions)
        assert len(compiler._pages) == 1
        assert compiler._pages[0].page_type == "terminal_report"
        assert compiler._pages[0].terminal_titles == descriptions

    def test_add_plc_report(self):
        """Adding a PLC report should be recorded."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_plc_report("plc.csv")
        assert len(compiler._pages) == 1
        assert compiler._pages[0].page_type == "plc_report"

    def test_add_custom_page(self):
        """Adding a custom page should be recorded."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_custom_page("Custom", "#text[Hello]")
        assert len(compiler._pages) == 1
        assert compiler._pages[0].page_type == "custom"
        assert compiler._pages[0].typst_content == "#text[Hello]"

    def test_multiple_pages(self):
        """Compiler should handle multiple pages in order."""
        compiler = TypstCompiler(TypstCompilerConfig())
        compiler.add_schematic_page("Page 1", "p1.svg")
        compiler.add_schematic_page("Page 2", "p2.svg", "p2.csv")
        compiler.add_custom_page("Notes", "#text[Notes]")
        assert len(compiler._pages) == 3
        assert compiler._pages[0].title == "Page 1"
        assert compiler._pages[1].title == "Page 2"
        assert compiler._pages[2].title == "Notes"


# ===========================================================================
# _rel_path tests
# ===========================================================================


class TestRelPath:
    def test_relative_path_unchanged(self):
        """A relative path should be returned as-is (with forward slashes)."""
        compiler = TypstCompiler(TypstCompilerConfig(root_dir="/some/root"))
        result = compiler._rel_path("temp/test.svg")
        assert result == "temp/test.svg"

    def test_backslashes_converted(self):
        """Backslashes in relative paths should be converted to forward slashes."""
        compiler = TypstCompiler(TypstCompilerConfig(root_dir="/some/root"))
        result = compiler._rel_path("temp\\sub\\test.svg")
        assert "\\" not in result
        assert result == "temp/sub/test.svg"

    def test_absolute_path_made_relative(self):
        """An absolute path should be made relative to root_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler = TypstCompiler(TypstCompilerConfig(root_dir=tmpdir))
            abs_path = os.path.join(tmpdir, "temp", "file.svg")
            result = compiler._rel_path(abs_path)
            assert "\\" not in result
            assert result == "temp/file.svg"

    def test_absolute_path_outside_root(self):
        """An absolute path outside root should still produce a relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler = TypstCompiler(TypstCompilerConfig(root_dir=tmpdir))
            abs_path = os.path.abspath("/some/other/dir/file.svg")
            result = compiler._rel_path(abs_path)
            # Should still be a string with forward slashes
            assert "\\" not in result
            assert isinstance(result, str)


# ===========================================================================
# _render_page dispatch tests
# ===========================================================================


class TestRenderPageDispatch:
    def test_dispatch_schematic(self):
        """_render_page should dispatch to _render_schematic_page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, _, _ = _make_compiler(tmpdir)
            page = _Page(page_type="schematic", title="Schematic", svg_path="test.svg")
            result = compiler._render_page(page)
            assert 'schematic("test.svg"' in result
            assert "Schematic" in result

    def test_dispatch_front(self):
        """_render_page should dispatch to _render_front_page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, _, _ = _make_compiler(tmpdir)
            # Create a dummy markdown file
            md_path = os.path.join(tmpdir, "front.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Title\n\nHello world\n")
            page = _Page(page_type="front", md_path=md_path)
            result = compiler._render_page(page)
            assert "Title" in result
            assert "#pagebreak()" in result

    def test_dispatch_plc_report(self):
        """_render_page should dispatch to _render_plc_report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, _, _ = _make_compiler(tmpdir)
            page = _Page(page_type="plc_report", csv_path="plc_data.csv")
            result = compiler._render_page(page)
            assert "plc_data.csv" in result
            assert "PLC" in result

    def test_dispatch_terminal_report(self):
        """_render_page should dispatch to _render_terminal_report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, _, _ = _make_compiler(tmpdir)
            page = _Page(
                page_type="terminal_report",
                csv_path="terms.csv",
                terminal_titles={"X1": "Power"},
            )
            result = compiler._render_page(page)
            assert "terms.csv" in result
            assert "X1" in result

    def test_dispatch_custom(self):
        """_render_page should dispatch to _render_custom_page."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="custom", title="Notes", typst_content="#text[Hello]")
        result = compiler._render_page(page)
        assert "#text[Hello]" in result
        assert "Notes" in result

    def test_dispatch_unknown_returns_empty(self):
        """_render_page with unknown page_type should return empty string."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="unknown_type")
        result = compiler._render_page(page)
        assert result == ""


# ===========================================================================
# _render_schematic_page tests
# ===========================================================================


class TestRenderSchematicPage:
    def test_without_terminals_csv(self):
        """Schematic page without terminal CSV should not include terminals_csv arg."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="schematic",
            title="Motor",
            svg_path="motor.svg",
            terminals_csv_path="",
        )
        result = compiler._render_schematic_page(page)
        assert 'schematic("motor.svg"' in result
        assert 'title: "Motor"' in result
        assert "terminals_csv" not in result
        assert "#pagebreak()" in result

    def test_with_terminals_csv(self):
        """Schematic page with terminal CSV should include terminals_csv arg."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="schematic",
            title="Motor",
            svg_path="motor.svg",
            terminals_csv_path="motor_terms.csv",
        )
        result = compiler._render_schematic_page(page)
        assert 'terminals_csv: "motor_terms.csv"' in result
        assert 'title: "Motor"' in result
        assert "#pagebreak()" in result

    def test_page_comment_includes_title(self):
        """The rendered output should contain a comment with the page title."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="schematic",
            title="Control Circuit",
            svg_path="ctrl.svg",
        )
        result = compiler._render_schematic_page(page)
        assert "// Page: Control Circuit" in result


# ===========================================================================
# _render_front_page tests
# ===========================================================================


class TestRenderFrontPage:
    def test_with_valid_markdown(self):
        """Front page should render markdown content to Typst."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "front.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Main Title\n\nSome description\n")
            compiler = TypstCompiler(TypstCompilerConfig())
            page = _Page(page_type="front", md_path=md_path)
            result = compiler._render_front_page(page)
            assert "= Main Title" in result
            assert "Some description" in result
            assert "#pagebreak()" in result

    def test_with_notice(self):
        """Front page with notice should include the notice block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "front.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Title\n")
            compiler = TypstCompiler(TypstCompilerConfig())
            page = _Page(page_type="front", md_path=md_path, notice="Legal notice")
            result = compiler._render_front_page(page)
            assert "Legal notice" in result

    def test_with_missing_file(self):
        """Front page with missing file should return empty string."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="front", md_path="/nonexistent/path.md")
        result = compiler._render_front_page(page)
        assert result == ""


# ===========================================================================
# _render_plc_report tests
# ===========================================================================


class TestRenderPlcReport:
    def test_csv_path_substituted(self):
        """PLC report should replace __CSV_PATH__ with the actual path."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="plc_report", csv_path="data/plc.csv")
        result = compiler._render_plc_report(page)
        assert "data/plc.csv" in result
        assert "__CSV_PATH__" not in result

    def test_contains_plc_title(self):
        """PLC report should contain the PLC I/O Connections title."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="plc_report", csv_path="plc.csv")
        result = compiler._render_plc_report(page)
        assert "PLC I/O Connections" in result

    def test_contains_pagebreak(self):
        """PLC report should end with a pagebreak."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="plc_report", csv_path="plc.csv")
        result = compiler._render_plc_report(page)
        assert "#pagebreak()" in result


# ===========================================================================
# _render_terminal_report tests
# ===========================================================================


class TestRenderTerminalReport:
    def test_csv_path_substituted(self):
        """Terminal report should replace __CSV_PATH__."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="terminal_report",
            csv_path="terms.csv",
            terminal_titles={"X1": "Power"},
        )
        result = compiler._render_terminal_report(page)
        assert "terms.csv" in result
        assert "__CSV_PATH__" not in result

    def test_descriptions_map_substituted(self):
        """Terminal report should replace __DESC_MAP__ with Typst map."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="terminal_report",
            csv_path="terms.csv",
            terminal_titles={"X1": "Power Supply", "X2": "Control"},
        )
        result = compiler._render_terminal_report(page)
        assert "__DESC_MAP__" not in result
        assert '"X1": "Power Supply"' in result
        assert '"X2": "Control"' in result
        assert "#let terminal_titles" in result

    def test_description_with_quotes_escaped(self):
        """Descriptions containing double quotes should be escaped."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="terminal_report",
            csv_path="terms.csv",
            terminal_titles={"X1": 'Main "power" input'},
        )
        result = compiler._render_terminal_report(page)
        assert r"Main \"power\" input" in result

    def test_empty_descriptions(self):
        """Terminal report with empty descriptions should still render."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="terminal_report",
            csv_path="terms.csv",
            terminal_titles={},
        )
        result = compiler._render_terminal_report(page)
        assert "#let terminal_titles" in result
        assert "terms.csv" in result

    def test_none_descriptions_defaults_to_empty(self):
        """Terminal report with None descriptions should use empty dict."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="terminal_report",
            csv_path="terms.csv",
            terminal_titles=None,
        )
        result = compiler._render_terminal_report(page)
        assert "#let terminal_titles" in result

    def test_contains_system_terminal_report_title(self):
        """Terminal report should contain the title text."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(
            page_type="terminal_report",
            csv_path="terms.csv",
            terminal_titles={},
        )
        result = compiler._render_terminal_report(page)
        assert "System Terminal Report" in result


# ===========================================================================
# _render_custom_page tests
# ===========================================================================


class TestRenderCustomPage:
    def test_with_title(self):
        """Custom page with title should include a comment with the title."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="custom", title="Notes", typst_content="#text[Notes]")
        result = compiler._render_custom_page(page)
        assert "Custom Page: Notes" in result
        assert "#text[Notes]" in result
        assert "#pagebreak(weak: true)" in result

    def test_without_title(self):
        """Custom page without title should not include a comment line."""
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="custom", title="", typst_content="#text[Raw]")
        result = compiler._render_custom_page(page)
        assert "Custom Page:" not in result
        assert "#text[Raw]" in result
        assert "#pagebreak(weak: true)" in result

    def test_content_preserved(self):
        """Custom page should preserve the exact Typst content."""
        content = "#grid(columns: 2)[A][B]"
        compiler = TypstCompiler(TypstCompilerConfig())
        page = _Page(page_type="custom", title="Grid", typst_content=content)
        result = compiler._render_custom_page(page)
        assert content in result


# ===========================================================================
# _build_typst_content tests
# ===========================================================================


class TestBuildTypstContent:
    def test_basic_content(self):
        """_build_typst_content should generate valid Typst markup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, frame_path, template_dest = _make_compiler(tmpdir)
            compiler.add_schematic_page("Motor Circuit", "test.svg")

            result = compiler._build_typst_content(frame_path, template_dest)

            assert "#import" in result
            assert "a3_drawing" in result
            assert "T-001" in result
            assert "Motor Circuit" in result
            assert 'schematic("test.svg"' in result

    def test_logo_path_none(self):
        """When logo_path is None, logo_arg should be 'none'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, frame_path, template_dest = _make_compiler(tmpdir)
            result = compiler._build_typst_content(frame_path, template_dest)
            assert "logo_path: none" in result

    def test_logo_path_set(self):
        """When logo_path is set, it should appear as a quoted relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy logo file
            logo_path = os.path.join(tmpdir, "logo.png")
            with open(logo_path, "w") as f:
                f.write("dummy")

            compiler, frame_path, template_dest = _make_compiler(
                tmpdir, logo_path=logo_path
            )
            result = compiler._build_typst_content(frame_path, template_dest)
            # Should NOT be 'none', should be a quoted path
            assert 'logo_path: "' in result
            assert "logo_path: none" not in result

    def test_all_config_fields_appear(self):
        """All config fields should appear in the generated content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, frame_path, template_dest = _make_compiler(
                tmpdir,
                drawing_name="Motor Starter",
                drawing_number="DWG-042",
                author="John Doe",
                project="Factory X",
                revision="B2",
                font_family="Arial",
            )
            result = compiler._build_typst_content(frame_path, template_dest)
            assert 'drawing_number: "DWG-042"' in result
            assert 'drawing_name: "Motor Starter"' in result
            assert 'author: "John Doe"' in result
            assert 'project: "Factory X"' in result
            assert 'revision: "B2"' in result
            assert 'font_family: "Arial"' in result

    def test_multiple_page_types_rendered(self):
        """Build content with mixed page types should include all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, frame_path, template_dest = _make_compiler(tmpdir)
            compiler.add_schematic_page("Page 1", "p1.svg")
            compiler.add_custom_page("Notes", "#text[N]")

            result = compiler._build_typst_content(frame_path, template_dest)
            assert 'schematic("p1.svg"' in result
            assert "#text[N]" in result

    def test_frame_path_in_content(self):
        """The frame SVG path should appear in the content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, frame_path, template_dest = _make_compiler(tmpdir)
            result = compiler._build_typst_content(frame_path, template_dest)
            assert "frame_path:" in result

    def test_clip_dimensions(self):
        """Content should contain clip dimensions derived from frame geometry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler, frame_path, template_dest = _make_compiler(tmpdir)
            result = compiler._build_typst_content(frame_path, template_dest)
            expected_clip_width = CONTENT_WIDTH - 2  # 398mm
            expected_clip_height = CONTENT_HEIGHT - 2  # 275mm
            assert f"{expected_clip_width}mm" in result
            assert f"{expected_clip_height}mm" in result


# ===========================================================================
# compile() tests
# ===========================================================================


class TestCompile:
    def test_compile_raises_import_error_when_typst_missing(self):
        """compile() should raise ImportError when typst package is missing."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "typst":
                raise ImportError("No module named 'typst'")
            return original_import(name, *args, **kwargs)

        compiler = TypstCompiler(TypstCompilerConfig())
        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="typst"):
                compiler.compile("output.pdf")

    def test_compile_error_message_mentions_pip(self):
        """The ImportError message should tell users how to install typst."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "typst":
                raise ImportError("No module named 'typst'")
            return original_import(name, *args, **kwargs)

        compiler = TypstCompiler(TypstCompilerConfig())
        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="pip install"):
                compiler.compile("output.pdf")


# ===========================================================================
# _get_template_path tests
# ===========================================================================


class TestGetTemplatePath:
    def test_template_file_exists(self):
        """The a3_drawing.typ template should exist in the package."""
        compiler = TypstCompiler(TypstCompilerConfig())
        path = compiler._get_template_path()
        assert os.path.exists(path), f"Template not found at {path}"

    def test_template_path_ends_with_typ(self):
        """Template path should end with a3_drawing.typ."""
        compiler = TypstCompiler(TypstCompilerConfig())
        path = compiler._get_template_path()
        assert path.endswith("a3_drawing.typ")

    def test_template_in_templates_directory(self):
        """Template should be in a 'templates' subdirectory."""
        compiler = TypstCompiler(TypstCompilerConfig())
        path = compiler._get_template_path()
        parent = os.path.basename(os.path.dirname(path))
        assert parent == "templates"


# ===========================================================================
# markdown_converter tests
# ===========================================================================


class TestMarkdownToTypst:
    def test_happy_path(self):
        """markdown_to_typst should convert a real markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "test.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Heading\n\nParagraph text\n")

            result = markdown_to_typst(md_path)
            assert "= Heading" in result
            assert "Paragraph text" in result
            assert "#pagebreak()" in result

    def test_file_not_found_returns_empty(self):
        """markdown_to_typst should return empty string for missing file."""
        result = markdown_to_typst("/nonexistent/path.md")
        assert result == ""

    def test_with_notice(self):
        """markdown_to_typst should include notice block when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "test.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Title\n")

            result = markdown_to_typst(md_path, notice="Notice text here")
            assert "Notice text here" in result

    def test_without_notice(self):
        """markdown_to_typst without notice should not contain notice block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "test.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Title\n")

            result = markdown_to_typst(md_path, notice=None)
            assert "#place(" not in result

    def test_custom_width(self):
        """markdown_to_typst should use the provided width."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "test.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Title\n")

            result = markdown_to_typst(md_path, width="80%")
            assert "80%" in result


class TestConvertLines:
    def test_h1_heading(self):
        """H1 heading should convert to Typst '=' heading."""
        typst_lines, _ = _convert_lines(["# Main Title\n"], "50%")
        joined = "\n".join(typst_lines)
        assert "= Main Title" in joined

    def test_h2_heading(self):
        """H2 heading should convert to Typst '==' heading."""
        typst_lines, _ = _convert_lines(["## Subtitle\n"], "50%")
        joined = "\n".join(typst_lines)
        assert "== Subtitle" in joined

    def test_h3_heading(self):
        """H3 heading should convert to Typst '===' heading."""
        typst_lines, _ = _convert_lines(["### Section\n"], "50%")
        joined = "\n".join(typst_lines)
        assert "=== Section" in joined

    def test_paragraph_text(self):
        """Plain text should appear as-is with a parbreak."""
        typst_lines, _ = _convert_lines(["Some plain text\n"], "50%")
        joined = "\n".join(typst_lines)
        assert "Some plain text" in joined
        assert "#parbreak()" in joined

    def test_empty_lines_ignored(self):
        """Empty lines should be skipped (no extra content)."""
        typst_lines, _ = _convert_lines(["# Title\n", "\n", "Text\n"], "50%")
        joined = "\n".join(typst_lines)
        assert "= Title" in joined
        assert "Text" in joined

    def test_table_rows(self):
        """Table rows starting with | should be converted to a Typst table."""
        lines = [
            "| Col A | Col B |\n",
            "| --- | --- |\n",
            "| val1 | val2 |\n",
        ]
        typst_lines, _ = _convert_lines(lines, "50%")
        joined = "\n".join(typst_lines)
        assert "#table(" in joined
        assert "[Col A]" in joined
        assert "[val1]" in joined
        assert "[val2]" in joined

    def test_table_separator_row_skipped(self):
        """Table separator rows with --- should be skipped."""
        lines = [
            "| A | B |\n",
            "| --- | --- |\n",
            "| 1 | 2 |\n",
        ]
        typst_lines, _ = _convert_lines(lines, "50%")
        joined = "\n".join(typst_lines)
        assert "---" not in joined

    def test_table_followed_by_empty_line_flushes(self):
        """A table followed by an empty line should be flushed properly."""
        lines = [
            "| A | B |\n",
            "\n",
            "Paragraph after table\n",
        ]
        typst_lines, _ = _convert_lines(lines, "50%")
        joined = "\n".join(typst_lines)
        assert "#table(" in joined
        assert "Paragraph after table" in joined

    def test_table_at_end_of_file_flushed(self):
        """A table at the end of file (no trailing empty line) should be flushed."""
        lines = [
            "| X | Y |\n",
            "| 1 | 2 |\n",
        ]
        typst_lines, _ = _convert_lines(lines, "50%")
        joined = "\n".join(typst_lines)
        assert "#table(" in joined
        assert "[X]" in joined

    def test_wrapping_structure(self):
        """Output should be wrapped in align and block."""
        typst_lines, _ = _convert_lines(["Hello\n"], "50%")
        joined = "\n".join(typst_lines)
        assert "#align(center + horizon)[" in joined
        assert "#block(width: 50%)[" in joined

    def test_width_parameter_used(self):
        """The width parameter should appear in the block."""
        typst_lines, _ = _convert_lines(["text\n"], "75%")
        joined = "\n".join(typst_lines)
        assert "75%" in joined


class TestFlushTable:
    def test_empty_input(self):
        """_flush_table with empty list should return empty list."""
        assert _flush_table([]) == []

    def test_single_column_table(self):
        """_flush_table should handle single-column table."""
        rows = ["| Single |"]
        result = _flush_table(rows)
        joined = "\n".join(result)
        assert "columns: 1" in joined
        assert "[Single]" in joined

    def test_multi_column_table(self):
        """_flush_table should handle multi-column table."""
        rows = ["| A | B | C |", "| 1 | 2 | 3 |"]
        result = _flush_table(rows)
        joined = "\n".join(result)
        assert "columns: 3" in joined
        assert "[A]" in joined
        assert "[1]" in joined
        assert "[2]" in joined
        assert "[3]" in joined

    def test_table_alignment(self):
        """_flush_table should set left alignment for all columns."""
        rows = ["| A | B |"]
        result = _flush_table(rows)
        joined = "\n".join(result)
        assert "align: (left, left)" in joined

    def test_table_stroke(self):
        """_flush_table should set stroke and inset."""
        rows = ["| A |"]
        result = _flush_table(rows)
        joined = "\n".join(result)
        assert "stroke: 0.5pt" in joined
        assert "inset: 5pt" in joined


class TestNoticeBlock:
    def test_notice_text(self):
        """_notice_block should contain the notice text."""
        result = _notice_block("Important notice", "50%")
        assert "Important notice" in result

    def test_notice_width(self):
        """_notice_block should use the provided width."""
        result = _notice_block("Notice", "60%")
        assert "60%" in result

    def test_notice_styling(self):
        """_notice_block should have proper Typst styling."""
        result = _notice_block("Text", "50%")
        assert "#place(" in result
        assert "bottom + center" in result
        assert "italic" in result

    def test_notice_block_structure(self):
        """_notice_block should contain block, fill, and radius styling."""
        result = _notice_block("Notice", "50%")
        assert "fill: luma(240)" in result
        assert "radius: 4pt" in result


# ===========================================================================
# frame_generator tests
# ===========================================================================


class TestFrameGeneratorConstants:
    def test_a3_width(self):
        """A3 width should be 420mm."""
        assert A3_WIDTH == 420

    def test_a3_height(self):
        """A3 height should be 297mm."""
        assert A3_HEIGHT == 297

    def test_content_width(self):
        """Content width should be INNER_FRAME_X2 - INNER_FRAME_X1."""
        assert CONTENT_WIDTH == INNER_FRAME_X2 - INNER_FRAME_X1

    def test_content_height(self):
        """Content height should be INNER_FRAME_Y2 - INNER_FRAME_Y1."""
        assert CONTENT_HEIGHT == INNER_FRAME_Y2 - INNER_FRAME_Y1

    def test_inner_frame_x1(self):
        """Inner frame X1 should be 10mm (margin + grid)."""
        assert INNER_FRAME_X1 == 10

    def test_inner_frame_y1(self):
        """Inner frame Y1 should be 10mm (margin + grid)."""
        assert INNER_FRAME_Y1 == 10

    def test_inner_frame_x2(self):
        """Inner frame X2 should be 410mm."""
        assert INNER_FRAME_X2 == 410

    def test_inner_frame_y2(self):
        """Inner frame Y2 should be 287mm."""
        assert INNER_FRAME_Y2 == 287


class TestGenerateFrame:
    def test_returns_circuit(self):
        """generate_frame should return a Circuit."""
        from schematika.electrical.system.system import Circuit

        frame = generate_frame()
        assert isinstance(frame, Circuit)

    def test_circuit_has_elements(self):
        """Generated frame should contain elements."""
        frame = generate_frame()
        assert len(frame.elements) > 0

    def test_contains_lines(self):
        """Frame should contain Line elements for borders and grid."""
        frame = generate_frame()
        lines = [e for e in frame.elements if isinstance(e, Line)]
        assert len(lines) > 0

    def test_contains_text_labels(self):
        """Frame should contain Text elements for grid labels."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        assert len(texts) > 0

    def test_column_labels_1_through_8(self):
        """Frame should have column labels 1 through 8."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        text_contents = [t.content for t in texts]
        for i in range(1, 9):
            assert str(i) in text_contents, f"Column label {i} missing"

    def test_row_labels_a_through_f(self):
        """Frame should have row labels A through F."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        text_contents = [t.content for t in texts]
        for ch in "ABCDEF":
            assert ch in text_contents, f"Row label {ch} missing"

    def test_column_labels_appear_twice(self):
        """Each column label should appear twice (top and bottom)."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        text_contents = [t.content for t in texts]
        for i in range(1, 9):
            count = text_contents.count(str(i))
            assert count == 2, f"Column label {i} appears {count} times, expected 2"

    def test_row_labels_appear_twice(self):
        """Each row label should appear twice (left and right)."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        text_contents = [t.content for t in texts]
        for ch in "ABCDEF":
            count = text_contents.count(ch)
            assert count == 2, f"Row label {ch} appears {count} times, expected 2"

    def test_total_text_count(self):
        """There should be 8 columns x 2 + 6 rows x 2 = 28 text elements."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        assert len(texts) == 28

    def test_total_line_count(self):
        """Line count: 2 rects (8 lines) + 8 col dividers x 2 + 6 row dividers x 2 = 36."""
        frame = generate_frame()
        lines = [e for e in frame.elements if isinstance(e, Line)]
        # 2 rectangles = 8 lines, 8 col top + 8 col bottom + 6 row left + 6 row right = 28
        assert len(lines) == 8 + 16 + 12

    def test_custom_font_family(self):
        """generate_frame should use the provided font_family."""
        frame = generate_frame(font_family="Courier New")
        texts = [e for e in frame.elements if isinstance(e, Text)]
        # All text elements should use the custom font
        for t in texts:
            assert t.style.font_family == "Courier New"

    def test_default_font_family(self):
        """Default font family should be Times New Roman."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        assert len(texts) > 0
        for t in texts:
            assert t.style.font_family == "Times New Roman"

    def test_line_style(self):
        """Lines should have black stroke and 0.18 stroke width."""
        frame = generate_frame()
        lines = [e for e in frame.elements if isinstance(e, Line)]
        for line in lines:
            assert line.style.stroke == "black"
            assert line.style.stroke_width == 0.18

    def test_text_anchor_is_middle(self):
        """All text labels should have 'middle' anchor."""
        frame = generate_frame()
        texts = [e for e in frame.elements if isinstance(e, Text)]
        for t in texts:
            assert t.anchor == "middle"

    def test_no_symbols(self):
        """Frame circuit should have no symbols (only raw elements)."""
        frame = generate_frame()
        assert len(frame.symbols) == 0
