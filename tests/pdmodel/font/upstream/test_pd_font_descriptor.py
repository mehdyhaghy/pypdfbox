"""Ported upstream tests for :class:`PDFontDescriptor`.

PDFBox 3.0.x has **no dedicated** ``PDFontDescriptorTest.java`` — the
upstream surface is exercised indirectly through ``PDFontTest`` and the
font subsetter integration tests. The cases below mirror what an
explicit ``PDFontDescriptorTest`` *would* assert if upstream had written
one, derived line-by-line from the Java source at::

    pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontDescriptor.java
    pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDPanose.java
    pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDPanoseClassification.java

Each test pins one Javadoc-documented contract from those files (default
values, flag bit masks, /Type entry written by the package-private
constructor, /CharSet COSString storage, /CIDSet stream wrapping, Panose
12-byte layout, etc.). The hand-written file in
:mod:`tests.pdmodel.font.test_pd_font_descriptor` and the parity file in
:mod:`tests.pdmodel.font.test_pd_font_descriptor_parity` cover the wider
caller-facing surface; this file pins the contract that *would* be
ported one-to-one if upstream ever adds a dedicated test.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    PDFontDescriptor,
    PDPanose,
    PDPanoseClassification,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- constructors ----------


def test_default_constructor_writes_type_font_descriptor() -> None:
    # Mirrors: PDFontDescriptor() { dic.setItem(TYPE, FONT_DESC); }
    fd = PDFontDescriptor()
    cos = fd.get_cos_object()
    type_value = cos.get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(type_value, COSName)
    assert type_value.name == "FontDescriptor"


def test_constructor_from_dictionary_wraps_argument() -> None:
    # Mirrors: PDFontDescriptor(COSDictionary desc) { dic = desc; }
    cos = COSDictionary()
    fd = PDFontDescriptor(cos)
    assert fd.get_cos_object() is cos


# ---------- flag predicate masks ----------
# Mirrors the nine `private static final int FLAG_*` constants in upstream.


@pytest.mark.parametrize(
    ("setter", "predicate", "mask"),
    [
        ("set_fixed_pitch", "is_fixed_pitch", 1),
        ("set_serif", "is_serif", 2),
        ("set_symbolic", "is_symbolic", 4),
        ("set_script", "is_script", 8),
        ("set_non_symbolic", "is_non_symbolic", 32),
        ("set_italic", "is_italic", 64),
        ("set_all_cap", "is_all_cap", 65536),
        ("set_small_cap", "is_small_cap", 131072),
        ("set_force_bold", "is_force_bold", 262144),
    ],
)
def test_flag_bit_round_trip(setter: str, predicate: str, mask: int) -> None:
    fd = PDFontDescriptor()
    assert getattr(fd, predicate)() is False

    getattr(fd, setter)(True)
    assert getattr(fd, predicate)() is True
    assert fd.get_flags() == mask

    getattr(fd, setter)(False)
    assert getattr(fd, predicate)() is False
    assert fd.get_flags() == 0


def test_flags_default_zero_when_unset() -> None:
    # Mirrors: dic.getInt(COSName.FLAGS, 0)
    assert PDFontDescriptor().get_flags() == 0


# ---------- string / name / float defaults ----------


def test_font_name_default_null() -> None:
    # Mirrors: dic.getNameAsString(COSName.FONT_NAME) -> null
    assert PDFontDescriptor().get_font_name() is None


def test_font_family_default_null() -> None:
    # Mirrors: dic.getString(COSName.FONT_FAMILY) -> null
    assert PDFontDescriptor().get_font_family() is None


def test_font_stretch_default_null() -> None:
    # Mirrors: dic.getNameAsString(COSName.FONT_STRETCH) -> null
    assert PDFontDescriptor().get_font_stretch() is None


def test_font_weight_default_zero() -> None:
    # Mirrors: dic.getFloat(COSName.FONT_WEIGHT, 0)
    assert PDFontDescriptor().get_font_weight() == 0.0


@pytest.mark.parametrize(
    "getter",
    [
        "get_italic_angle",
        "get_ascent",
        "get_descent",
        "get_leading",
        "get_cap_height",
        "get_x_height",
        "get_stem_v",
        "get_stem_h",
        "get_avg_width",
        "get_max_width",
        "get_missing_width",
    ],
)
def test_numeric_metric_defaults_to_zero(getter: str) -> None:
    """All numeric metrics default to 0 when the entry is absent (Table 122).
    Mirrors the upstream ``dic.getFloat(KEY, 0)`` pattern."""
    fd = PDFontDescriptor()
    assert getattr(fd, getter)() == 0.0


# ---------- font name storage ----------


def test_set_font_name_stores_as_cos_name() -> None:
    # Mirrors: dic.setItem(FONT_NAME, COSName.getPDFName(fontName))
    fd = PDFontDescriptor()
    fd.set_font_name("Helvetica")
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontName"))
    assert isinstance(raw, COSName)
    assert raw.name == "Helvetica"


def test_set_font_family_stores_as_cos_string() -> None:
    # Mirrors: dic.setItem(FONT_FAMILY, new COSString(fontFamily))
    fd = PDFontDescriptor()
    fd.set_font_family("Helvetica")
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontFamily"))
    assert isinstance(raw, COSString)
    assert raw.get_string() == "Helvetica"


def test_set_font_stretch_stores_as_cos_name() -> None:
    # Mirrors: dic.setItem(FONT_STRETCH, COSName.getPDFName(fontStretch))
    fd = PDFontDescriptor()
    fd.set_font_stretch("Condensed")
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontStretch"))
    assert isinstance(raw, COSName)
    assert raw.name == "Condensed"


def test_set_character_set_stores_as_cos_string() -> None:
    # Mirrors: dic.setItem(CHAR_SET, new COSString(charSet))
    fd = PDFontDescriptor()
    fd.set_character_set("/A/B")
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CharSet"))
    assert isinstance(raw, COSString)
    assert raw.get_string() == "/A/B"


# ---------- /FontBBox ----------


def test_get_font_bounding_box_null_when_absent() -> None:
    # Mirrors: rect == null -> retval == null
    assert PDFontDescriptor().get_font_bounding_box() is None


def test_set_font_bounding_box_round_trip() -> None:
    fd = PDFontDescriptor()
    rect = PDRectangle(-100.0, -200.0, 1000.0, 900.0)
    fd.set_font_bounding_box(rect)

    out = fd.get_font_bounding_box()
    assert isinstance(out, PDRectangle)
    assert out.lower_left_x == pytest.approx(-100.0)
    assert out.upper_right_y == pytest.approx(900.0)


def test_set_font_bounding_box_null_clears_entry() -> None:
    # Mirrors: rect == null -> dic.setItem(FONT_BBOX, null)
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, 0.0, 100.0, 100.0))
    fd.set_font_bounding_box(None)
    assert fd.get_font_bounding_box() is None


# ---------- CapHeight / XHeight PDFBOX-429 abs() workaround ----------


def test_cap_height_abs_workaround_only_on_dict_read() -> None:
    # Mirrors getCapHeight() lines 522-532: the abs() workaround
    # (capHeight = Math.abs(dic.getFloat(CAP_HEIGHT,0))) fires ONLY on the
    # lazy cache-miss read (capHeight == Float.NEGATIVE_INFINITY).
    # setCapHeight (lines 541-544) writes the dict AND caches the RAW value
    # (this.capHeight = capHeight), so a re-read returns the raw negative.
    from pypdfbox.cos import COSDictionary, COSName

    fd = PDFontDescriptor()
    fd.set_cap_height(-700.0)
    assert fd.get_cap_height() == pytest.approx(-700.0)  # cached raw, not abs

    d = COSDictionary()
    d.set_float(COSName.get_pdf_name("CapHeight"), -700.0)
    assert PDFontDescriptor(d).get_cap_height() == pytest.approx(700.0)  # abs


def test_x_height_abs_workaround_only_on_dict_read() -> None:
    # Mirrors getXHeight() lines 552-562 / setXHeight() lines 570-573.
    from pypdfbox.cos import COSDictionary, COSName

    fd = PDFontDescriptor()
    fd.set_x_height(-450.0)
    assert fd.get_x_height() == pytest.approx(-450.0)

    d = COSDictionary()
    d.set_float(COSName.get_pdf_name("XHeight"), -450.0)
    assert PDFontDescriptor(d).get_x_height() == pytest.approx(450.0)


# ---------- /Widths and /MissingWidth predicates ----------


def test_has_widths_false_by_default() -> None:
    # Mirrors: containsKey(WIDTHS) || containsKey(MISSING_WIDTH)
    assert PDFontDescriptor().has_widths() is False


def test_has_missing_width_false_by_default() -> None:
    assert PDFontDescriptor().has_missing_width() is False


def test_has_widths_true_with_only_missing_width() -> None:
    fd = PDFontDescriptor()
    fd.set_missing_width(250.0)
    assert fd.has_widths() is True
    assert fd.has_missing_width() is True


# ---------- font program streams ----------


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_font_file", "set_font_file"),
        ("get_font_file2", "set_font_file2"),
        ("get_font_file3", "set_font_file3"),
        ("get_cid_set", "set_cid_set"),
    ],
)
def test_font_program_stream_default_null(getter: str, setter: str) -> None:
    # Mirrors: stream != null ? new PDStream(stream) : null
    fd = PDFontDescriptor()
    assert getattr(fd, getter)() is None


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_font_file", "set_font_file"),
        ("get_font_file2", "set_font_file2"),
        ("get_font_file3", "set_font_file3"),
        ("get_cid_set", "set_cid_set"),
    ],
)
def test_font_program_stream_round_trip(getter: str, setter: str) -> None:
    fd = PDFontDescriptor()
    raw = COSStream()
    getattr(fd, setter)(PDStream(raw))

    out = getattr(fd, getter)()
    assert isinstance(out, PDStream)
    assert out.get_cos_object() is raw


# ---------- /Style /Panose ----------


def test_get_panose_null_when_style_missing() -> None:
    # Mirrors: style == null -> return null
    assert PDFontDescriptor().get_panose() is None


def test_get_panose_returns_wrapper_when_style_holds_12_bytes() -> None:
    # Mirrors: bytes.length >= PDPanose.LENGTH (=12) -> new PDPanose(bytes)
    fd = PDFontDescriptor()
    style = COSDictionary()
    payload = bytes([0x00, 0x08]) + bytes([2, 11, 6, 3, 5, 4, 5, 2, 2, 4])
    style.set_item(COSName.get_pdf_name("Panose"), COSString(payload))
    fd.get_cos_object().set_item(COSName.get_pdf_name("Style"), style)

    panose = fd.get_panose()
    assert isinstance(panose, PDPanose)
    assert panose.get_family_class() == 8


def test_pd_panose_length_constant_is_12() -> None:
    # Mirrors: public static final int LENGTH = 12;
    assert PDPanose.LENGTH == 12


def test_pd_panose_classification_length_constant_is_10() -> None:
    # Mirrors: public static final int LENGTH = 10;
    assert PDPanoseClassification.LENGTH == 10


def test_pd_panose_get_family_class_signed_negative_high_byte() -> None:
    # Mirrors: (bytes[0] << 8) | (bytes[1] & 0xff) where bytes[0] is signed.
    panose = PDPanose(b"\xff\x00" + b"\x00" * 10)
    # ((byte)0xff) << 8 | 0x00 == -256
    assert panose.get_family_class() == -256


def test_pd_panose_classification_per_byte_accessors() -> None:
    # Mirrors: bytes[0]..bytes[9] -> familyKind..xHeight
    cls = PDPanoseClassification(bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]))
    assert cls.get_family_kind() == 0
    assert cls.get_serif_style() == 1
    assert cls.get_weight() == 2
    assert cls.get_proportion() == 3
    assert cls.get_contrast() == 4
    assert cls.get_stroke_variation() == 5
    assert cls.get_arm_style() == 6
    assert cls.get_letterform() == 7
    assert cls.get_midline() == 8
    assert cls.get_x_height() == 9


def test_pd_panose_get_panose_returns_classification() -> None:
    # Mirrors: Arrays.copyOfRange(bytes, 2, 12); new PDPanoseClassification(panose)
    raw = bytes([0x00, 0x08]) + bytes(range(10, 20))
    panose = PDPanose(raw)
    cls = panose.get_panose()
    assert isinstance(cls, PDPanoseClassification)
    assert cls.get_bytes() == bytes(range(10, 20))
