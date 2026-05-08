from __future__ import annotations

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
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_ALL_CAP,
    FLAG_FIXED_PITCH,
    FLAG_FORCE_BOLD,
    FLAG_ITALIC,
    PDFontDescriptor,
    PDPanose,
    PDPanoseClassification,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave279_flags_absent_default_vs_explicit_zero_and_clear() -> None:
    fd = PDFontDescriptor()
    flags = _name("Flags")

    assert fd.get_flags() == 0
    assert fd.is_fixed_pitch() is False
    assert flags not in fd

    fd.set_flags(0)
    raw = fd.get_cos_object().get_dictionary_object(flags)
    assert isinstance(raw, COSInteger)
    assert raw.int_value() == 0
    assert fd.get_flags() == 0
    assert flags in fd

    fd.set_flags(FLAG_FIXED_PITCH | FLAG_ITALIC | FLAG_FORCE_BOLD)
    fd.clear_flags()
    raw = fd.get_cos_object().get_dictionary_object(flags)
    assert isinstance(raw, COSInteger)
    assert raw.int_value() == 0
    assert fd.get_flags() == 0
    assert fd.is_fixed_pitch() is False
    assert fd.is_italic() is False
    assert fd.is_force_bold() is False


def test_wave279_mask_and_index_flag_helpers_do_not_cross_talk() -> None:
    fd = PDFontDescriptor()

    fd.set_flag_bit(FLAG_FORCE_BOLD, True)
    assert fd.is_flag_bit_on(FLAG_FORCE_BOLD) is True
    assert fd.get_flag(19) is True
    assert fd.get_flag(FLAG_FORCE_BOLD) is False

    fd.set_flag(17, True)
    assert fd.is_flag_bit_on(FLAG_ALL_CAP) is True
    assert fd.get_flags() == FLAG_FORCE_BOLD | FLAG_ALL_CAP

    fd.set_flag_bit(FLAG_FORCE_BOLD, False)
    assert fd.is_force_bold() is False
    assert fd.is_all_cap() is True
    assert fd.get_flags() == FLAG_ALL_CAP


def test_wave279_font_file_predicates_report_presence_even_when_malformed() -> None:
    fd = PDFontDescriptor()
    font_file2 = _name("FontFile2")
    fd.get_cos_object().set_item(font_file2, COSString("not a stream"))

    assert fd.has_font_file2() is True
    assert fd.is_embedded() is True
    assert fd.get_font_file2() is None

    fd.set_font_file2(None)
    assert fd.has_font_file2() is False
    assert fd.is_embedded() is False
    assert font_file2 not in fd


def test_wave279_font_file_clear_preserves_other_embedded_slots() -> None:
    fd = PDFontDescriptor()
    stream1 = COSStream()
    stream3 = COSStream()
    fd.set_font_file(PDStream(stream1))
    fd.set_font_file3(stream3)

    assert fd.has_font_file() is True
    assert fd.has_font_file3() is True
    assert fd.is_embedded() is True

    fd.set_font_file(None)
    assert fd.has_font_file() is False
    assert fd.has_font_file3() is True
    assert fd.get_font_file3().get_cos_object() is stream3
    assert fd.is_embedded() is True

    fd.set_font_file3(None)
    assert fd.is_embedded() is False


def test_wave279_bbox_presence_is_separate_from_typed_shape() -> None:
    fd = PDFontDescriptor()
    bbox = _name("FontBBox")

    assert fd.has_font_bounding_box() is False
    assert fd.get_font_b_box() is None
    assert fd.get_font_bounding_box() is None

    fd.get_cos_object().set_item(bbox, COSString("bad bbox"))
    assert fd.has_font_bounding_box() is True
    assert fd.get_font_b_box() is None
    assert fd.get_font_bounding_box() is None

    fd.set_font_b_box(COSArray([COSFloat(0.0), COSFloat(1.0), COSFloat(2.0)]))
    assert fd.has_font_bounding_box() is True
    assert fd.get_font_bounding_box() is None

    fd.set_font_bounding_box(PDRectangle(0.0, 1.0, 2.0, 3.0))
    rect = fd.get_font_bounding_box()
    assert isinstance(rect, PDRectangle)
    assert rect.upper_right_y == pytest.approx(3.0)

    fd.set_font_b_box(None)
    assert fd.has_font_bounding_box() is False


