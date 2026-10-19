"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDTrueTypeFontHintingTest.java``.

Verifies the render-path hinting wiring at the font level: an embedded
TrueType font returns a grid-fitted normalized path that differs from the
unhinted one, is in the same 1000/em space, and respects the gasp gate.
"""

from pathlib import Path
from typing import Any

import pytest

# The GlyphHinter port (wave 1611) is required to produce hinted paths.
pytest.importorskip("pypdfbox.fontbox.ttf.glyph_hinter")

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font import PDTrueTypeFont
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding

_TTF = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _font_stream() -> bytes:
    return _TTF.read_bytes()


def _points(path: list[Any]) -> list[tuple[float, float]]:
    """Every coordinate pair of a fontTools ``(verb, args)`` path."""
    return [tuple(pt) for _verb, args in path for pt in args if pt is not None]


def test_hinted_normalized_path_differs_from_unhinted() -> None:
    with PDDocument() as doc:
        font = PDTrueTypeFont.load(doc, _font_stream(), WinAnsiEncoding.INSTANCE)
        code = ord("H")

        hinted = font.get_hinted_normalized_path(code, 16)
        assert hinted is not None, "expected a hinted path for 'H' at 16ppem"
        unhinted = font.get_normalized_path(code)

        # hinting must change the outline
        assert hinted != unhinted, "hinted path should differ from the unhinted path"

        # and it must still be in the 1000-unit em square
        max_y = max(y for _x, y in _points(hinted))
        assert 300 < max_y < 1000, (
            f"hinted path should be normalized to 1000/em, was maxY={max_y}"
        )


def test_gasp_gate_returns_null_at_small_ppem() -> None:
    with PDDocument() as doc:
        font = PDTrueTypeFont.load(doc, _font_stream(), WinAnsiEncoding.INSTANCE)
        # LiberationSans gasp disables grid-fitting at <= 8 ppem
        assert font.get_hinted_normalized_path(ord("H"), 8) is None
        assert font.get_hinted_normalized_path(ord("H"), 16) is not None


def test_non_embedded_font_does_not_hint() -> None:
    """Only an embedded outline carries bytecode we can execute."""
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("TrueType"))
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")

    font = PDTrueTypeFont(d)
    assert not font.is_embedded(), "font should not be embedded"
    # the substituted font still draws, so a None hinted path is the
    # embedded check talking
    assert font.get_normalized_path(ord("H")), (
        "expected the substitute font to produce an outline"
    )
    assert font.get_hinted_normalized_path(ord("H"), 16) is None
