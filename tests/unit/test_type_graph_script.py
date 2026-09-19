"""Tests for scripts/type_graph.py: graph metrics, stale-docs detection, determinism."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "type_graph.py"


@pytest.fixture(scope="module")
def tg() -> ModuleType:
    spec = importlib.util.spec_from_file_location("type_graph", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_numbers_triangle_with_pendant_and_isolate(tg: ModuleType) -> None:
    adj = {
        "a": {"b", "c", "d"},
        "b": {"a", "c"},
        "c": {"a", "b"},
        "d": {"a"},
        "e": set(),
    }
    assert tg.core_numbers(adj) == {"a": 2, "b": 2, "c": 2, "d": 1, "e": 0}


def test_pagerank_ranks_shared_dependency_highest_and_sums_to_one(
    tg: ModuleType,
) -> None:
    out = {"a": ["c"], "b": ["c"], "c": []}
    rank = tg.pagerank(["a", "b", "c"], out)
    assert sum(rank.values()) == pytest.approx(1.0)
    assert rank["c"] > rank["a"]
    assert rank["a"] == pytest.approx(rank["b"])


def test_find_stale_flags_missing_edited_and_orphan_files(
    tg: ModuleType, tmp_path: Path
) -> None:
    files = {tmp_path / "a.md": "x\n"}
    assert tg.find_stale(tmp_path, files) == [tmp_path / "a.md"]  # missing

    (tmp_path / "a.md").write_text("x\n", encoding="utf-8")
    assert tg.find_stale(tmp_path, files) == []

    (tmp_path / "a.md").write_text("edited\n", encoding="utf-8")
    assert tg.find_stale(tmp_path, files) == [tmp_path / "a.md"]  # differs

    (tmp_path / "a.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "old.md").write_text("orphan\n", encoding="utf-8")
    assert tg.find_stale(tmp_path, files) == [tmp_path / "old.md"]  # orphan


def test_generation_is_deterministic_and_doctest_safe(tg: ModuleType) -> None:
    first = tg.render_all(tg.build_graph())
    second = tg.render_all(tg.build_graph())
    assert first == second
    assert tg.OUT_DIR / "index.md" in first
    # `just docs-test` doctests every docs/**/*.md; generated pages must not trip it.
    assert not [p for p, text in first.items() if p.suffix == ".md" and ">>>" in text]


def test_metrics_count_only_typed_surface_edges(tg: ModuleType) -> None:
    graph = tg.build_graph()
    flow_only = [e for e in graph.edges if not tg.TYPED_SURFACE & set(e.kinds)]
    assert flow_only, "expected some flow-only edges to make this test meaningful"
    for node_id, node in graph.nodes.items():
        typed_in = [e for e in graph.inc[node_id] if tg.TYPED_SURFACE & set(e.kinds)]
        assert node.fan_in == len(typed_in)
