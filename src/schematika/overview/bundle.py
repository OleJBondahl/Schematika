"""Assemble a self-contained overview HTML from graph data and bundled assets."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TYPE_CHECKING

from schematika.core.exceptions import CircuitValidationError

if TYPE_CHECKING:
    from schematika.overview.model import OverviewGraph

_CYTOSCAPE_VERSION = (
    "3.33.4"  # vendored; latest stable is 3.34.0 but app.js is verified against 3.33.4
)

_DEFAULT_CONFIG: dict = {
    "title": "System Overview",
    "netColors": {
        "power": "#E69F00",
        "CAN": "#56B4E9",
        "GND": "#999999",
        "interlock": "#D55E00",
        "signal": "#009E73",
        "mixed": "#6e7681",
    },
    "classColors": {
        "X": "#d2a8ff",
        "Q": "#e3b341",
        "F": "#f0883e",
        "FT": "#f85149",
        "K": "#58a6ff",
        "CT": "#7ee787",
        "G": "#bc8cff",
        "U": "#79c0ff",
        "PLC": "#ff9e64",
        "FIELD": "#39c5cf",
    },
    "defaultClassColor": "#8b949e",
    "spineClasses": [],
}

_TEMPLATE_TOKENS = ("TITLE_TAG", "CDN_TAG", "APP_TAG", "VERLABEL_TAG")


def escape_json_for_script(obj: object) -> str:
    r"""Return a JS string literal (with quotes) that JSON.parse() decodes to obj.

    Double json.dumps gives an ASCII-safe quoted literal. Neutralize < and >
    so no </script>, <!--, or --> can break out of the surrounding <script> tag.
    JSON.parse decodes </> back to < / >, so the data round-trips exactly.
    """
    literal = json.dumps(json.dumps(obj))
    return literal.replace("<", "\\u003c").replace(">", "\\u003e")


def build_data_block(graph_dict: dict, config: dict) -> str:
    """Return a JS statement assigning the merged payload to window.OVERVIEW_DATA."""
    payload = {**graph_dict, "config": config}
    return f"window.OVERVIEW_DATA = JSON.parse({escape_json_for_script(payload)});"


def assemble_html(
    *,
    template: str,
    cytoscape_js: str,
    app_js: str,
    data_block: str,
    title: str,
    version_label: str,
) -> str:
    """Replace the four literal tokens in *template* and return the final HTML string.

    Raises CircuitValidationError if any token is absent from the template.
    """
    for tag in _TEMPLATE_TOKENS:
        if tag not in template:
            msg = f"template missing marker: {tag}"
            raise CircuitValidationError(msg)

    return (
        template.replace("TITLE_TAG", title)
        .replace("CDN_TAG", f"<script>{cytoscape_js}</script>")
        .replace("APP_TAG", f"<script>\n{data_block}\n{app_js}\n</script>")
        .replace("VERLABEL_TAG", version_label)
    )


def render_html(
    graph: OverviewGraph,
    *,
    title: str,
    config: dict,
    version_label: str = "",
) -> str:
    """Load bundled assets and assemble a self-contained HTML string."""
    assets = files("schematika.overview") / "assets"
    cytoscape_js = (assets / "cytoscape.min.js").read_text(encoding="utf-8")
    app_js = (assets / "app.js").read_text(encoding="utf-8")
    template = (assets / "template.html").read_text(encoding="utf-8")
    data_block = build_data_block(graph.to_dict(), config)
    return assemble_html(
        template=template,
        cytoscape_js=cytoscape_js,
        app_js=app_js,
        data_block=data_block,
        title=title,
        version_label=version_label,
    )
