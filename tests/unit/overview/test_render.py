"""Tests for schematika.overview.render."""

from schematika.overview import build, render_overview
from schematika.overview.inputs import OverviewInput, OverviewWire
from schematika.overview.render import build_from_inputs


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


def test_build_accepts_classify_override(small_project, tmp_path) -> None:
    calls: list[str | None] = []

    def spy_classify(label):
        calls.append(label)
        return "signal"

    build(small_project, tmp_path / "o.html", classify=spy_classify)
    assert calls  # override was invoked at least once


def test_build_from_inputs_merges_and_writes_file(tmp_path) -> None:
    pcb = OverviewInput(
        wires=(),
        field_device_tags=frozenset(),
        terminal_tags=frozenset(),
        pcb_nets=(("JB1", "GND", ("JB1.F1.1", "JB1.K1.A1")),),
    )
    harness = OverviewInput(
        wires=(OverviewWire(a="X1..1", b="JB1.F1.1", label=None),),
        field_device_tags=frozenset(),
        terminal_tags=frozenset({"X1"}),
    )
    out = tmp_path / "merged.html"
    build_from_inputs(pcb, harness, output_path=out)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "window.OVERVIEW_DATA" in html
    assert "JB1" in html  # PCB-side device made it into the rendered graph
