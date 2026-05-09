from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.common.pd_stream import PDStream

# ---------- crop box ----------


def test_get_crop_box_defaults_to_media_box() -> None:
    """Absent ``/CropBox`` falls back to ``/MediaBox`` per PDF 1.7 §14.11.2."""
    page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
    cb = page.get_crop_box()
    mb = page.get_media_box()
    assert (cb.lower_left_x, cb.lower_left_y, cb.upper_right_x, cb.upper_right_y) == (
        mb.lower_left_x,
        mb.lower_left_y,
        mb.upper_right_x,
        mb.upper_right_y,
    )


def test_set_crop_box_round_trip() -> None:
    page = PDPage()
    page.set_crop_box(PDRectangle(10.0, 20.0, 110.0, 220.0))
    cb = page.get_crop_box()
    assert (cb.lower_left_x, cb.lower_left_y, cb.upper_right_x, cb.upper_right_y) == (
        10.0,
        20.0,
        110.0,
        220.0,
    )


def test_set_crop_box_none_removes_entry() -> None:
    page = PDPage()
    page.set_crop_box(PDRectangle(10.0, 10.0, 100.0, 100.0))
    page.set_crop_box(None)
    # Falls back to MediaBox after removal.
    cb = page.get_crop_box()
    mb = page.get_media_box()
    assert cb.width == mb.width
    assert cb.height == mb.height


# ---------- PDContentStream BBox ----------


def test_get_b_box_returns_resolved_crop_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
    page.set_crop_box(PDRectangle(10.0, 20.0, 110.0, 220.0))

    bbox = page.get_b_box()

    assert (
        bbox.lower_left_x,
        bbox.lower_left_y,
        bbox.upper_right_x,
        bbox.upper_right_y,
    ) == (10.0, 20.0, 110.0, 220.0)


def test_get_bbox_aliases_get_b_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))

    assert page.get_bbox() == page.get_b_box()


# ---------- bleed / trim / art boxes ----------


def test_set_bleed_box_round_trip() -> None:
    page = PDPage()
    page.set_bleed_box(PDRectangle(1.0, 2.0, 11.0, 22.0))
    bb = page.get_bleed_box()
    assert (bb.lower_left_x, bb.lower_left_y, bb.upper_right_x, bb.upper_right_y) == (
        1.0,
        2.0,
        11.0,
        22.0,
    )


def test_set_trim_box_round_trip() -> None:
    page = PDPage()
    page.set_trim_box(PDRectangle(3.0, 4.0, 13.0, 24.0))
    tb = page.get_trim_box()
    assert (tb.lower_left_x, tb.lower_left_y, tb.upper_right_x, tb.upper_right_y) == (
        3.0,
        4.0,
        13.0,
        24.0,
    )


def test_set_art_box_round_trip() -> None:
    page = PDPage()
    page.set_art_box(PDRectangle(5.0, 6.0, 15.0, 26.0))
    ab = page.get_art_box()
    assert (ab.lower_left_x, ab.lower_left_y, ab.upper_right_x, ab.upper_right_y) == (
        5.0,
        6.0,
        15.0,
        26.0,
    )


def test_bleed_trim_art_default_to_crop_box() -> None:
    page = PDPage()
    page.set_crop_box(PDRectangle(7.0, 8.0, 17.0, 28.0))
    for getter in (page.get_bleed_box, page.get_trim_box, page.get_art_box):
        rect = getter()
        assert (
            rect.lower_left_x,
            rect.lower_left_y,
            rect.upper_right_x,
            rect.upper_right_y,
        ) == (7.0, 8.0, 17.0, 28.0)


def test_set_bleed_trim_art_none_removes_entries() -> None:
    page = PDPage()
    page.set_crop_box(PDRectangle(0.0, 0.0, 50.0, 50.0))
    page.set_bleed_box(PDRectangle(1.0, 1.0, 49.0, 49.0))
    page.set_trim_box(PDRectangle(2.0, 2.0, 48.0, 48.0))
    page.set_art_box(PDRectangle(3.0, 3.0, 47.0, 47.0))
    page.set_bleed_box(None)
    page.set_trim_box(None)
    page.set_art_box(None)
    # All three fall back to CropBox now.
    for getter in (page.get_bleed_box, page.get_trim_box, page.get_art_box):
        rect = getter()
        assert (
            rect.lower_left_x,
            rect.lower_left_y,
            rect.upper_right_x,
            rect.upper_right_y,
        ) == (0.0, 0.0, 50.0, 50.0)


# ---------- rotation ----------


