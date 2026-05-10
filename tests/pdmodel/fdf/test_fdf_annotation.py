from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.fdf import FDFAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_default_constructor_stamps_type_annot() -> None:
    a = FDFAnnotation()
    type_key = COSName.get_pdf_name("Type")
    assert a.get_cos_object().get_dictionary_object(type_key) is COSName.get_pdf_name("Annot")


def test_wraps_existing_dict_without_overwriting_type() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Custom"))
    a = FDFAnnotation(d)
    # Existing /Type respected.
    type_key = COSName.get_pdf_name("Type")
    assert a.get_cos_object().get_dictionary_object(type_key) is COSName.get_pdf_name("Custom")


def test_page_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_page() == -1  # default sentinel from get_int
    a.set_page(3)
    assert a.get_page() == 3


def test_name_contents_title_round_trip() -> None:
    a = FDFAnnotation()
    a.set_name("annot-1")
    a.set_contents("hello world")
    a.set_title("alice")
    assert a.get_name() == "annot-1"
    assert a.get_contents() == "hello world"
    assert a.get_title() == "alice"


def test_subtype_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_subtype() is None
    a.set_subtype("Text")
    assert a.get_subtype() == "Text"
    a.set_subtype(None)
    assert a.get_subtype() is None


def test_rectangle_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_rectangle() is None
    a.set_rectangle((10.0, 20.0, 30.5, 40.5))
    assert a.get_rectangle() == (10.0, 20.0, 30.5, 40.5)
    a.set_rectangle(None)
    assert a.get_rectangle() is None


def test_set_rectangle_accepts_pd_rectangle() -> None:
    a = FDFAnnotation()
    a.set_rectangle(PDRectangle(1.0, 2.0, 3.0, 4.0))
    assert a.get_rectangle() == (1.0, 2.0, 3.0, 4.0)


def test_get_rectangle_as_pd_rectangle() -> None:
    a = FDFAnnotation()
    assert a.get_rectangle_as_pd_rectangle() is None
    a.set_rectangle((10.0, 20.0, 30.0, 40.0))
    rect = a.get_rectangle_as_pd_rectangle()
    assert rect is not None
    assert rect.lower_left_x == 10.0
    assert rect.upper_right_y == 40.0


def test_color_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_color() is None
    a.set_color((1.0, 0.5, 0.0))
    assert a.get_color() == (1.0, 0.5, 0.0)


def test_flags_default_zero() -> None:
    a = FDFAnnotation()
    assert a.get_flags() == 0
    a.set_flags(7)
    assert a.get_flags() == 7


def test_name_attribute_round_trip() -> None:
    a = FDFAnnotation()
    a.set_name_attribute("Note")
    assert a.get_name_attribute() == "Note"


def test_modified_date_round_trip() -> None:
    a = FDFAnnotation()
    a.set_modified_date("D:20260427120000Z")
    assert a.get_modified_date() == "D:20260427120000Z"


# ---------------- individual flag accessors ----------------


@pytest.mark.parametrize(
    ("getter", "setter", "bit"),
    [
        ("is_invisible", "set_invisible", 1 << 0),
        ("is_hidden", "set_hidden", 1 << 1),
        ("is_printed", "set_printed", 1 << 2),
        ("is_no_zoom", "set_no_zoom", 1 << 3),
        ("is_no_rotate", "set_no_rotate", 1 << 4),
        ("is_no_view", "set_no_view", 1 << 5),
        ("is_read_only", "set_read_only", 1 << 6),
        ("is_locked", "set_locked", 1 << 7),
        ("is_toggle_no_view", "set_toggle_no_view", 1 << 8),
        ("is_locked_contents", "set_locked_contents", 1 << 9),
    ],
)
def test_individual_flag_accessor(getter: str, setter: str, bit: int) -> None:
    a = FDFAnnotation()
    assert getattr(a, getter)() is False
    getattr(a, setter)(True)
    assert getattr(a, getter)() is True
    assert (a.get_flags() & bit) == bit
    getattr(a, setter)(False)
    assert getattr(a, getter)() is False
    assert (a.get_flags() & bit) == 0


def test_flags_are_independent() -> None:
    a = FDFAnnotation()
    a.set_invisible(True)
    a.set_locked(True)
    a.set_printed(True)
    assert a.is_invisible()
    assert a.is_locked()
    assert a.is_printed()
    assert not a.is_hidden()
    a.set_locked(False)
    assert a.is_invisible()
    assert not a.is_locked()
    assert a.is_printed()


# ---------------- /M date alias ----------------


def test_date_alias_round_trip() -> None:
    """``set_date``/``get_date`` (Java parity) and the modified-date pair
    operate on the same /M entry."""
    a = FDFAnnotation()
    a.set_date("D:20260101120000Z")
    assert a.get_date() == "D:20260101120000Z"
    assert a.get_modified_date() == "D:20260101120000Z"
    a.set_modified_date("D:20260202020202Z")
    assert a.get_date() == "D:20260202020202Z"


