"""Upstream-parity coverage for the PDAnnotation base class.

Mirrors PDF 32000-1 §12.5 Table 168 entries. The handful of accessors
already present in ``test_pd_annotation.py`` (rectangle, contents,
modification date, /F flags individually, /NM, /T, border, color base
case) stay in that file; this module covers the additions that landed
with the base-parity round-out: every flag bit individually, /AS, /P,
/StructParent, /OC and the /C tuple round-trip.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationText,
)

# ---------- /Subtype public setter ----------


def test_subtype_round_trip_via_public_setter() -> None:
    ann = PDAnnotationText()
    ann.set_subtype("Square")
    assert ann.get_subtype() == "Square"


def test_subtype_clear() -> None:
    ann = PDAnnotationText()
    ann.set_subtype(None)
    assert ann.get_subtype() is None


# ---------- /Rect alias ----------


def test_get_rect_is_alias_for_get_rectangle() -> None:
    ann = PDAnnotationText()
    ann.set_rectangle(PDRectangle(1.0, 2.0, 3.0, 4.0))
    rect_a = ann.get_rectangle()
    rect_b = ann.get_rect()
    assert rect_a is not None
    assert rect_b is not None
    assert (
        rect_b.lower_left_x,
        rect_b.lower_left_y,
        rect_b.upper_right_x,
        rect_b.upper_right_y,
    ) == (
        rect_a.lower_left_x,
        rect_a.lower_left_y,
        rect_a.upper_right_x,
        rect_a.upper_right_y,
    )


# ---------- /F flag bits exhaustive ----------


_FLAG_BITS: list[tuple[str, int]] = [
    ("invisible", PDAnnotation.FLAG_INVISIBLE),
    ("hidden", PDAnnotation.FLAG_HIDDEN),
    ("printed", PDAnnotation.FLAG_PRINTED),
    ("no_zoom", PDAnnotation.FLAG_NO_ZOOM),
    ("no_rotate", PDAnnotation.FLAG_NO_ROTATE),
    ("no_view", PDAnnotation.FLAG_NO_VIEW),
    ("read_only", PDAnnotation.FLAG_READ_ONLY),
    ("locked", PDAnnotation.FLAG_LOCKED),
    ("toggle_no_view", PDAnnotation.FLAG_TOGGLE_NO_VIEW),
    ("locked_contents", PDAnnotation.FLAG_LOCKED_CONTENTS),
]


def test_flag_bit_values_match_spec() -> None:
    # Verify the FLAG_* constants are the exact bit positions specified
    # by PDF 32000-1 §12.5.3 Table 165.
    expected = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    actual = [bit for _, bit in _FLAG_BITS]
    assert actual == expected


@pytest.mark.parametrize("name,bit", _FLAG_BITS)
def test_flag_set_and_query(name: str, bit: int) -> None:
    ann = PDAnnotationText()
    setter = getattr(ann, f"set_{name}")
    getter = getattr(ann, f"is_{name}")

    assert not getter()
    assert ann.get_annotation_flags() == 0

    setter(True)
    assert getter()
    assert ann.get_annotation_flags() == bit

    setter(False)
    assert not getter()
    assert ann.get_annotation_flags() == 0


def test_flag_set_does_not_disturb_neighbours() -> None:
    ann = PDAnnotationText()
    # Set every flag, then clear them one at a time and check the rest stay.
    for name, _ in _FLAG_BITS:
        getattr(ann, f"set_{name}")(True)
    expected_total = sum(bit for _, bit in _FLAG_BITS)
    assert ann.get_annotation_flags() == expected_total

    for name, bit in _FLAG_BITS:
        getattr(ann, f"set_{name}")(False)
        expected_total -= bit
        assert ann.get_annotation_flags() == expected_total


# ---------- /NM ----------


def test_annotation_name_round_trip_unique_marker() -> None:
    ann = PDAnnotationText()
    ann.set_annotation_name("uuid-42")
    assert ann.get_annotation_name() == "uuid-42"


def test_annotation_name_clear() -> None:
    ann = PDAnnotationText()
    ann.set_annotation_name("x")
    ann.set_annotation_name(None)
    assert ann.get_annotation_name() is None


# ---------- /M ----------


def test_modified_date_round_trip_string() -> None:
    ann = PDAnnotationText()
    ann.set_modified_date("D:20240101010203Z00'00'")
    assert ann.get_modified_date() == "D:20240101010203Z00'00'"


# ---------- /C colour with 3-tuple ----------


def test_color_round_trip_from_tuple() -> None:
    ann = PDAnnotationText()
    ann.set_color((1.0, 0.5, 0.25))
    rt = ann.get_color()
    assert rt is not None
    assert rt.size() == 3
    assert rt.to_float_array() == [1.0, 0.5, 0.25]


def test_color_round_trip_from_list() -> None:
    ann = PDAnnotationText()
    ann.set_color([0.0, 0.0, 0.0, 1.0])  # CMYK-shaped 4-tuple is also valid.
    rt = ann.get_color()
    assert rt is not None
    assert rt.size() == 4
    assert rt.to_float_array() == [0.0, 0.0, 0.0, 1.0]


def test_color_round_trip_from_cos_array_still_works() -> None:
    ann = PDAnnotationText()
    arr = COSArray([COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)])
    ann.set_color(arr)
    assert ann.get_color() is arr


def test_color_rejects_bad_type() -> None:
    ann = PDAnnotationText()
    with pytest.raises(TypeError):
        ann.set_color(42)  # type: ignore[arg-type]


# ---------- /AS appearance state ----------


def test_appearance_state_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_appearance_state("On")
    assert ann.get_appearance_state() == "On"


def test_appearance_state_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_appearance_state() is None


def test_appearance_state_clear() -> None:
    ann = PDAnnotationText()
    ann.set_appearance_state("Off")
    ann.set_appearance_state(None)
    assert ann.get_appearance_state() is None


# ---------- appearance construction ----------


def test_construct_appearances_base_noop_preserves_dictionary() -> None:
    ann = PDAnnotationText()
    raw = ann.get_cos_object()
    before = list(raw.entry_set())

    ann.construct_appearances()
    ann.construct_appearances(None)

    assert ann.get_cos_object() is raw
    assert list(raw.entry_set()) == before


# ---------- /P parent page back-pointer ----------


def test_p_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_p() is None


def test_p_round_trip_with_pd_page() -> None:
    ann = PDAnnotationText()
    page = PDPage()
    ann.set_p(page)
    rt = ann.get_p()
    assert rt is not None
    assert rt is page.get_cos_object()


def test_p_round_trip_with_raw_dict() -> None:
    ann = PDAnnotationText()
    page_dict = COSDictionary()
    page_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))  # type: ignore[attr-defined]
    ann.set_p(page_dict)
    assert ann.get_p() is page_dict


def test_p_clear() -> None:
    ann = PDAnnotationText()
    ann.set_p(PDPage())
    ann.set_p(None)
    assert ann.get_p() is None


def test_p_rejects_bad_type() -> None:
    ann = PDAnnotationText()
    with pytest.raises(TypeError):
        ann.set_p("not-a-page")  # type: ignore[arg-type]


# ---------- /StructParent ----------


def test_struct_parent_default_minus_one() -> None:
    ann = PDAnnotationText()
    assert ann.get_struct_parent() == -1


def test_struct_parent_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_struct_parent(7)
    assert ann.get_struct_parent() == 7
    # And it actually wrote to /StructParent in the COS dict.
    assert ann.get_cos_object().get_int(
        COSName.get_pdf_name("StructParent"), -999
    ) == 7


def test_struct_parent_round_trip_zero() -> None:
    ann = PDAnnotationText()
    ann.set_struct_parent(0)
    assert ann.get_struct_parent() == 0


# ---------- /OC optional content ----------


def test_optional_content_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_optional_content() is None


def test_optional_content_round_trip_with_ocg() -> None:
    ann = PDAnnotationText()
    ocg_dict = COSDictionary()
    ocg_dict.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    ocg_dict.set_item(
        COSName.get_pdf_name("Name"),
        COSName.get_pdf_name("layer-1"),
    )
    ann.set_optional_content(ocg_dict)
    rt = ann.get_optional_content()
    assert rt is not None
    assert isinstance(rt, PDOptionalContentGroup)
    assert rt.get_cos_object() is ocg_dict


def test_optional_content_round_trip_with_property_list_wrapper() -> None:
    ann = PDAnnotationText()
    ocg_dict = COSDictionary()
    ocg_dict.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    ocg = PDOptionalContentGroup(ocg_dict)
    ann.set_optional_content(ocg)
    rt = ann.get_optional_content()
    assert rt is not None
    assert rt.get_cos_object() is ocg_dict


def test_optional_content_clear() -> None:
    ann = PDAnnotationText()
    ocg_dict = COSDictionary()
    ocg_dict.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    ann.set_optional_content(ocg_dict)
    ann.set_optional_content(None)
    assert ann.get_optional_content() is None


def test_optional_content_rejects_bad_type() -> None:
    ann = PDAnnotationText()
    with pytest.raises(TypeError):
        ann.set_optional_content(42)  # type: ignore[arg-type]


# Suppress unused-import lint for fixtures we wire above.
_ = COSInteger
