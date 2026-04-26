from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationCircle,
    PDAnnotationLink,
    PDAnnotationSquare,
    PDAnnotationText,
    PDAnnotationUnknown,
)


# ---------- construction ----------


def test_default_constructor_sets_type_annot() -> None:
    # Concrete instance via subclass — base is abstract by convention.
    ann = PDAnnotationText()
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_constructor_accepts_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Square")  # type: ignore[attr-defined]
    ann = PDAnnotationSquare(raw)
    assert ann.get_cos_object() is raw
    assert ann.get_subtype() == "Square"


def test_constructor_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        PDAnnotationSquare("not-a-dict")  # type: ignore[arg-type]


# ---------- factory dispatch ----------


def test_create_dispatches_link() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Link")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationLink)


def test_create_dispatches_text() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationText)


def test_create_dispatches_square() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Square")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationSquare)


def test_create_dispatches_circle() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Circle")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationCircle)


def test_create_unknown_for_missing_subtype() -> None:
    d = COSDictionary()
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationUnknown)
    assert ann.get_subtype() is None


def test_create_unknown_for_unsupported_subtype() -> None:
    # Widget falls back in cluster #5 lite — see CHANGES.md.
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Widget")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationUnknown)
    assert ann.get_subtype() == "Widget"


def test_create_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        PDAnnotation.create(COSName.get_pdf_name("Annot"))


# ---------- /Rect round-trip ----------


def test_rectangle_round_trip() -> None:
    ann = PDAnnotationText()
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    ann.set_rectangle(rect)
    rt = ann.get_rectangle()
    assert rt is not None
    assert rt.lower_left_x == 10.0
    assert rt.lower_left_y == 20.0
    assert rt.upper_right_x == 110.0
    assert rt.upper_right_y == 220.0


def test_rectangle_absent_returns_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_rectangle() is None


def test_rectangle_clear() -> None:
    ann = PDAnnotationText()
    ann.set_rectangle(PDRectangle(0.0, 0.0, 10.0, 10.0))
    ann.set_rectangle(None)
    assert ann.get_rectangle() is None


# ---------- /Contents round-trip ----------


def test_contents_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_contents("hello world")
    assert ann.get_contents() == "hello world"


def test_contents_clear() -> None:
    ann = PDAnnotationText()
    ann.set_contents("hi")
    ann.set_contents(None)
    assert ann.get_contents() is None


# ---------- /M (modified date) round-trip ----------


def test_modified_date_string_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_modified_date("D:20230101120000Z00'00'")
    assert ann.get_modified_date() == "D:20230101120000Z00'00'"


def test_modified_date_datetime_round_trip() -> None:
    ann = PDAnnotationText()
    when = _dt.datetime(2023, 6, 1, 12, 30, 45, tzinfo=_dt.timezone.utc)
    ann.set_modified_date(when)
    raw = ann.get_modified_date()
    assert raw is not None
    assert raw.startswith("D:20230601123045")


def test_modified_date_clear() -> None:
    ann = PDAnnotationText()
    ann.set_modified_date("D:20230101120000Z")
    ann.set_modified_date(None)
    assert ann.get_modified_date() is None


# ---------- /F flags ----------


def test_flags_default_zero() -> None:
    ann = PDAnnotationText()
    assert ann.get_annotation_flags() == 0
    assert not ann.is_invisible()
    assert not ann.is_printed()


def test_flags_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_annotation_flags(
        PDAnnotation.FLAG_PRINTED | PDAnnotation.FLAG_LOCKED
    )
    assert ann.is_printed()
    assert ann.is_locked()
    assert not ann.is_hidden()


def test_set_flag_individually() -> None:
    ann = PDAnnotationText()
    ann.set_printed(True)
    assert ann.is_printed()
    assert ann.get_annotation_flags() == PDAnnotation.FLAG_PRINTED
    ann.set_printed(False)
    assert not ann.is_printed()
    assert ann.get_annotation_flags() == 0


def test_set_flag_preserves_other_bits() -> None:
    ann = PDAnnotationText()
    ann.set_invisible(True)
    ann.set_printed(True)
    assert ann.is_invisible()
    assert ann.is_printed()
    ann.set_invisible(False)
    assert not ann.is_invisible()
    assert ann.is_printed()


def test_all_flag_accessors_exist() -> None:
    ann = PDAnnotationText()
    for name in (
        "invisible",
        "hidden",
        "printed",
        "no_zoom",
        "no_rotate",
        "no_view",
        "read_only",
        "locked",
        "toggle_no_view",
        "locked_contents",
    ):
        getter = getattr(ann, f"is_{name}")
        setter = getattr(ann, f"set_{name}")
        assert callable(getter)
        assert callable(setter)
        setter(True)
        assert getter()
        setter(False)
        assert not getter()


# ---------- /NM ----------


def test_annotation_name_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_annotation_name("note-1")
    assert ann.get_annotation_name() == "note-1"


def test_annotation_name_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_annotation_name() is None


# ---------- /T ----------


def test_title_popup_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_title_popup("alice")
    assert ann.get_title_popup() == "alice"


def test_title_popup_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_title_popup() is None


# ---------- /Border ----------


def test_border_default() -> None:
    ann = PDAnnotationText()
    border = ann.get_border()
    assert border.size() == 3
    assert border.get_int(0) == 0
    assert border.get_int(1) == 0
    assert border.get_int(2) == 1


def test_border_round_trip() -> None:
    ann = PDAnnotationText()
    arr = COSArray([COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)])
    ann.set_border(arr)
    assert ann.get_border() is arr


def test_border_clear() -> None:
    ann = PDAnnotationText()
    ann.set_border(COSArray([COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)]))
    ann.set_border(None)
    # After clearing, the spec default is returned.
    border = ann.get_border()
    assert border.get_int(0) == 0
    assert border.get_int(2) == 1


# ---------- /C ----------


def test_color_round_trip() -> None:
    ann = PDAnnotationText()
    arr = COSArray([COSFloat(1.0), COSFloat(0.0), COSFloat(0.0)])
    ann.set_color(arr)
    rt = ann.get_color()
    assert rt is arr


def test_color_components_helper() -> None:
    ann = PDAnnotationText()
    ann.set_color_components([0.5, 0.25, 0.75])
    rt = ann.get_color()
    assert rt is not None
    assert rt.size() == 3
    assert rt.to_float_array() == [0.5, 0.25, 0.75]


def test_color_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_color() is None


def test_color_clear() -> None:
    ann = PDAnnotationText()
    ann.set_color_components([0.0, 0.0, 0.0])
    ann.set_color(None)
    assert ann.get_color() is None


# ---------- equality ----------


def test_equal_when_backing_dict_is_same() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    a = PDAnnotation.create(raw)
    b = PDAnnotation.create(raw)
    assert a == b


def test_unequal_when_backing_dict_differs() -> None:
    a = PDAnnotationText()
    b = PDAnnotationText()
    assert a != b


# Ensure unused imports stay referenced (suppresses linter chatter).
_ = COSString
