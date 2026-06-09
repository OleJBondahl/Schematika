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
    """Build graph, apply layout, and render a self-contained HTML string.

    Args:
        inp: Frozen connectivity snapshot to render.
        layout: Optional callable that positions device nodes; defaults to
            :func:`~schematika.overview.layout.compute_device_positions`.

    Returns:
        A self-contained HTML string with inlined JS/CSS and ``window.OVERVIEW_DATA``.

    Examples:
        >>> from schematika.overview.inputs import OverviewInput, OverviewWire
        >>> from schematika.overview.render import render_overview
        >>> w = OverviewWire(a="A.J1.1", b="B.J2.1", label=None)
        >>> inp = OverviewInput(
        ...     wires=(w,), field_device_tags=frozenset(), terminal_tags=frozenset()
        ... )
        >>> "window.OVERVIEW_DATA" in render_overview(inp)
        True
    """
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
    """Render overview HTML for *project* and write it to *output_path*.

    Args:
        project: Any :class:`~schematika.overview.inputs.ProjectLike`
            (any object with an ``overview_input()`` method).
        output_path: Destination file path; created or overwritten.
        layout: Optional device-layout override; see :func:`render_overview`.

    Examples:
        >>> import tempfile, os
        >>> from pathlib import Path
        >>> from schematika.overview.inputs import OverviewInput, OverviewWire
        >>> from schematika.overview.render import build
        >>> class Stub:
        ...     def overview_input(self):
        ...         w = OverviewWire(a="A.J1.1", b="B.J2.1", label=None)
        ...         return OverviewInput(
        ...             wires=(w,), field_device_tags=frozenset(),
        ...             terminal_tags=frozenset())
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     out = Path(tmp) / "overview.html"
        ...     build(Stub(), out)
        ...     out.exists()
        True
    """
    html = render_overview(project.overview_input(), layout=layout)
    Path(output_path).write_text(html, encoding="utf-8")
