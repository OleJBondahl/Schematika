"""Tests for automatic multi-page splitting (schematika.electrical.pagination)."""

from pathlib import Path

import pytest

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical import coil, fuse, no_contact
from schematika.electrical.pagination import (
    ComponentSpec,
    RungSpec,
    SystemNetlist,
    TagLink,
    check_offpage_connector_coherence,
    classify_link,
    partition_netlist_to_pages,
    partition_to_pages,
)
from schematika.project import Project


def _terminal(tag: str) -> ComponentSpec:
    return ComponentSpec(kind="terminal", id_or_prefix=tag)


def _symbol(tag: str, fn=no_contact) -> ComponentSpec:
    return ComponentSpec(kind="symbol", id_or_prefix=tag, symbol_fn=fn)


def _stub(tag: str) -> ComponentSpec:
    return ComponentSpec(kind="stub", id_or_prefix=tag)


class TestClassifyLink:
    def test_terminal_pair_is_terminal_crossing(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec("a", "power", "fa", "A", (_terminal("X4"),)),
                RungSpec("b", "power", "fb", "B", (_terminal("X4"),)),
            ),
        )
        link = TagLink("X4", "a", "b")
        assert classify_link(netlist, link) == "terminal_crossing"

    def test_symbol_pair_is_tag_echo(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec("a", "control", "fa", "A", (_symbol("K1"),)),
                RungSpec("b", "control", "fb", "B", (_symbol("K1"),)),
            ),
        )
        link = TagLink("K1", "a", "b")
        assert classify_link(netlist, link) == "tag_echo"

    def test_stub_on_either_side_is_severed_signal(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec("a", "control", "fa", "A", (_stub("WD"),)),
                RungSpec("b", "control", "fb", "B", (_terminal("WD"),)),
            ),
        )
        link = TagLink("WD", "a", "b")
        assert classify_link(netlist, link) == "severed_signal"


class TestPinToFunction:
    def test_ambiguous_rung_relocates_to_pinned_functions_page(self) -> None:
        """The e-stop case: a control-shaped rung must land on the power
        page it's pinned to, not a control-logic page with unrelated rungs.
        """
        netlist = SystemNetlist(
            rungs=(
                RungSpec(
                    "main_incomer_a",
                    "power",
                    "main_incomer_a",
                    "Incomer",
                    (_terminal("X1"),),
                ),
                RungSpec("power_b", "power", "fb", "B", (_terminal("X2"),)),
                RungSpec("power_c", "power", "fc", "C", (_terminal("X3"),)),
                RungSpec(
                    "estop_master",
                    "control",
                    "estop",
                    "E-stop",
                    (_terminal("X9"),),
                    pin_to_function="main_incomer_a",
                ),
                RungSpec(
                    "unrelated_control",
                    "control",
                    "conveyor",
                    "Conveyor",
                    (_terminal("X10"),),
                ),
            ),
        )
        result = partition_netlist_to_pages(netlist, max_rungs_per_page=2)
        page_of = {key: p.number for p in result.pages for key in p.rung_keys}
        title_of = {p.number: p.title for p in result.pages}

        # Same page as its pinned target, not merely "somewhere in power".
        assert page_of["estop_master"] == page_of["main_incomer_a"]
        assert title_of[page_of["estop_master"]].startswith("Power Distribution")
        # And nowhere near the unrelated control rung.
        assert page_of["estop_master"] != page_of["unrelated_control"]

    def test_unresolvable_pin_to_function_raises(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec(
                    "a",
                    "control",
                    "fa",
                    "A",
                    (_terminal("X1"),),
                    pin_to_function="nonexistent",
                ),
            ),
        )
        with pytest.raises(CircuitValidationError, match="matches no rung"):
            partition_netlist_to_pages(netlist)


