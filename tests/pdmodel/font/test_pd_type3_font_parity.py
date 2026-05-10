from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------- /FontMatrix ----------


def test_font_matrix_default_when_missing() -> None:
    font = PDType3Font()
    # PDF 32000-1 §9.2.4 default for Type 3 maps a 1000-unit em into text space.
    assert font.get_font_matrix() == [0.001, 0, 0, 0.001, 0, 0]


def test_font_matrix_default_when_array_wrong_size() -> None:
    font = PDType3Font()
    bogus = COSArray([COSFloat(1.0), COSFloat(0.0), COSFloat(0.0)])
    font.get_cos_object().set_item(COSName.get_pdf_name("FontMatrix"), bogus)
    assert font.get_font_matrix() == [0.001, 0, 0, 0.001, 0, 0]


def test_font_matrix_round_trip() -> None:
    font = PDType3Font()
    font.set_font_matrix([0.002, 0.0, 0.0, 0.002, 1.5, 2.5])
    # COSFloat stores values at float32 precision (PDF on-disk fidelity).
    assert font.get_font_matrix() == pytest.approx(
        [0.002, 0.0, 0.0, 0.002, 1.5, 2.5], rel=1e-6
    )


def test_font_matrix_round_trip_reads_from_dict() -> None:
    font = PDType3Font()
    font.set_font_matrix([0.001, 0.0, 0.0, 0.001, 0.0, 0.0])
    arr = font.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("FontMatrix")
    )
    assert isinstance(arr, COSArray)
    assert arr.size() == 6


def test_font_matrix_rejects_wrong_length() -> None:
    font = PDType3Font()
    with pytest.raises(ValueError):
        font.set_font_matrix([1.0, 0.0, 0.0, 1.0, 0.0])  # only 5


def test_font_matrix_accepts_integer_entries_in_dict() -> None:
    font = PDType3Font()
    arr = COSArray(
        [
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(0),
        ]
    )
    font.get_cos_object().set_item(COSName.get_pdf_name("FontMatrix"), arr)
    assert font.get_font_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------- /FontBBox ----------


def test_font_bbox_returns_none_when_missing() -> None:
    font = PDType3Font()
    assert font.get_font_bbox() is None


def test_font_bbox_round_trip() -> None:
    font = PDType3Font()
    rect = PDRectangle(0.0, 0.0, 750.0, 1000.0)
    font.set_font_bbox(rect)

    out = font.get_font_bbox()
    assert isinstance(out, PDRectangle)
    assert out == rect


def test_font_bbox_clear_with_none() -> None:
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 100.0, 200.0))
    assert font.get_font_bbox() is not None
    font.set_font_bbox(None)
    assert font.get_font_bbox() is None


# ---------- /Resources ----------


def test_resources_returns_none_when_missing() -> None:
    font = PDType3Font()
    assert font.get_resources() is None


def test_resources_round_trip() -> None:
    font = PDType3Font()
    resources = PDResources()
    font.set_resources(resources)

    out = font.get_resources()
    assert isinstance(out, PDResources)
    assert out.get_cos_object() is resources.get_cos_object()


def test_resources_clear_with_none() -> None:
    font = PDType3Font()
    font.set_resources(PDResources())
    assert font.get_resources() is not None
    font.set_resources(None)
    assert font.get_resources() is None


# ---------- /CharProcs ----------


def test_char_procs_returns_none_when_missing() -> None:
    font = PDType3Font()
    assert font.get_char_procs() is None
    assert font.get_char_proc("A") is None


def test_char_procs_round_trip() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    font.set_char_procs(char_procs)
    assert font.get_char_procs() is char_procs


def test_char_procs_clear_with_none() -> None:
    font = PDType3Font()
    font.set_char_procs(COSDictionary())
    assert font.get_char_procs() is not None
    font.set_char_procs(None)
    assert font.get_char_procs() is None


