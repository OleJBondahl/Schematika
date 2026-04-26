"""Tests for ``schematika.overview.build`` orchestration."""

from __future__ import annotations

import shutil

import pytest

from schematika import overview
from schematika.electrical.builder_models import BuildResult
from schematika.electrical.system.system import Circuit
from schematika.overview.model import ContainerSpec
from schematika.overview.options import OverviewOptions
from schematika.project import Project


def _empty_circuit_factory(state, **_kwargs):
    return BuildResult(state=state, circuit=Circuit(), used_terminals=[])


def test_build_raises_typeerror_when_options_none() -> None:
    project = Project()
    with pytest.raises(TypeError, match="OverviewOptions is required"):
        overview.build(project, options=None)


def test_build_auto_calls_build_circuits_when_results_empty(
    tmp_path, monkeypatch
) -> None:
    """Empty ``_results`` triggers ``project.build_circuits()`` once before extract."""
    project = Project()
    project.add_circuit("main", builder_fn=_empty_circuit_factory)
    assert project._results == {}

    # Stub the emitter so we don't need the dot CLI for this test.
    calls: dict[str, int] = {"emit": 0}

    def _stub_emit(_units, _wires, **_kwargs):
        calls["emit"] += 1

    monkeypatch.setattr(overview.emitter, "emit", _stub_emit)

    overview.build(
        project,
        options=OverviewOptions(
            containment={
                "cab": ContainerSpec(label="C", kind="cabinet"),
            },
            output_path=tmp_path / "out.svg",
        ),
    )

    assert "main" in project._results
    assert calls["emit"] == 1


def test_build_skips_build_circuits_when_results_present(tmp_path, monkeypatch) -> None:
    """Already-built ``_results`` must NOT be rebuilt by ``build()``."""
    project = Project()
    project.add_circuit("main", builder_fn=_empty_circuit_factory)
    project.build_circuits()
    expected_state = project._state

    builds: dict[str, int] = {"count": 0}
    original_build_circuits = Project.build_circuits

    def _spy_build_circuits(self):
        builds["count"] += 1
        original_build_circuits(self)

    monkeypatch.setattr(Project, "build_circuits", _spy_build_circuits)
    monkeypatch.setattr(overview.emitter, "emit", lambda *_a, **_kw: None)

    overview.build(
        project,
        options=OverviewOptions(
            containment={
                "cab": ContainerSpec(label="C", kind="cabinet"),
            },
            output_path=tmp_path / "out.svg",
        ),
    )

    assert builds["count"] == 0
    assert project._state is expected_state


# ---------------------------------------------------------------------------
# Integration test (skipped without dot)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz `dot` not on PATH")
def test_build_end_to_end_writes_svg(tmp_path) -> None:
    project = Project()
    project.add_circuit("ckt_a", builder_fn=_empty_circuit_factory)
    project.add_circuit("ckt_b", builder_fn=_empty_circuit_factory)
    out = tmp_path / "system.svg"

    overview.build(
        project,
        options=OverviewOptions(
            containment={
                "cab": ContainerSpec(label="Cabinet", kind="cabinet"),
            },
            output_path=out,
        ),
    )

    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")
    assert (tmp_path / "system.svg.dot").exists()
    assert (tmp_path / "system.svg.expected.json").exists()