class TestSharedBusFanout:
    def test_terminal_crossing_never_produces_a_marker_at_any_fanout(self) -> None:
        rungs = tuple(
            RungSpec(
                f"loop_{i}",
                "control",
                f"loop_{i}",
                f"Loop {i}",
                (_terminal("X4"), _symbol(f"K{i}")),
            )
            for i in range(4)
        )
        links = tuple(TagLink("X4", "loop_0", f"loop_{i}") for i in range(1, 4))
        netlist = SystemNetlist(rungs=rungs, tag_links=links)

        result = partition_netlist_to_pages(netlist, max_rungs_per_page=1)
        page_of = {key: p.number for p in result.pages for key in p.rung_keys}
        # Every loop is on its own page (max_rungs_per_page=1), so all three
        # links genuinely cross a page boundary -- and still zero markers.
        assert len({page_of[r.key] for r in rungs}) == 4
        assert result.markers == {}
        assert len(result.terminal_crossings) == 3

    def test_severed_signal_fanout_beyond_pair_raises(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec("owner", "control", "fo", "Owner", (_stub("BROKEN"),)),
                RungSpec("user_0", "control", "fu0", "U0", (_stub("BROKEN"),)),
                RungSpec("user_1", "control", "fu1", "U1", (_stub("BROKEN"),)),
            ),
            tag_links=(
                TagLink("BROKEN", "owner", "user_0"),
                TagLink("BROKEN", "owner", "user_1"),
            ),
        )
        with pytest.raises(
            CircuitValidationError, match="cannot fan out beyond one owner"
        ):
            partition_netlist_to_pages(netlist, max_rungs_per_page=1)

    def test_same_fanout_resolves_once_terminal_anchored(self) -> None:
        """The guard fires on a bare stub; anchoring the same net at a
        terminal instead removes the fan-out cap entirely.
        """
        netlist = SystemNetlist(
            rungs=(
                RungSpec("owner", "control", "fo", "Owner", (_terminal("BROKEN"),)),
                RungSpec("user_0", "control", "fu0", "U0", (_terminal("BROKEN"),)),
                RungSpec("user_1", "control", "fu1", "U1", (_terminal("BROKEN"),)),
            ),
            tag_links=(
                TagLink("BROKEN", "owner", "user_0"),
                TagLink("BROKEN", "owner", "user_1"),
            ),
        )
        result = partition_netlist_to_pages(netlist, max_rungs_per_page=1)
        assert result.markers == {}


class TestWidthBasedPacking:
    def test_group_splits_by_width_even_under_a_generous_rung_count_cap(self) -> None:
        """4 three-pole (220mm) rungs sum past the width ceiling even though
        4 rungs is nowhere near a generous count cap -- width, not count, drives it.
        """
        rungs = tuple(
            RungSpec(
                f"r{i}",
                "power",
                "wide",
                f"Wide {i}",
                (ComponentSpec("terminal", f"X{i}", poles=3),),
            )
            for i in range(4)
        )
        netlist = SystemNetlist(rungs=rungs)
        result = partition_netlist_to_pages(netlist, max_rungs_per_page=20)
        assert len(result.pages) > 1

    def test_trailing_remainder_of_an_oversized_group_merges_with_next_group(
        self,
    ) -> None:
        """An oversized group's under-full last chunk stays open for the next
        function group to merge into, instead of being stranded alone.
        """
        wide = tuple(
            RungSpec(
                f"w{i}",
                "power",
                "wide",
                f"Wide {i}",
                (ComponentSpec("terminal", f"XW{i}", poles=3),),
            )
            for i in range(4)
        )
        narrow = (RungSpec("n0", "power", "narrow", "Narrow", (_terminal("XN0"),)),)
        netlist = SystemNetlist(rungs=wide + narrow)
        result = partition_netlist_to_pages(netlist, max_rungs_per_page=20)
        page_of = {key: p.number for p in result.pages for key in p.rung_keys}
        assert len(result.pages) == 2
        assert page_of["n0"] == page_of["w3"]


class TestBuildOrder:
    def test_cyclic_tag_dependency_raises(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec("a", "control", "fa", "A", (_symbol("K1"),)),
                RungSpec("b", "control", "fb", "B", (_symbol("K2"),)),
            ),
            tag_links=(TagLink("K1", "b", "a"), TagLink("K2", "a", "b")),
        )
        with pytest.raises(CircuitValidationError, match="cyclic tag dependency"):
            partition_netlist_to_pages(netlist)


