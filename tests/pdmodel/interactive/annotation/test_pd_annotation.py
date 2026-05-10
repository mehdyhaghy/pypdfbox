from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotation3D,
    PDAnnotationCircle,
    PDAnnotationLink,
    PDAnnotationPrinterMark,
    PDAnnotationRedact,
    PDAnnotationSquare,
    PDAnnotationText,
    PDAnnotationTrapNet,
    PDAnnotationUnknown,
    PDAnnotationWatermark,
    PDAppearanceDictionary,
    PDAppearanceStream,
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


@pytest.mark.parametrize(
    ("subtype", "expected_cls"),
    [
        ("Redact", PDAnnotationRedact),
        ("3D", PDAnnotation3D),
        ("Watermark", PDAnnotationWatermark),
        ("PrinterMark", PDAnnotationPrinterMark),
        ("TrapNet", PDAnnotationTrapNet),
    ],
)
def test_create_dispatches_recent_annotation_subtypes(
    subtype: str, expected_cls: type[PDAnnotation]
) -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, subtype)  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, expected_cls)
    assert ann.get_subtype() == subtype


def test_create_unknown_for_unsupported_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "TotallyMadeUpSubtype")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationUnknown)
    assert ann.get_subtype() == "TotallyMadeUpSubtype"


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
    when = _dt.datetime(2023, 6, 1, 12, 30, 45, tzinfo=_dt.UTC)
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


# ---------- constructor /Type defaulting ----------


def test_constructor_defaults_type_when_missing_on_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Square")  # type: ignore[attr-defined]
    # No /Type is set on the raw dict.
    ann = PDAnnotationSquare(raw)
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_constructor_leaves_existing_non_annot_type_alone() -> None:
    """Upstream only logs a warning when /Type is non-/Annot — it does
    not overwrite. We follow that."""
    raw = COSDictionary()
    raw.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject")
    )
    raw.set_name(COSName.SUBTYPE, "Square")  # type: ignore[attr-defined]
    ann = PDAnnotationSquare(raw)
    assert ann.get_cos_object().get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]


# ---------- /Border zero-padding ----------


def test_border_pads_short_array_with_zero() -> None:
    """Adobe Reader behaviour (PDFBOX-…) — missing border entries default
    to 0; a stored two-element /Border [5 6] returns [5 6 0]."""
    ann = PDAnnotationText()
    ann.set_border(COSArray([COSInteger.get(5), COSInteger.get(6)]))
    rt = ann.get_border()
    assert rt.size() == 3
    assert rt.get_int(0) == 5
    assert rt.get_int(1) == 6
    assert rt.get_int(2) == 0


def test_border_pads_empty_array_with_zero() -> None:
    ann = PDAnnotationText()
    ann.set_border(COSArray())
    rt = ann.get_border()
    assert rt.size() == 3
    assert rt.get_int(0) == 0
    assert rt.get_int(1) == 0
    assert rt.get_int(2) == 0


def test_border_pad_does_not_mutate_persisted_array() -> None:
    """Padding must copy — the stored COSArray must remain its original
    size so we don't silently rewrite the PDF on read."""
    ann = PDAnnotationText()
    stored = COSArray([COSInteger.get(7)])
    ann.set_border(stored)
    # Pull the padded view; original must remain untouched.
    _ = ann.get_border()
    assert stored.size() == 1


def test_border_full_array_returned_as_is() -> None:
    ann = PDAnnotationText()
    arr = COSArray(
        [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)]
    )
    ann.set_border(arr)
    # No padding required → exact same instance.
    assert ann.get_border() is arr


# ---------- get_page / set_page upstream-named accessors ----------


def test_get_page_returns_p_dictionary() -> None:
    ann = PDAnnotationText()
    page_dict = COSDictionary()
    page_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
    )
    ann.set_p(page_dict)
    assert ann.get_page() is page_dict


def test_set_page_writes_p_entry() -> None:
    ann = PDAnnotationText()
    page_dict = COSDictionary()
    page_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
    )
    ann.set_page(page_dict)
    assert ann.get_p() is page_dict
    assert ann.get_page() is page_dict


def test_set_page_none_clears() -> None:
    ann = PDAnnotationText()
    ann.set_page(COSDictionary())
    ann.set_page(None)
    assert ann.get_page() is None


def test_get_page_none_when_absent() -> None:
    ann = PDAnnotationText()
    assert ann.get_page() is None


# ---------- get_normal_appearance_stream ----------


def test_normal_appearance_stream_none_when_no_ap() -> None:
    ann = PDAnnotationText()
    assert ann.get_normal_appearance_stream() is None