# ---------------- /CreationDate ----------------


def test_creation_date_string_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_creation_date() is None
    a.set_creation_date("D:20260301120000Z")
    parsed = a.get_creation_date()
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 3
    assert parsed.day == 1


def test_creation_date_datetime_round_trip() -> None:
    a = FDFAnnotation()
    when = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    a.set_creation_date(when)
    parsed = a.get_creation_date()
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.hour == 12


# ---------------- /CA opacity ----------------


def test_opacity_default_one() -> None:
    a = FDFAnnotation()
    assert a.get_opacity() == 1.0


def test_opacity_round_trip() -> None:
    a = FDFAnnotation()
    a.set_opacity(0.5)
    assert a.get_opacity() == pytest.approx(0.5)


# ---------------- /Subj subject ----------------


def test_subject_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_subject() is None
    a.set_subject("Comment")
    assert a.get_subject() == "Comment"


# ---------------- /IT intent ----------------


def test_intent_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_intent() is None
    a.set_intent("FreeTextTypewriter")
    assert a.get_intent() == "FreeTextTypewriter"


# ---------------- /RC rich contents ----------------


def test_rich_contents_default_empty_string() -> None:
    a = FDFAnnotation()
    # upstream getStringOrStream returns "" when entry is missing
    assert a.get_rich_contents() == ""


def test_rich_contents_round_trip() -> None:
    a = FDFAnnotation()
    a.set_rich_contents("<body>hi</body>")
    assert a.get_rich_contents() == "<body>hi</body>"


def test_rich_contents_from_cos_stream() -> None:
    """Upstream ``getRichContents`` accepts a stream-shaped /RC entry."""
    a = FDFAnnotation()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"<rich/>")
    a.get_cos_object().set_item(COSName.get_pdf_name("RC"), stream)
    assert a.get_rich_contents() == "<rich/>"


# ---------------- /BS border style ----------------


def test_border_style_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_border_style() is None
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    a.set_border_style(bs)
    fetched = a.get_border_style()
    assert fetched is not None
    assert fetched.get_width() == pytest.approx(2.0)


def test_border_style_clear() -> None:
    a = FDFAnnotation()
    a.set_border_style(PDBorderStyleDictionary())
    assert a.get_border_style() is not None
    a.set_border_style(None)
    assert a.get_border_style() is None


# ---------------- /BE border effect ----------------


def test_border_effect_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_border_effect() is None
    be = PDBorderEffectDictionary()
    be.set_intensity(1.5)
    a.set_border_effect(be)
    fetched = a.get_border_effect()
    assert fetched is not None
    assert fetched.get_intensity() == pytest.approx(1.5)


def test_border_effect_clear() -> None:
    a = FDFAnnotation()
    a.set_border_effect(PDBorderEffectDictionary())
    assert a.get_border_effect() is not None
    a.set_border_effect(None)
    assert a.get_border_effect() is None


# ---------------- protected helpers ----------------


def test_get_string_or_stream_none() -> None:
    a = FDFAnnotation()
    assert a.get_string_or_stream(None) == ""


def test_get_string_or_stream_string() -> None:
    a = FDFAnnotation()
    assert a.get_string_or_stream(COSString("hello")) == "hello"


def test_get_string_or_stream_stream() -> None:
    a = FDFAnnotation()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"streamed")
    assert a.get_string_or_stream(stream) == "streamed"


def test_get_string_or_stream_other_returns_empty() -> None:
    a = FDFAnnotation()
    # A COSName is neither a string nor a stream — upstream falls through to "".
    assert a.get_string_or_stream(COSName.get_pdf_name("Foo")) == ""


def test_parse_rectangle_attributes_round_trip() -> None:
    a = FDFAnnotation()
    assert a.parse_rectangle_attributes("1,2,3,4", "boom") == [1.0, 2.0, 3.0, 4.0]


def test_parse_rectangle_attributes_wrong_count_raises() -> None:
    a = FDFAnnotation()
    with pytest.raises(OSError):
        a.parse_rectangle_attributes("1,2,3", "wrong count")


def test_parse_floats_round_trip() -> None:
    a = FDFAnnotation()
    assert a.parse_floats(["1.5", "2.25", "-3"]) == [1.5, 2.25, -3.0]


def test_create_rectangle_from_attributes_round_trip() -> None:
    a = FDFAnnotation()
    rect = a.create_rectangle_from_attributes("10,20,30,40", "boom")
    assert rect.lower_left_x == 10.0
    assert rect.lower_left_y == 20.0
    assert rect.upper_right_x == 30.0
    assert rect.upper_right_y == 40.0


def test_create_rectangle_from_attributes_wrong_count_raises() -> None:
    a = FDFAnnotation()
    with pytest.raises(OSError):
        a.create_rectangle_from_attributes("1,2", "boom")
