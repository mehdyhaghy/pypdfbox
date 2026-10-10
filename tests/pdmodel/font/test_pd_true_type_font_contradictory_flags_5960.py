"""Hand-written pins for the PDFBOX-5960 forward-port (3.0 branch, unreleased
3.0.9): a symbolic TrueType font whose descriptor also sets the NonSymbolic
flag, and whose /Encoding dictionary has a recognized /BaseEncoding, resolves
codes by glyph name first. Upstream test: ``tests/pdmodel/font/upstream/
test_pd_font.py::test_pdfbox5960``."""

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font import PDTrueTypeFont
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    MacRomanEncoding,
    StandardEncoding,
    WinAnsiEncoding,
)
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


def _font_with_flags(flags: int) -> PDTrueTypeFont:
    font = PDTrueTypeFont(COSDictionary())
    fd = PDFontDescriptor()
    fd.set_flags(flags)
    font.get_cos_object().set_item(
        COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object()
    )
    return font


def test_contradictory_flags_detected_only_when_both_set() -> None:
    symbolic, non_symbolic = 4, 32
    assert _font_with_flags(symbolic | non_symbolic)._has_contradictory_symbolic_flags()
    assert not _font_with_flags(symbolic)._has_contradictory_symbolic_flags()
    assert not _font_with_flags(non_symbolic)._has_contradictory_symbolic_flags()
    assert not PDTrueTypeFont(COSDictionary())._has_contradictory_symbolic_flags()


def test_recognized_base_encodings() -> None:
    recognized = PDTrueTypeFont._is_recognized_base_encoding
    assert recognized(StandardEncoding.INSTANCE)
    assert recognized(WinAnsiEncoding.INSTANCE)
    assert recognized(MacRomanEncoding.INSTANCE)
    assert not recognized(BuiltInEncoding({65: "A"}))
    assert not recognized(None)