def test_normal_appearance_stream_none_when_ap_lacks_n() -> None:
    ann = PDAnnotationText()
    ann.set_appearance_dictionary(PDAppearanceDictionary())
    # /AP exists but has no /N entry.
    assert ann.get_normal_appearance_stream() is None


def test_normal_appearance_stream_direct_stream() -> None:
    """When /AP /N is a direct appearance stream, return it wrapped."""
    ann = PDAnnotationText()
    ap = COSDictionary()
    stream = COSStream()
    stream.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject")
    )
    stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    ap.set_item(COSName.get_pdf_name("N"), stream)
    ann.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
    result = ann.get_normal_appearance_stream()
    assert isinstance(result, PDAppearanceStream)
    assert result.get_cos_object() is stream


def test_normal_appearance_stream_state_keyed() -> None:
    """When /AP /N is a state-keyed subdict, return the entry that
    matches the current /AS."""
    ann = PDAnnotationText()
    ap = COSDictionary()
    n_subdict = COSDictionary()
    on_stream = COSStream()
    on_stream.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject")
    )
    on_stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    off_stream = COSStream()
    off_stream.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject")
    )
    off_stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    n_subdict.set_item(COSName.get_pdf_name("On"), on_stream)
    n_subdict.set_item(COSName.get_pdf_name("Off"), off_stream)
    ap.set_item(COSName.get_pdf_name("N"), n_subdict)
    ann.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
    ann.set_appearance_state("On")
    result = ann.get_normal_appearance_stream()
    assert isinstance(result, PDAppearanceStream)
    assert result.get_cos_object() is on_stream
    ann.set_appearance_state("Off")
    result = ann.get_normal_appearance_stream()
    assert isinstance(result, PDAppearanceStream)
    assert result.get_cos_object() is off_stream


def test_normal_appearance_stream_state_keyed_unknown_state() -> None:
    """A state name that isn't in the subdict yields None — we don't
    invent a stream."""
    ann = PDAnnotationText()
    ap = COSDictionary()
    n_subdict = COSDictionary()
    on_stream = COSStream()
    n_subdict.set_item(COSName.get_pdf_name("On"), on_stream)
    ap.set_item(COSName.get_pdf_name("N"), n_subdict)
    ann.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
    ann.set_appearance_state("Missing")
    assert ann.get_normal_appearance_stream() is None


def test_normal_appearance_stream_state_keyed_no_state_set() -> None:
    """Subdict /N with no /AS entry on the annotation: we return None
    rather than guessing a state."""
    ann = PDAnnotationText()
    ap = COSDictionary()
    n_subdict = COSDictionary()
    on_stream = COSStream()
    n_subdict.set_item(COSName.get_pdf_name("On"), on_stream)
    ap.set_item(COSName.get_pdf_name("N"), n_subdict)
    ann.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
    # No /AS on the annotation.
    assert ann.get_appearance_state() is None
    assert ann.get_normal_appearance_stream() is None


# ---------- create_annotation (upstream-named factory) ----------


def test_create_annotation_dispatches_link() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Link")  # type: ignore[attr-defined]
    ann = PDAnnotation.create_annotation(d)
    assert isinstance(ann, PDAnnotationLink)


def test_create_annotation_unknown_for_missing_subtype() -> None:
    d = COSDictionary()
    ann = PDAnnotation.create_annotation(d)
    assert isinstance(ann, PDAnnotationUnknown)


def test_create_annotation_raises_oserror_for_non_dict() -> None:
    """Upstream throws ``IOException("Error: Unknown annotation type …")``
    when the input is not a COSDictionary; we surface that as
    :class:`OSError` per the CLAUDE.md mapping."""
    with pytest.raises(OSError):
        PDAnnotation.create_annotation(COSName.get_pdf_name("Annot"))


# ---------- equals / hash_code (upstream-named aliases) ----------


def test_equals_true_on_shared_dict() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    a = PDAnnotation.create(raw)
    b = PDAnnotation.create(raw)
    assert a.equals(b)


def test_equals_self() -> None:
    ann = PDAnnotationText()
    assert ann.equals(ann)


def test_equals_false_on_distinct_dicts() -> None:
    a = PDAnnotationText()
    b = PDAnnotationText()
    assert not a.equals(b)


def test_equals_false_on_non_annotation() -> None:
    ann = PDAnnotationText()
    assert not ann.equals("not an annotation")
    assert not ann.equals(None)


def test_hash_code_matches_dunder_hash() -> None:
    ann = PDAnnotationText()
    assert ann.hash_code() == hash(ann)


def test_hash_code_stable_across_calls() -> None:
    ann = PDAnnotationText()
    first = ann.hash_code()
    second = ann.hash_code()
    assert first == second


# Ensure unused imports stay referenced (suppresses linter chatter).
_ = COSString
