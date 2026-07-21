from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText


def test_wave636_inheritable_lookup_stops_on_parent_cycle() -> None:
    page_dict = COSDictionary()
    parent = COSDictionary()
    page_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    parent.set_item(COSName.PARENT, page_dict)  # type: ignore[attr-defined]

    page = PDPage(page_dict)

    assert page.get_inherited_cos_object("Missing") is None
    assert page.get_media_box().width == 612.0


def test_wave636_contents_array_direct_clear_and_indirect_streams() -> None:
    page = PDPage()
    empty_stream = COSStream()
    full_stream = COSStream()
    full_stream.set_raw_data(b"BT")
    indirect_stream = COSObject(8, resolved=full_stream)
    contents = COSArray([empty_stream, indirect_stream])

    page.set_contents(contents)

    assert page.has_contents() is True
    assert page.get_contents() == b"\nBT"
    streams = page.get_content_streams()
    assert [stream.get_cos_object() for stream in streams] == [empty_stream, full_stream]

    page.set_contents(COSArray())
    assert page.has_contents() is False

    page.set_contents(contents)
    page.set_contents(None)
    assert page.get_contents() == b""


def test_wave636_single_empty_stream_does_not_count_as_contents() -> None:
    page = PDPage()

    page.set_contents(COSStream())

    assert page.has_contents() is False
    assert page.get_contents() == b""


def test_wave636_annotations_skip_null_entries() -> None:
    """Only ``null`` /Annots members are skipped (upstream's
    ``if (item == null) continue;``). A well-formed dict member dispatches."""
    page = PDPage()
    text = PDAnnotationText()
    annots = COSArray([COSNull.NULL, text.get_cos_object()])
    page.get_cos_object().set_item("Annots", annots)

    assert [annotation.get_cos_object() for annotation in page.get_annotations()] == [
        text.get_cos_object()
    ]


def test_wave636_annotations_log_and_skip_non_dict_member(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-``null``, non-dictionary /Annots member is logged and skipped
    (PDFBOX-6206, upstream 3.0.8): ``getAnnotations`` wraps
    ``PDAnnotation.createAnnotation`` per-item in try/catch(IOException),
    logs the error, and continues — one malformed member no longer aborts
    the whole call. Well-formed members in the same array still dispatch."""
    page = PDPage()
    text = PDAnnotationText()
    annots = COSArray([COSName.get_pdf_name("Bad"), text.get_cos_object()])
    page.get_cos_object().set_item("Annots", annots)

    with caplog.at_level("ERROR", logger="pypdfbox.pdmodel.pd_page"):
        result = page.get_annotations()

    assert [annotation.get_cos_object() for annotation in result] == [
        text.get_cos_object()
    ]
    assert any(
        "Unknown annotation type" in record.getMessage() for record in caplog.records
    )


def test_wave636_box_fallbacks_and_clipping_are_independent() -> None:
    page = PDPage(PDRectangle(0, 0, 100, 100))
    page.set_crop_box(PDRectangle(-5, 5, 80, 120))
    page.set_bleed_box(None)
    page.set_trim_box(None)
    page.set_art_box(None)

    assert page.get_crop_box().lower_left_x == 0
    assert page.get_crop_box().upper_right_y == 100
    assert page.get_bleed_box().upper_right_y == 100
    assert page.get_trim_box().upper_right_y == 100
    assert page.get_art_box().upper_right_y == 100


def test_wave636_direct_numeric_struct_parents_defaults_to_minus_one() -> None:
    page = PDPage()

    assert page.get_struct_parents() == -1

    page.get_cos_object().set_item("StructParents", COSInteger.get(0))
    assert page.get_struct_parents() == 0
