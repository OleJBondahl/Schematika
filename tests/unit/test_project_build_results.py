"""Project.build_results: public read-only accessor for per-circuit BuildResult."""

from typing import Any

from schematika.electrical.builder import BuildResult
from schematika.electrical.system.system import Circuit
from schematika.project import Project


def _circuit_fn(state: Any, **_kwargs: Any) -> BuildResult:
    return BuildResult(state=state, circuit=Circuit(), used_terminals=[])


def test_build_results_returns_results_by_key():
    p = Project()
    p.add_circuit("c1", _circuit_fn)

    results = p.build_results

    assert set(results) == {"c1"}
    assert isinstance(results["c1"], BuildResult)


def test_build_results_auto_builds_if_needed():
    p = Project()
    p.add_circuit("c1", _circuit_fn)

    assert p._circuits_built is False
    _ = p.build_results
    assert p._circuits_built is True


def test_build_results_returns_a_copy_not_the_live_dict():
    p = Project()
    p.add_circuit("c1", _circuit_fn)

    results = p.build_results
    results["bogus"] = results["c1"]

    assert "bogus" not in p.build_results