def test_wave279_missing_width_explicit_zero_keeps_presence_predicates() -> None:
    fd = PDFontDescriptor()
    missing_width = _name("MissingWidth")

    assert fd.get_missing_width() == 0.0
    assert fd.has_missing_width() is False
    assert fd.has_widths() is False

    fd.set_missing_width(0.0)
    raw = fd.get_cos_object().get_dictionary_object(missing_width)
    assert isinstance(raw, COSFloat)
    assert raw.float_value() == pytest.approx(0.0)
    assert fd.get_missing_width() == 0.0
    assert fd.has_missing_width() is True
    assert fd.has_widths() is True

    fd.get_cos_object().remove_item(missing_width)
    assert fd.get_missing_width() == 0.0
    assert fd.has_missing_width() is False
    assert fd.has_widths() is False


def test_wave279_widths_presence_tolerates_malformed_widths_entry() -> None:
    fd = PDFontDescriptor()
    widths = _name("Widths")
    fd.get_cos_object().set_item(widths, COSString("bad widths"))

    assert fd.has_widths() is True
    assert fd.has_missing_width() is False

    fd.get_cos_object().remove_item(widths)
    assert fd.has_widths() is False


def test_wave279_stem_metrics_explicit_zero_round_trip_through_cos() -> None:
    fd = PDFontDescriptor()
    stem_v = _name("StemV")
    stem_h = _name("StemH")

    assert fd.get_stem_v() == 0.0
    assert fd.get_stem_h() == 0.0
    assert stem_v not in fd
    assert stem_h not in fd

    fd.set_stem_v(0.0)
    fd.set_stem_h(12.5)

    raw_v = fd.get_cos_object().get_dictionary_object(stem_v)
    raw_h = fd.get_cos_object().get_dictionary_object(stem_h)
    assert isinstance(raw_v, COSFloat)
    assert isinstance(raw_h, COSFloat)
    assert raw_v.float_value() == pytest.approx(0.0)
    assert raw_h.float_value() == pytest.approx(12.5)
    assert fd.get_stem_v() == pytest.approx(0.0)
    assert fd.get_stem_h() == pytest.approx(12.5)


def test_wave279_panose_presence_is_separate_from_typed_value() -> None:
    fd = PDFontDescriptor()
    style_key = _name("Style")
    panose_key = _name("Panose")
    style = COSDictionary()
    style.set_item(panose_key, COSArray())
    fd.get_cos_object().set_item(style_key, style)

    assert fd.has_panose() is True
    assert fd.get_panose() is None

    payload = bytes([0x00, 0x08, 2, 11, 6, 3, 5, 4, 5, 2, 2, 4])
    fd.set_panose(payload)
    panose = fd.get_panose()
    assert isinstance(panose, PDPanose)
    assert panose.get_bytes() == payload


def test_wave279_panose_clear_removes_empty_style_but_preserves_siblings() -> None:
    fd = PDFontDescriptor()
    style_key = _name("Style")
    custom_key = _name("Custom")

    fd.set_panose(bytes(PDPanose.LENGTH))
    fd.set_panose(None)
    assert fd.has_panose() is False
    assert fd.get_cos_object().get_dictionary_object(style_key) is None

    fd.set_panose(bytes(PDPanose.LENGTH))
    style = fd.get_cos_object().get_dictionary_object(style_key)
    assert isinstance(style, COSDictionary)
    style.set_name(custom_key, "Value")

    fd.set_panose(None)
    style = fd.get_cos_object().get_dictionary_object(style_key)
    assert isinstance(style, COSDictionary)
    assert style.get_name(custom_key) == "Value"
    assert fd.has_panose() is False


def test_wave279_panose_factory_rejects_out_of_range_family_class() -> None:
    classification = PDPanoseClassification(bytes(PDPanoseClassification.LENGTH))

    with pytest.raises(ValueError, match="signed 16-bit"):
        PDPanose.from_family_class_and_classification(0x8000, classification)

    with pytest.raises(ValueError, match="signed 16-bit"):
        PDPanose.from_family_class_and_classification(-0x8001, classification)

