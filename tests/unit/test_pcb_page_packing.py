"""Tests for _pack_pages: greedy packing, page boundaries, auto titles."""

from schematika.pcb.builder import _Column, _pack_pages


def _make_columns(keys_and_widths: list[tuple[str, float]]) -> list[_Column]:
    return [
        _Column(
            key=key,
            placed_symbols=(),
            width_mm=width,
            height_mm=40.0,
        )
        for key, width in keys_and_widths
    ]


class TestPackPagesBasic:
    def test_single_column_single_page(self) -> None:
        cols = _make_columns([("col_000", 50.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=40.0)
        assert len(pages) == 1
        assert pages[0][0] == "Page 1"
        assert "col_000" in pages[0][1]

    def test_empty_columns_no_pages(self) -> None:
        pages = _pack_pages([], page_size=(297.0, 210.0), column_spacing_mm=40.0)
        assert pages == ()

    def test_two_columns_fit_on_one_page(self) -> None:
        # 2 columns × (50 + 40) = 180 mm < 297 mm
        cols = _make_columns([("col_000", 50.0), ("col_001", 50.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=40.0)
        assert len(pages) == 1
        assert set(pages[0][1]) == {"col_000", "col_001"}

    def test_columns_overflow_to_second_page(self) -> None:
        # 4 columns × 90 mm = 360 mm > 297 mm; first 3 fit (270), 4th overflows
        cols = _make_columns([("c0", 50.0), ("c1", 50.0), ("c2", 50.0), ("c3", 50.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=40.0)
        assert len(pages) == 2


class TestPackPagesAutoTitles:
    def test_first_page_title_is_page_1(self) -> None:
        cols = _make_columns([("col_000", 50.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=0.0)
        assert pages[0][0] == "Page 1"

    def test_second_page_title_is_page_2(self) -> None:
        # Force overflow: 3 wide columns on 200 mm page
        cols = _make_columns([("c0", 100.0), ("c1", 100.0), ("c2", 100.0)])
        pages = _pack_pages(cols, page_size=(200.0, 210.0), column_spacing_mm=0.0)
        assert len(pages) == 2
        assert pages[1][0] == "Page 2"

    def test_three_pages_correctly_titled(self) -> None:
        cols = _make_columns(
            [("c0", 100.0), ("c1", 100.0), ("c2", 100.0), ("c3", 100.0), ("c4", 100.0)]
        )
        pages = _pack_pages(cols, page_size=(120.0, 210.0), column_spacing_mm=0.0)
        assert len(pages) == 5
        assert pages[2][0] == "Page 3"


class TestPackPagesColumnGrouping:
    def test_keys_preserved_in_order(self) -> None:
        cols = _make_columns([("a", 30.0), ("b", 30.0), ("c", 30.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=0.0)
        flat_keys = [k for _, keys in pages for k in keys]
        assert flat_keys == ["a", "b", "c"]

    def test_all_columns_assigned_to_a_page(self) -> None:
        cols = _make_columns([(f"col_{i:03d}", 50.0) for i in range(10)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=40.0)
        paged_keys = {k for _, keys in pages for k in keys}
        original_keys = {col.key for col in cols}
        assert paged_keys == original_keys

    def test_no_column_assigned_twice(self) -> None:
        cols = _make_columns([(f"col_{i:03d}", 50.0) for i in range(8)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=40.0)
        paged_keys: list[str] = [k for _, keys in pages for k in keys]
        assert len(paged_keys) == len(set(paged_keys))

    def test_result_is_tuple_of_tuples(self) -> None:
        cols = _make_columns([("x", 50.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=0.0)
        assert isinstance(pages, tuple)
        title, keys = pages[0]
        assert isinstance(title, str)
        assert isinstance(keys, tuple)

    def test_wide_single_column_fits_on_its_own_page(self) -> None:
        """A column wider than the page still gets its own page (no infinite loop)."""
        # Column width 400 mm > page width 297 mm — greedy: starts new page (empty),
        # then places first column alone.
        cols = _make_columns([("wide", 400.0)])
        pages = _pack_pages(cols, page_size=(297.0, 210.0), column_spacing_mm=0.0)
        assert len(pages) == 1
        assert pages[0][1] == ("wide",)
