"""High-level overview rendering: pure core + I/O shell."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from schematika.overview.bundle import _DEFAULT_CONFIG, render_html
from schematika.overview.extract import graph_from_input
from schematika.overview.layout import Layout, compute_device_positions

if TYPE_CHECKING:
    from schematika.overview.inputs import OverviewInput, ProjectLike


def render_overview(inp: OverviewInput, *, layout: Layout | None = None) -> str:
    """Build graph, apply layout, and render a self-contained HTML string."""
    graph = graph_from_input(inp)
    graph = (layout or compute_device_positions)(graph)
    config = {**_DEFAULT_CONFIG, "title": inp.title}
    return render_html(graph, title=inp.title, config=config)


def build(
    project: ProjectLike,
    output_path: str | Path,
    *,
    layout: Layout | None = None,
) -> None:
    """Render overview HTML for *project* and write it to *output_path*."""
    html = render_overview(project.overview_input(), layout=layout)
    Path(output_path).write_text(html, encoding="utf-8")
