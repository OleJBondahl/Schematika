"""Tests for ``schematika.overview.emitter``.

The DOT-text and sidecar pieces don't need the ``dot`` CLI and run on
every machine. The single integration test at the bottom is gated on
``shutil.which("dot")`` and skipped if Graphviz isn't installed.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import schematika.overview.emitter as emitter_mod
from schematika.overview.emitter import (
    _build_dot,
    _quote_dot_id,
    _render_unit_table,
    emit,
)
from schematika.overview.errors import OverviewRenderError
from schematika.overview.model import Unit, Wire

# ---------------------------------------------------------------------------
# Tiny model fixture
# ---------------------------------------------------------------------------


def _model() -> tuple[list[Unit], list[Wire]]:
    units = [
        Unit(
            id="cab",
            label="Cabinet",
            parent=None,
            is_container=True,
            ports=(),
            kind="cabinet",
        ),
        Unit(
            id="K1",
            label="K1",
            parent="cab",
            is_container=False,
            ports=("A1", "A2"),
            kind="device",
        ),
        Unit(
            id="X1",
            label="X1",
            parent="cab",
            is_container=False,
            ports=("1", "2"),
            kind="terminal",
        ),
    ]
    wires = [
        Wire(from_unit="X1", from_port="1", to_unit="K1", to_port="A1", kind="power"),
    ]
    return units, wires


def _stub_dot(monkeypatch, *, returncode: int = 0, stderr_text: str = "") -> None:
    """Replace ``subprocess.run`` so emit() works without the dot binary.

    Honours ``text=True`` (used by ``_get_graphviz_version``) so the
    stubbed object matches what the production code would receive in real
    runs.
    """

    def _fake_run(cmd, **kwargs):
        if "-o" in cmd:
            target = cmd[cmd.index("-o") + 1]
            Path(target).write_text("<svg/>", encoding="utf-8")
        text = kwargs.get("text", False)
        return SimpleNamespace(
            returncode=returncode,
            stdout="" if text else b"",
            stderr=stderr_text if text else stderr_text.encode("utf-8"),
        )

    monkeypatch.setattr(emitter_mod.subprocess, "run", _fake_run)


# ---------------------------------------------------------------------------
# _quote_dot_id
# ---------------------------------------------------------------------------


def test_quote_dot_id_passes_through_simple_word() -> None:
    assert _quote_dot_id("K1") == "K1"


def test_quote_dot_id_quotes_colons() -> None:
    assert _quote_dot_id("PLC:AI:Sig") == '"PLC:AI:Sig"'


def test_quote_dot_id_quotes_dot_keyword() -> None:
    assert _quote_dot_id("graph") == '"graph"'


def test_quote_dot_id_escapes_inner_quote() -> None:
    assert _quote_dot_id('he said "hi"') == '"he said \\"hi\\""'


def test_quote_dot_id_quotes_empty_string() -> None:
    assert _quote_dot_id("") == '""'


# ---------------------------------------------------------------------------
# _render_unit_table
# ---------------------------------------------------------------------------


def test_unit_table_has_one_tr_per_port_plus_header() -> None:
    unit = Unit(
        id="K1",
        label="K1",
        parent=None,
        is_container=False,
        ports=("A1", "A2", "A3"),
        kind="device",
    )
    table = _render_unit_table(unit)
    # header row + 3 ports = 4 <TR> blocks
    assert table.count("<TR>") == 4
    for port in ("A1", "A2", "A3"):
        assert f'PORT="{port}"' in table


def test_unit_table_escapes_html_special_chars() -> None:
    unit = Unit(
        id="weird",
        label="A & B <c>",
        parent=None,
        is_container=False,
        ports=(),
        kind="device",
    )
    table = _render_unit_table(unit)
    assert "A &amp; B &lt;c&gt;" in table


# ---------------------------------------------------------------------------
# _build_dot
# ---------------------------------------------------------------------------


def test_build_dot_contains_required_keywords() -> None:
    units, wires = _model()
    dot = _build_dot(units, wires, {"power": "#c0392b", "signal": "#2980b9"})
    assert "digraph system" in dot
    assert 'splines="ortho"' in dot
    assert "compound=true" in dot
    assert 'rankdir="LR"' in dot
    assert "newrank=true" in dot


def test_build_dot_emits_cluster_for_container() -> None:
    units, wires = _model()
    dot = _build_dot(units, wires, {"power": "#c0392b", "signal": "#2980b9"})
    assert "subgraph cluster_cab" in dot
    assert 'style="rounded,filled"' in dot
    assert "cluster=true;" in dot


def test_build_dot_emits_node_per_leaf_unit() -> None:
    units, wires = _model()
    dot = _build_dot(units, wires, {"power": "#c0392b", "signal": "#2980b9"})
    assert "K1 [shape=plaintext" in dot
    assert "X1 [shape=plaintext" in dot


def test_build_dot_edge_uses_palette_color() -> None:
    units, wires = _model()
    dot = _build_dot(units, wires, {"power": "#aa0000", "signal": "#0000aa"})
    assert 'color="#aa0000"' in dot
    # Wire kind="power" -> palette["power"]; signal palette unused.
    assert 'color="#0000aa"' not in dot


def test_build_dot_edge_endpoint_uses_port_syntax() -> None:
    units, wires = _model()
    dot = _build_dot(units, wires, {"power": "#c0392b", "signal": "#2980b9"})
    # Port "1" starts with a digit so must be quoted per DOT grammar.
    assert 'X1:"1":e -> K1:A1:w' in dot


def test_build_dot_edge_tooltip_round_trip_format() -> None:
    units, wires = _model()
    dot = _build_dot(units, wires, {"power": "#c0392b", "signal": "#2980b9"})
    assert 'tooltip="X1:1->K1:A1"' in dot


# ---------------------------------------------------------------------------
# emit() — DOT + sidecar I/O (subprocess stubbed)
# ---------------------------------------------------------------------------


def test_emit_writes_dot_alongside_svg(tmp_path, monkeypatch) -> None:
    """Even if `dot` is absent, the DOT file is written before invocation."""
    units, wires = _model()
    out = tmp_path / "system.svg"

    def _missing_dot(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(emitter_mod.subprocess, "run", _missing_dot)

    with pytest.raises(OverviewRenderError, match="not found on PATH"):
        emit(units, wires, output_path=out)

    assert (tmp_path / "system.svg.dot").exists()
    dot_text = (tmp_path / "system.svg.dot").read_text(encoding="utf-8")
    assert "digraph system" in dot_text


def test_sidecar_shape(tmp_path, monkeypatch) -> None:
    units, wires = _model()
    out = tmp_path / "system.svg"
    _stub_dot(monkeypatch, stderr_text="dot - graphviz version 99.0.0 (test)")

    emit(units, wires, output_path=out)

    sidecar = json.loads((tmp_path / "system.svg.expected.json").read_text())
    assert sidecar["version"] == 1
    assert set(sidecar) >= {
        "version",
        "graphviz_version",
        "schematika_version",
        "palette",
        "counts",
        "containers",
        "units",
        "edges",
    }
    # Counts come from the in-memory model.
    assert sidecar["counts"] == {"nodes": 2, "edges": 1, "clusters": 1}
    assert {c["id"] for c in sidecar["containers"]} == {"cab"}
    assert {u["id"] for u in sidecar["units"]} == {"K1", "X1"}
    assert sidecar["containers"][0]["child_units"] == ["K1", "X1"]


def test_sidecar_default_palette(tmp_path, monkeypatch) -> None:
    units, wires = _model()
    out = tmp_path / "system.svg"
    _stub_dot(monkeypatch)

    emit(units, wires, output_path=out)

    sidecar = json.loads((tmp_path / "system.svg.expected.json").read_text())
    assert sidecar["palette"] == {"power": "#c0392b", "signal": "#2980b9"}
    # Default palette propagates to edge color.
    assert sidecar["edges"][0]["color"] == "#c0392b"


def test_sidecar_custom_palette_overrides_default(tmp_path, monkeypatch) -> None:
    units, wires = _model()
    out = tmp_path / "system.svg"
    _stub_dot(monkeypatch)

    emit(
        units,
        wires,
        output_path=out,
        palette={"power": "#ffaa00", "signal": "#00aaff"},
    )

    sidecar = json.loads((tmp_path / "system.svg.expected.json").read_text())
    assert sidecar["palette"] == {"power": "#ffaa00", "signal": "#00aaff"}
    assert sidecar["edges"][0]["color"] == "#ffaa00"


def test_emit_raises_with_stderr_on_dot_nonzero_exit(tmp_path, monkeypatch) -> None:
    units, wires = _model()
    out = tmp_path / "system.svg"
    _stub_dot(monkeypatch, returncode=1, stderr_text="dot: syntax error in line 7")

    with pytest.raises(OverviewRenderError, match="syntax error"):
        emit(units, wires, output_path=out)


# ---------------------------------------------------------------------------
# Integration test (skipped without dot)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz `dot` not on PATH")
def test_emit_against_real_dot_writes_svg(tmp_path) -> None:
    units, wires = _model()
    out = tmp_path / "system.svg"

    emit(units, wires, output_path=out)

    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")
    assert (tmp_path / "system.svg.dot").exists()
    assert (tmp_path / "system.svg.expected.json").exists()