def test_get_char_proc_returns_glyph_stream() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    glyph_a = COSStream()
    glyph_b = COSStream()
    char_procs.set_item(COSName.get_pdf_name("A"), glyph_a)
    char_procs.set_item(COSName.get_pdf_name("B"), glyph_b)
    font.set_char_procs(char_procs)

    assert font.get_char_proc("A") is glyph_a
    assert font.get_char_proc("B") is glyph_b
    assert font.get_char_proc("C") is None


def test_get_char_proc_returns_none_when_entry_not_a_stream() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSDictionary())
    font.set_char_procs(char_procs)
    assert font.get_char_proc("A") is None


# ---------- /FirstChar /LastChar /Widths ----------


def test_first_char_default_when_missing() -> None:
    # PDSimpleFont.get_first_char defaults to -1 when absent.
    font = PDType3Font()
    assert font.get_first_char() == -1


def test_last_char_default_when_missing() -> None:
    font = PDType3Font()
    assert font.get_last_char() == -1


def test_first_char_round_trip() -> None:
    font = PDType3Font()
    font.set_first_char(33)
    assert font.get_first_char() == 33


def test_last_char_round_trip() -> None:
    font = PDType3Font()
    font.set_last_char(126)
    assert font.get_last_char() == 126


def test_first_and_last_char_round_trip_together() -> None:
    font = PDType3Font()
    font.set_first_char(0)
    font.set_last_char(255)
    assert font.get_first_char() == 0
    assert font.get_last_char() == 255


def test_widths_default_when_missing() -> None:
    font = PDType3Font()
    assert font.get_widths() == []


def test_widths_round_trip() -> None:
    font = PDType3Font()
    font.set_widths([500.0, 600.0, 250.5, 0.0, 1000.0])
    # COSFloat is float32 — exact for these integer-magnitude values.
    assert font.get_widths() == pytest.approx(
        [500.0, 600.0, 250.5, 0.0, 1000.0], rel=1e-6
    )


def test_widths_round_trip_after_first_last_char() -> None:
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(67)
    font.set_widths([500.0, 500.0, 500.0])
    assert font.get_first_char() == 65
    assert font.get_last_char() == 67
    assert font.get_widths() == pytest.approx([500.0, 500.0, 500.0], rel=1e-6)


# ---------- is_standard_14 (Type 3 override) ----------


def test_is_standard_14_always_false_even_with_standard_basefont() -> None:
    """Upstream ``PDType3Font.isStandard14()`` returns ``false`` flat-out;
    a Type 3 font that happens to carry a Standard 14 ``/BaseFont`` (e.g.
    ``Helvetica``) must still be classified as non-Standard 14."""
    font = PDType3Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_standard_14() is False


def test_is_standard_14_false_when_no_basefont() -> None:
    assert PDType3Font().is_standard_14() is False


# ---------- is_font_symbolic (Type 3 override) ----------


def test_is_font_symbolic_always_false() -> None:
    """Mirrors upstream protected ``isFontSymbolic() → false``: Type 3
    fonts are non-symbolic for encoding-resolution purposes."""
    assert PDType3Font().is_font_symbolic() is False


# ---------- has_glyph(str) (string overload) ----------


def test_has_glyph_str_true_when_charproc_registered() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSStream())
    font.set_char_procs(char_procs)
    assert font.has_glyph("A") is True


def test_has_glyph_str_false_when_no_charprocs() -> None:
    assert PDType3Font().has_glyph("A") is False


def test_has_glyph_str_false_when_name_not_in_charprocs() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSStream())
    font.set_char_procs(char_procs)
    assert font.has_glyph("B") is False


def test_has_glyph_str_false_when_entry_not_a_stream() -> None:
    """Mirrors upstream's stream-typed lookup: a non-stream entry under
    the requested name must register as ``False``."""
    font = PDType3Font()
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSDictionary())
    font.set_char_procs(char_procs)
    assert font.has_glyph("A") is False


def test_has_glyph_rejects_bool() -> None:
    """``bool`` is an ``int`` in Python — disallow to avoid ambiguous
    code-vs-name dispatch (mirrors :meth:`get_char_proc`)."""
    font = PDType3Font()
    with pytest.raises(TypeError):
        font.has_glyph(True)  # type: ignore[arg-type]
