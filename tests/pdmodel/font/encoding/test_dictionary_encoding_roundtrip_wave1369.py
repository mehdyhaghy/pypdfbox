"""DictionaryEncoding /Differences COS round-trip.

Wave 1369 round-out — exercises the writer-side flow where an encoding is
built up, dumped to its COSDictionary, then re-parsed back through the
reader path. Mirrors how a writer would round-trip an embedded encoding.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    WinAnsiEncoding,
)


def test_writer_then_reader_round_trip_via_cos_dict() -> None:
    # Writer-side build.
    writer = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding")
    )
    writer.set_differences({0x41: "Aacute", 0x42: "Acircumflex", 0x80: "myglyph"})

    # Round-trip through the COS dict (what gets written to the PDF).
    cos = writer.get_cos_object()
    assert isinstance(cos, COSDictionary)

    # Reader-side reconstruction.
    reader = DictionaryEncoding(font_encoding=cos, is_non_symbolic=True)
    assert reader.get_base_encoding() is WinAnsiEncoding.INSTANCE
    assert reader.get_name(0x41) == "Aacute"
    assert reader.get_name(0x42) == "Acircumflex"
    assert reader.get_name(0x80) == "myglyph"
    # Base-only codes still flow from WinAnsi (0x20 -> /space).
    assert reader.get_name(0x20) == "space"


def test_round_trip_preserves_differences_array_layout() -> None:
    # Differences with two non-contiguous runs should keep that exact shape
    # across the get_cos_object -> font_encoding boundary.
    diffs = COSArray()
    diffs.add(COSInteger.get(0x10))
    diffs.add(COSName.get_pdf_name("alpha"))
    diffs.add(COSName.get_pdf_name("beta"))
    diffs.add(COSInteger.get(0x40))
    diffs.add(COSName.get_pdf_name("gamma"))

    writer = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("StandardEncoding"),
        differences=diffs,
    )
    cos = writer.get_cos_object()
    arr = cos.get_dictionary_object(COSName.get_pdf_name("Differences"))
    # Same array instance: writer hangs it directly off the dict.
    assert arr is diffs

    reader = DictionaryEncoding(font_encoding=cos, is_non_symbolic=True)
    assert reader.get_name(0x10) == "alpha"
    assert reader.get_name(0x11) == "beta"
    assert reader.get_name(0x40) == "gamma"


def test_round_trip_with_type3_no_base_encoding() -> None:
    # Build a Type 3-style encoding (no /BaseEncoding) and round-trip it.
    cos = COSDictionary()
    cos.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    diffs.add(COSInteger.get(0x01))
    diffs.add(COSName.get_pdf_name("glyph_one"))
    diffs.add(COSName.get_pdf_name("glyph_two"))
    cos.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=cos)
    assert enc.is_type3() is True
    assert enc.has_base_encoding() is False
    assert enc.get_encoding_name() == "differences"
    assert enc.get_name(0x01) == "glyph_one"
    assert enc.get_name(0x02) == "glyph_two"
    # Re-read from the same dict — must produce an equivalent encoding.
    enc_again = DictionaryEncoding(font_encoding=enc.get_cos_object())
    assert enc_again.get_name(0x01) == "glyph_one"
    assert enc_again.get_name(0x02) == "glyph_two"


def test_get_cos_object_identity_stable_under_mutation() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    first = enc.get_cos_object()
    enc.set_differences({0x41: "Acircumflex"})
    second = enc.get_cos_object()
    # Mutations don't replace the underlying dict — same instance.
    assert second is first
