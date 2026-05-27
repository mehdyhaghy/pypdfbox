from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
)
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont, PDType1Font
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    StandardEncoding,
    WinAnsiEncoding,
)
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_FORCE_BOLD,
    FLAG_ITALIC,
    FLAG_SYMBOLIC,
)


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_defaults_without_optional_font_entries_are_conservative() -> None:
    font = PDType1Font()

    assert font.get_first_char() == -1
    assert font.get_last_char() == -1
    assert font.get_widths() == []
    assert font.get_average_font_width() == 0.0
    assert font.get_encoding() is None
    # No /Encoding entry: get_encoding_typed falls back to
    # read_encoding_from_font() (mirroring upstream PDSimpleFont.readEncoding),
    # which for a bare PDType1Font bottoms out at StandardEncoding — verified
    # against the live PDFBox oracle (BuiltinEncodingProbe: bare Type1 ->
    # StandardEncoding, 65 -> A). Was None pre-wave-1434 (the blank-render bug).
    assert isinstance(font.get_encoding_typed(), StandardEncoding)
    assert font.get_font_descriptor() is None
    assert font.get_symbolic_flag() is None
    # With the StandardEncoding now resolved, is_font_symbolic returns False
    # (a Latin encoding guarantees nonsymbolic) — matching upstream
    # PDSimpleFont.isFontSymbolic. is_symbolic still defaults False here.
    assert font.is_symbolic() is False
    # StandardEncoding maps code 65 -> "A" -> unicode "A" via the glyph list.
    assert font.to_unicode(65) == "A"
    assert font.will_be_subset() is False


def test_char_range_reads_numeric_values_and_rejects_malformed_shapes() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()

    cos.set_item(_name("FirstChar"), COSFloat(31.9))
    cos.set_item(_name("LastChar"), COSFloat(126.2))
    assert font.get_first_char() == 31
    assert font.get_last_char() == 126

    cos.set_item(_name("FirstChar"), _name("not-a-number"))
    cos.set_item(_name("LastChar"), COSArray())
    assert font.get_first_char() == -1
    assert font.get_last_char() == -1


def test_widths_skip_malformed_entries_and_average_only_positive_numbers() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_item(
        _name("Widths"),
        COSArray(
            [
                COSInteger.get(0),
                _name("bad-width"),
                COSInteger.get(250),
                COSDictionary(),
                COSFloat(500.5),
                COSInteger.get(-12),
            ]
        ),
    )

    assert font.get_widths() == [0.0, 250.0, 500.5, -12.0]
    assert font.get_average_font_width() == pytest.approx((250.0 + 500.5) / 2)


def test_has_explicit_width_uses_first_char_and_parsed_width_entries() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(_name("FirstChar"), 40)
    cos.set_int(_name("LastChar"), 99)
    cos.set_item(
        _name("Widths"),
        COSArray([COSInteger.get(100), _name("bad-width"), COSInteger.get(300)]),
    )

    assert font.has_explicit_width(39) is False
    assert font.has_explicit_width(40) is True
    assert font.has_explicit_width(41) is True
    assert font.has_explicit_width(42) is False


def test_encoding_raw_typed_and_dictionary_round_trip_from_cos() -> None:
    raw = COSDictionary()
    enc = COSDictionary()
    enc.set_name(_name("BaseEncoding"), "WinAnsiEncoding")
    enc.set_item(
        _name("Differences"),
        COSArray([COSInteger.get(65), _name("Z"), COSInteger.get(97), _name("a")]),
    )
    raw.set_item(_name("Encoding"), enc)

    font = PDType1Font(raw)
    assert font.get_encoding() is enc
    typed = font.get_encoding_typed()
    assert isinstance(typed, DictionaryEncoding)
    assert typed.get_base_encoding() is WinAnsiEncoding.INSTANCE
    assert typed.get_differences() == {65: "Z", 97: "a"}
    assert font.get_encoding_typed() is typed


def test_unknown_or_malformed_encoding_resolves_to_none_and_is_cached() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(_name("Encoding"), _name("BogusEncoding"))

    assert font.get_encoding_typed() is None
    font.get_cos_object().set_item(_name("Encoding"), _name("WinAnsiEncoding"))
    assert font.get_encoding_typed() is None

    fresh = PDType1Font()
    fresh.get_cos_object().set_item(_name("Encoding"), COSInteger.get(7))
    assert fresh.get_encoding() == COSInteger.get(7)
    assert fresh.get_encoding_typed() is None


def test_to_unicode_falls_back_to_encoding_when_to_unicode_shape_is_malformed() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_item(_name("Encoding"), _name("WinAnsiEncoding"))
    cos.set_item(_name("ToUnicode"), COSArray([COSInteger.get(65)]))

    assert font.has_to_unicode() is True
    assert font.get_to_unicode_cmap() is None
    assert font.to_unicode(0x41) == "A"


def test_font_descriptor_accessors_ignore_malformed_descriptor_shape() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(_name("FontDescriptor"), _name("NotADictionary"))

    assert font.get_font_descriptor() is None
    assert font.is_symbolic() is False
    assert font.is_italic() is False
    assert font.is_force_bold() is False
    assert font.is_bold() is False


def test_font_descriptor_can_be_read_through_resolved_cos_object() -> None:
    descriptor = COSDictionary()
    descriptor.set_int(_name("Flags"), FLAG_SYMBOLIC | FLAG_ITALIC | FLAG_FORCE_BOLD)
    descriptor.set_int(_name("FontWeight"), 700)
    raw = COSDictionary()
    raw.set_item(_name("FontDescriptor"), COSObject(12, resolved=descriptor))

    font = PDType1Font(raw)
    assert isinstance(font.get_font_descriptor(), PDFontDescriptor)
    assert font.is_symbolic() is True
    assert font.is_italic() is True
    assert font.is_force_bold() is True
    assert font.is_bold() is True


def test_full_cos_round_trip_keeps_simple_font_accessors_on_new_wrapper() -> None:
    font = PDTrueTypeFont()
    cos = font.get_cos_object()
    cos.set_name(_name("BaseFont"), "Wave279Font")
    cos.set_int(_name("FirstChar"), 65)
    cos.set_int(_name("LastChar"), 67)
    cos.set_item(
        _name("Widths"),
        COSArray([COSInteger.get(600), COSFloat(610.5), COSInteger.get(620)]),
    )
    cos.set_item(_name("Encoding"), _name("WinAnsiEncoding"))
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_ITALIC)
    fd.set_font_weight(400)
    font.set_font_descriptor(fd)

    parsed = PDTrueTypeFont(cos)
    assert parsed.get_first_char() == 65
    assert parsed.get_last_char() == 67
    assert parsed.get_widths() == [600.0, 610.5, 620.0]
    assert parsed.get_encoding_typed() is WinAnsiEncoding.INSTANCE
    assert parsed.to_unicode(65) == "A"
    assert parsed.is_italic() is True
    assert parsed.is_bold() is False


def test_not_implemented_subsetting_paths_have_actionable_message() -> None:
    font = PDType1Font()

    with pytest.raises(NotImplementedError, match="subsetting is not supported"):
        font.add_to_subset(ord("A"))
    with pytest.raises(NotImplementedError, match="subsetting is not supported"):
        font.subset()