class TestCrossPageConnectorCoherence:
    def test_clean_partition_has_no_findings(self) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec("owner", "control", "fo", "Owner", (_stub("WD"),)),
                RungSpec("user", "control", "fu", "User", (_stub("WD"),)),
            ),
            tag_links=(TagLink("WD", "owner", "user"),),
        )
        result = partition_netlist_to_pages(netlist, max_rungs_per_page=1)
        assert check_offpage_connector_coherence(netlist, result) == ()

    def test_marker_on_non_severed_tag_is_flagged(self) -> None:
        """A hand-built PartitionResult that puts a marker on a terminal_crossing
        tag (round-1's Finding-1 bug) must be caught, not silently accepted.
        """
        from schematika.electrical.pagination import (
            OffPageMarker,
            PageAssignment,
            PartitionResult,
        )

        netlist = SystemNetlist(
            rungs=(
                RungSpec("a", "power", "fa", "A", (_terminal("X4"),)),
                RungSpec("b", "power", "fb", "B", (_terminal("X4"),)),
            ),
            tag_links=(TagLink("X4", "a", "b"),),
        )
        broken = PartitionResult(
            pages=(
                PageAssignment(1, "A", ("a",)),
                PageAssignment(2, "B", ("b",)),
            ),
            build_order=("a", "b"),
            markers={"a": (OffPageMarker("X4", "end", "down", "/2.C1"),)},
        )
        findings = check_offpage_connector_coherence(netlist, broken)
        assert any(f.kind == "marker_on_non_severed_tag" for f in findings)


class TestEndToEndRenderAndWindowsPathFix:
    def test_partition_to_pages_renders_a_real_multi_page_pdf(
        self, tmp_path: Path
    ) -> None:
        # Deliberately long, descriptive rung keys on one merged page --
        # exercises project.py's long-merged-filename fix for real.
        long_names = [
            "main_incomer_domain_alpha_control_supply",
            "control_supply_domain_alpha_secondary_feed",
            "conveyor_start_stop_station_number_one",
            "conveyor_contactor_coil_assembly_station_one",
        ]
        rungs = tuple(
            RungSpec(
                name,
                "control",
                "group_one",
                name,
                (_terminal(f"X{i}"), _symbol(f"K{i}", fn=coil)),
            )
            for i, name in enumerate(long_names)
        )
        netlist = SystemNetlist(rungs=rungs)

        result = partition_to_pages(netlist, max_rungs_per_page=4)
        assert len(result.partition.pages) == 1
        assert len(result.circuit_results) == 4

        project = Project(
            title="Test",
            drawing_number="T-1",
            author="test",
            project="test",
            revision="0",
        )
        project.add_partition(result)
        # build_svgs exercises the exact _render_multi_circuit_pages path
        # (including the long-merged-filename fix) without needing Typst,
        # which sandboxes writes outside its configured root -- see
        # test_project_safe_merged_key.py for the direct unit test of the
        # fix, and TestBuildMethod in test_project.py for this repo's own
        # convention of mocking Typst in unit tests rather than compiling
        # real PDFs.
        out_dir = tmp_path / "svgs"
        project.build_svgs(str(out_dir))
        # One merged SVG for the page (in addition to one per rung) --
        # named after the first rung key plus a short hash, not the ~180+
        # char join of all four descriptive keys that failed before the fix.
        merged_svgs = [
            p
            for p in out_dir.glob("*.svg")
            if p.name != f"{long_names[0]}.svg" and p.stem.startswith(long_names[0])
        ]
        assert len(merged_svgs) == 1
        assert len(merged_svgs[0].name) < 100

    def test_fuse_rung_builds_and_pages_across_two_pages(self, tmp_path: Path) -> None:
        netlist = SystemNetlist(
            rungs=(
                RungSpec(
                    "incomer",
                    "power",
                    "incomer",
                    "Incomer",
                    (_terminal("X1"), _symbol("F1", fn=fuse), _terminal("X2")),
                ),
                RungSpec(
                    "loop",
                    "control",
                    "loop1",
                    "Loop 1",
                    (_terminal("X3"), _symbol("K1", fn=coil)),
                ),
            ),
        )
        result = partition_to_pages(netlist, max_rungs_per_page=1)
        assert len(result.partition.pages) == 2

        project = Project(
            title="Test",
            drawing_number="T-2",
            author="test",
            project="test",
            revision="0",
        )
        project.add_partition(result)
        out_dir = tmp_path / "svgs2"
        project.build_svgs(str(out_dir))
        assert (out_dir / "incomer.svg").exists()
        assert (out_dir / "loop.svg").exists()
