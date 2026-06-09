"""Tests for schematika.overview.bundle."""

import pytest

from schematika.overview.bundle import (
    assemble_html,
    escape_json_for_script,
    render_html,
)
from schematika.overview.extract import graph_from_input
from schematika.overview.inputs import OverviewInput, OverviewWire


def _inp(
    wires: list,
    *,
    field: frozenset = frozenset(),
    term: frozenset = frozenset(),
) -> OverviewInput:
    return OverviewInput(
        wires=tuple(OverviewWire(a=a, b=b, label=lbl) for a, b, lbl in wires),
        field_device_tags=field,
        terminal_tags=term,
        title="T",
    )


def test_escape_blocks_script_breakout() -> None:
    s = escape_json_for_script({"x": "</script>"})
    assert "</script>" not in s
    assert "\\u003c" in s


def test_render_html_embeds_data_and_assets() -> None:
    g = graph_from_input(
        _inp(
            [("X1..1", "M1..1", None)],
            field=frozenset({"M1"}),
            term=frozenset({"X1"}),
        )
    )
    html = render_html(g, title="MyTitle", config={"title": "MyTitle"})
    assert "window.OVERVIEW_DATA" in html
    assert "cytoscape" in html.lower()
    assert "MyTitle" in html
    assert "TITLE_TAG" not in html
    assert "APP_TAG" not in html
    assert "CDN_TAG" not in html
    assert "VERLABEL_TAG" not in html


def test_render_html_raises_on_template_missing_marker() -> None:
    from schematika.core.exceptions import CircuitValidationError

    with pytest.raises(CircuitValidationError):
        assemble_html(
            template="<html>no markers</html>",
            cytoscape_js="x",
            app_js="y",
            data_block="z",
            title="t",
            version_label="",
        )
