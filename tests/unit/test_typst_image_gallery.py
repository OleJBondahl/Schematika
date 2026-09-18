"""image_gallery: Typst page-body builders for image renders/placement drawings."""

from schematika.rendering.typst.image_gallery import (
    image_full_page,
    image_row_page,
    page_wrapper,
)


def test_page_wrapper_includes_title_and_body():
    result = page_wrapper("My Title", "body content")

    assert "My Title" in result
    assert "body content" in result
    assert result.startswith("#pad(")


def test_image_row_page_empty_shows_default_message():
    result = image_row_page([], "3D Renders")

    assert "No images available." in result
    assert "#grid(" not in result


def test_image_row_page_empty_message_is_overridable():
    result = image_row_page([], "3D Renders", empty_message="No renders available.")

    assert "No renders available." in result


def test_image_row_page_splits_width_evenly():
    result = image_row_page(
        [("a.png", "Top"), ("b.png", "Bottom")],
        "3D Renders",
        page_width_mm=380,
        gutter_mm=4,
    )

    assert "columns: 2" in result
    assert "a.png" in result
    assert "b.png" in result
    assert "width: 188mm" in result  # (380 - 4) // 2


def test_image_full_page_embeds_single_image():
    result = image_full_page("placement_top.svg", "Top", "Component Placement")

    assert "placement_top.svg" in result
    assert "Component Placement" in result
    assert "Top" in result
    assert "width: 380mm" in result
    assert "height: 220mm" in result
