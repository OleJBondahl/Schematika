"""Tests for schematika.overview.render."""

from schematika.overview import build, render_overview


def test_render_overview_returns_html(small_project) -> None:
    html = render_overview(small_project.overview_input())
    assert "<html" in html.lower() or html.lstrip().startswith("<!")
    assert "window.OVERVIEW_DATA" in html


def test_build_writes_file(small_project, tmp_path) -> None:
    out = tmp_path / "overview.html"
    build(small_project, out)
    assert out.exists()
    assert "window.OVERVIEW_DATA" in out.read_text(encoding="utf-8")


def test_build_accepts_layout_override(small_project, tmp_path) -> None:
    calls: list[int] = []

    def my_layout(graph):
        calls.append(1)
        return graph  # identity

    build(small_project, tmp_path / "o.html", layout=my_layout)
    assert calls  # override was invoked
