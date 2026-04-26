from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDPage, PDRectangle


def test_default_constructor_us_letter_media_box() -> None:
    page = PDPage()
    mb = page.get_media_box()
    assert mb.width == 612.0
    assert mb.height == 792.0
    # Type entry must be /Page so the writer treats it as a leaf.
    assert page.get_cos_object().get_name(COSName.TYPE) == "Page"  # type: ignore[attr-defined]


def test_constructor_with_pd_rectangle() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    mb = page.get_media_box()
    assert (mb.lower_left_x, mb.lower_left_y, mb.upper_right_x, mb.upper_right_y) == (
        0.0,
        0.0,
        100.0,
        200.0,
    )


def test_constructor_wraps_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    page = PDPage(raw)
    assert page.get_cos_object() is raw


def test_set_media_box_round_trip() -> None:
    page = PDPage()
    page.set_media_box(PDRectangle(10.0, 20.0, 410.0, 620.0))
    mb = page.get_media_box()
    assert mb.width == 400.0
    assert mb.height == 600.0


def test_get_rotation_default_zero() -> None:
    page = PDPage()
    assert page.get_rotation() == 0


def test_set_rotation() -> None:
    page = PDPage()
    page.set_rotation(90)
    assert page.get_rotation() == 90
    page.set_rotation(450)  # normalised
    assert page.get_rotation() == 90


def test_rotation_inherited_from_parent() -> None:
    parent = COSDictionary()
    parent.set_int(COSName.get_pdf_name("Rotate"), 180)
    child_dict = COSDictionary()
    child_dict.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child_dict)
    assert page.get_rotation() == 180


def test_resources_inherited_from_parent() -> None:
    parent_res = COSDictionary()
    parent = COSDictionary()
    parent.set_item(COSName.RESOURCES, parent_res)  # type: ignore[attr-defined]
    child_dict = COSDictionary()
    child_dict.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child_dict)
    assert page.get_resources().get_cos_object() is parent_res


def test_set_resources_replaces_dict() -> None:
    page = PDPage()
    new_res = COSDictionary()
    page.set_resources(new_res)
    assert page.get_resources().get_cos_object() is new_res


def test_get_contents_empty_when_absent() -> None:
    page = PDPage()
    assert page.get_contents() == b""


def test_get_contents_single_stream() -> None:
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"BT /F0 12 Tf ET")
    page.set_contents(stream)
    assert page.get_contents() == b"BT /F0 12 Tf ET"


def test_get_contents_array_of_streams() -> None:
    page = PDPage()
    s1 = COSStream()
    s1.set_raw_data(b"q")
    s2 = COSStream()
    s2.set_raw_data(b"Q")
    arr = COSArray([s1, s2])
    page.get_cos_object().set_item(COSName.CONTENTS, arr)  # type: ignore[attr-defined]
    assert page.get_contents() == b"q\nQ"


def test_crop_box_falls_back_to_media_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    cb = page.get_crop_box()
    assert cb.width == 100.0
    assert cb.height == 200.0


def test_set_crop_box_overrides_media_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.set_crop_box(PDRectangle(10.0, 10.0, 100.0, 100.0))
    cb = page.get_crop_box()
    assert cb.width == 90.0


def test_bleed_trim_art_fall_back_to_crop_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    page.set_crop_box(PDRectangle(5.0, 5.0, 95.0, 195.0))
    for getter in (page.get_bleed_box, page.get_trim_box, page.get_art_box):
        box = getter()
        assert box.width == 90.0
        assert box.height == 190.0


def test_user_unit_default_one() -> None:
    page = PDPage()
    assert page.get_user_unit() == 1.0


def test_user_unit_round_trip() -> None:
    page = PDPage()
    page.set_user_unit(2.5)
    assert page.get_user_unit() == 2.5


def test_stub_methods_raise() -> None:
    page = PDPage()
    assert page.get_annotations() == []
    with pytest.raises(NotImplementedError):
        page.get_thumb()
    with pytest.raises(NotImplementedError):
        page.get_transition()
    with pytest.raises(NotImplementedError):
        page.get_actions()


def test_constructor_rejects_bad_type() -> None:
    with pytest.raises(TypeError):
        PDPage("nope")  # type: ignore[arg-type]


def test_unwrap_via_cos_integer_rotation() -> None:
    """COSInteger rotation values return ints — guards against accidental
    COSFloat-only handling."""
    page = PDPage()
    page.get_cos_object().set_item(COSName.get_pdf_name("Rotate"), COSInteger.get(270))
    assert page.get_rotation() == 270
