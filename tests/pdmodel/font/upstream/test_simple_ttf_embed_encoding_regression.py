"""Regression test for the wave-1364 ``Encoding.get_cos_object`` fix.

Source: derived from the upstream
``PDTrueTypeFont.load(PDDocument, InputStream, Encoding)`` test path
exercised by ``PDFontTest.testPDFBOX5486`` and
``PDFontTest.PDFBOX5920TrueType`` — both call
``PDTrueTypeFont.load(doc, stream, WinAnsiEncoding.INSTANCE)`` and
rely on the resulting font dictionary advertising
``/Encoding /WinAnsiEncoding``.

Prior to wave 1364, ``_build_simple_ttf_font`` called
``encoding.get_cos_object()`` unconditionally; the predefined
encodings (``WinAnsiEncoding`` / ``MacRomanEncoding`` / ...) did not
override the missing base method, so the call site crashed with
``AttributeError: 'WinAnsiEncoding' object has no attribute
'get_cos_object'``.

This test pins down the end-to-end embedding path so the regression
cannot re-surface.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos.cos_name import COSName
from pypdfbox.fontbox.encoding.mac_roman_encoding import MacRomanEncoding
from pypdfbox.fontbox.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.pd_document import PDDocument

_LIBERATION_SANS = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def test_simple_ttf_load_with_win_ansi_writes_encoding_name() -> None:
    """``PDTrueTypeFont.load(doc, stream, WinAnsiEncoding.INSTANCE)``
    must serialize ``/Encoding /WinAnsiEncoding`` on the font dict.

    Before wave 1364 this crashed at ``_build_simple_ttf_font`` because
    ``WinAnsiEncoding`` lacked ``get_cos_object``.
    """
    assert _LIBERATION_SANS.exists(), f"missing bundled TTF: {_LIBERATION_SANS}"
    with PDDocument() as doc, _LIBERATION_SANS.open("rb") as fh:
        font = PDTrueTypeFont.load(doc, fh, WinAnsiEncoding.INSTANCE)
        enc = font.get_cos_object().get_item(COSName.get_pdf_name("Encoding"))
        assert enc == COSName.WIN_ANSI_ENCODING


def test_simple_ttf_load_with_mac_roman_writes_encoding_name() -> None:
    """``PDTrueTypeFont.load(doc, stream, MacRomanEncoding.INSTANCE)``
    must serialize ``/Encoding /MacRomanEncoding`` on the font dict.

    Same fix as ``test_simple_ttf_load_with_win_ansi_writes_encoding_name``
    — the missing ``get_cos_object`` override was on the entire
    predefined-encoding family.
    """
    assert _LIBERATION_SANS.exists(), f"missing bundled TTF: {_LIBERATION_SANS}"
    with PDDocument() as doc, _LIBERATION_SANS.open("rb") as fh:
        font = PDTrueTypeFont.load(doc, fh, MacRomanEncoding.INSTANCE)
        enc = font.get_cos_object().get_item(COSName.get_pdf_name("Encoding"))
        assert enc == COSName.MAC_ROMAN_ENCODING
