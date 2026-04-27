from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font import PDFont, PDFontDescriptor


# PDFont is conceptually abstract — concrete subclasses set ``SUB_TYPE`` and
# add behaviour. For base-class parity we drive the methods through a thin
# concrete stand-in so we exercise *only* the inherited PDFont surface and
# never accidentally hit a subclass override.
class _BarePDFont(PDFont):
    """Bare concrete PDFont subclass for base-method parity tests."""

    SUB_TYPE = None


# ---------- defaults on a fresh empty font ----------


def test_bare_font_is_embedded_false_when_no_descriptor() -> None:
    font = _BarePDFont()
    assert font.is_embedded() is False


def test_bare_font_is_embedded_false_when_descriptor_has_no_font_file() -> None:
    font = _BarePDFont()
    fd = PDFontDescriptor()
    font.set_font_descriptor(fd)
    assert font.is_embedded() is False


def test_bare_font_is_damaged_default_false() -> None:
    assert _BarePDFont().is_damaged() is False


def test_bare_font_get_widths_default_empty() -> None:
    assert _BarePDFont().get_widths() == []


def test_bare_font_get_first_char_default_minus_one() -> None:
    assert _BarePDFont().get_first_char() == -1


def test_bare_font_get_last_char_default_minus_one() -> None:
    assert _BarePDFont().get_last_char() == -1


def test_bare_font_get_average_font_width_default_zero() -> None:
    assert _BarePDFont().get_average_font_width() == 0.0


def test_bare_font_get_space_width_defaults_to_250() -> None:
    assert _BarePDFont().get_space_width() == 250.0


def test_bare_font_is_subset_false_when_no_base_font() -> None:
    assert _BarePDFont().is_subset() is False


# ---------- /BaseFont subset prefix detection ----------


def test_is_subset_true_for_six_letter_prefix() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ABCDEF+Helvetica")
    assert font.is_subset() is True


def test_is_subset_false_for_plain_base_font() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_subset() is False


def test_is_subset_false_for_non_uppercase_prefix() -> None:
    # Mixed-case prefix is not a valid PDF subset marker.
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "AbCdEf+Helvetica")
    assert font.is_subset() is False


def test_is_subset_false_for_short_prefix() -> None:
    # Five-letter prefix does not match the six-letter rule.
    font = _BarePDFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ABCDE+Helvetica")
    assert font.is_subset() is False


# ---------- is_embedded across each /FontFile* slot ----------


def _font_with_font_file_key(key_name: str) -> _BarePDFont:
    font = _BarePDFont()
    fd = PDFontDescriptor()
    fd.get_cos_object().set_item(COSName.get_pdf_name(key_name), COSStream())
    font.set_font_descriptor(fd)
    return font


def test_is_embedded_true_when_font_file_present() -> None:
    assert _font_with_font_file_key("FontFile").is_embedded() is True


def test_is_embedded_true_when_font_file2_present() -> None:
    assert _font_with_font_file_key("FontFile2").is_embedded() is True


def test_is_embedded_true_when_font_file3_present() -> None:
    assert _font_with_font_file_key("FontFile3").is_embedded() is True


# ---------- /Widths-driven accessors ----------


def test_get_widths_reads_int_and_float_entries() -> None:
    font = _BarePDFont()
    arr = COSArray([COSInteger.get(250), COSInteger.get(333), COSFloat(408.5)])
    font.get_cos_object().set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_widths() == [250.0, 333.0, 408.5]


def test_get_first_and_last_char_round_trip() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 126)
    assert font.get_first_char() == 32
    assert font.get_last_char() == 126


def test_get_average_font_width_returns_mean_of_positive_widths() -> None:
    font = _BarePDFont()
    # Mean of positive entries (zero entries — typically .notdef — are skipped)
    arr = COSArray(
        [
            COSInteger.get(250),
            COSInteger.get(500),
            COSInteger.get(0),  # skipped
            COSInteger.get(750),
        ]
    )
    font.get_cos_object().set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_average_font_width() == 500.0


def test_get_space_width_uses_widths_offset_by_first_char() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 30)
    # Index 32 - 30 = 2 → expect 600.0
    arr = COSArray(
        [COSInteger.get(100), COSInteger.get(200), COSInteger.get(600), COSInteger.get(800)]
    )
    cos.set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_space_width() == 600.0


def test_get_space_width_falls_back_to_250_when_index_out_of_range() -> None:
    # /FirstChar = 100 puts code 32 below the start of /Widths → fallback.
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 100)
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(500)]))
    assert font.get_space_width() == 250.0


# ---------- wrapping a pre-built dict preserves base behaviour ----------


def test_wrapping_existing_dict_with_subset_base_font() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("BaseFont"), "ZZZZZZ+Times-Roman")
    font = _BarePDFont(raw)
    assert font.is_subset() is True
    assert font.get_name() == "ZZZZZZ+Times-Roman"