def test_set_rotation_round_trip() -> None:
    page = PDPage()
    assert page.get_rotation() == 0
    page.set_rotation(90)
    assert page.get_rotation() == 90
    page.set_rotation(180)
    assert page.get_rotation() == 180
    page.set_rotation(270)
    assert page.get_rotation() == 270


def test_rotation_normalises_modulo_360() -> None:
    page = PDPage()
    page.set_rotation(450)  # 450 % 360 == 90
    assert page.get_rotation() == 90
    page.set_rotation(-90)  # negative wraps to 270
    assert page.get_rotation() == 270


# ---------- user unit ----------


def test_user_unit_default_one() -> None:
    page = PDPage()
    assert page.get_user_unit() == 1.0


def test_set_user_unit_round_trip() -> None:
    page = PDPage()
    page.set_user_unit(2.0)
    assert page.get_user_unit() == 2.0
    page.set_user_unit(0.5)
    assert page.get_user_unit() == 0.5


def test_set_user_unit_rejects_non_positive_values() -> None:
    page = PDPage()
    for value in (0.0, -1.0):
        with pytest.raises(ValueError):
            page.set_user_unit(value)


def test_get_user_unit_defaults_for_non_positive_cos_values() -> None:
    page = PDPage()
    page.get_cos_object().set_item(COSName.get_pdf_name("UserUnit"), COSFloat(0))
    assert page.get_user_unit() == 1.0

    page.get_cos_object().set_item(COSName.get_pdf_name("UserUnit"), COSInteger.get(-2))
    assert page.get_user_unit() == 1.0


# ---------- struct parents ----------


def test_struct_parents_default_minus_one() -> None:
    """Absent ``/StructParents`` returns sentinel ``-1`` per upstream."""
    page = PDPage()
    assert page.get_struct_parents() == -1


def test_set_struct_parents_round_trip() -> None:
    page = PDPage()
    page.set_struct_parents(0)
    assert page.get_struct_parents() == 0
    page.set_struct_parents(42)
    assert page.get_struct_parents() == 42
    # Underlying COS value is a COSInteger, not a string or float.
    raw = page.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("StructParents")
    )
    assert isinstance(raw, COSInteger)
    assert raw.value == 42


# ---------- content streams (list form) ----------


def test_get_content_streams_empty_when_absent() -> None:
    page = PDPage()
    assert page.get_content_streams() == []


def test_has_contents_false_when_absent() -> None:
    page = PDPage()
    assert page.has_contents() is False


def test_has_contents_false_for_empty_stream() -> None:
    page = PDPage()
    page.set_contents(COSStream())
    assert page.has_contents() is False


def test_has_contents_true_for_non_empty_stream() -> None:
    page = PDPage()
    s = COSStream()
    s.create_output_stream().write(b"q Q")
    page.set_contents(s)
    assert page.has_contents() is True


def test_has_contents_uses_array_presence_not_substream_size() -> None:
    page = PDPage()
    assert page.has_contents() is False

    page.set_contents(COSArray())
    assert page.has_contents() is False

    page.set_contents(COSArray([COSStream()]))
    assert page.has_contents() is True


def test_get_content_streams_single_stream() -> None:
    page = PDPage()
    s = COSStream()
    s.create_output_stream().write(b"q Q")
    page.set_contents(s)
    streams = page.get_content_streams()
    assert len(streams) == 1
    assert isinstance(streams[0], PDStream)
    assert streams[0].get_cos_object() is s


def test_set_contents_accepts_single_pdstream_wrapper() -> None:
    page = PDPage()
    stream = PDStream()
    with stream.create_output_stream() as out:
        out.write(b"q 1 0 0 1 0 0 cm Q")

    page.set_contents(stream)

    assert page.get_cos_object().get_dictionary_object(COSName.CONTENTS) is stream.get_cos_object()
    assert page.get_contents() == b"q 1 0 0 1 0 0 cm Q"


def test_get_content_streams_array_form() -> None:
    page = PDPage()
    s1 = COSStream()
    s1.create_output_stream().write(b"q")
    s2 = COSStream()
    s2.create_output_stream().write(b"Q")
    arr = COSArray()
    arr.add(s1)
    arr.add(s2)
    page.get_cos_object().set_item(COSName.CONTENTS, arr)  # type: ignore[attr-defined]
    streams = page.get_content_streams()
    assert len(streams) == 2
    assert all(isinstance(s, PDStream) for s in streams)
    assert streams[0].get_cos_object() is s1
    assert streams[1].get_cos_object() is s2
