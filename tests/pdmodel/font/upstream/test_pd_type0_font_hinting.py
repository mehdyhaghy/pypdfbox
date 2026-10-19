"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDType0FontHintingTest.java``.

The CID half of the render-path hinting wiring:
:meth:`PDCIDFontType2.get_hinted_normalized_path` and the
:class:`PDType0Font` forwarder.
"""

from pathlib import Path
from typing import Any

import pytest

# The GlyphHinter port (wave 1611) is required to produce hinted paths.
pytest.importorskip("pypdfbox.fontbox.ttf.glyph_hinter")

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.fontbox.ttf import TTFParser
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font import PDType0Font

_TTF = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _load(doc: PDDocument) -> tuple[PDType0Font, int]:
    """Embed the font whole (no subsetting) so the encoding is Identity and
    a character code is its own glyph id."""
    ttf = TTFParser().parse(_TTF)
    gid = ttf.get_unicode_cmap_lookup().get_glyph_id(ord("H"))
    assert gid > 0, "no glyph for 'H'"
    return PDType0Font.load(doc, _TTF, embed_subset=False), gid


def _points(path: list[Any]) -> list[tuple[float, float]]:
    """Every coordinate pair of a ``("moveto", x, y)``-style command list."""
    out: list[tuple[float, float]] = []
    for cmd in path:
        coords = cmd[1:]
        out.extend((coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2))
    return out


def test_hinted_normalized_path_differs_from_unhinted() -> None:
    with PDDocument() as doc:
        font, gid = _load(doc)

        hinted = font.get_hinted_normalized_path(gid, 16)
        assert hinted is not None, "expected a hinted path for 'H' at 16ppem"
        unhinted = font.get_normalized_path(gid)

        assert hinted != unhinted, "hinted path should differ from the unhinted path"

        max_y = max(y for _x, y in _points(hinted))
        assert 300 < max_y < 1000, (
            f"hinted path should be normalized to 1000/em, was maxY={max_y}"
        )


def test_gasp_gate_returns_null_at_small_ppem() -> None:
    with PDDocument() as doc:
        font, gid = _load(doc)
        # LiberationSans gasp disables grid-fitting at <= 8 ppem
        assert font.get_hinted_normalized_path(gid, 8) is None
        assert font.get_hinted_normalized_path(gid, 16) is not None


def _non_embedded() -> PDType0Font:
    """The Type0/CIDFontType2 dictionary pair of a non-embedded font."""
    cid = COSDictionary()
    cid.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    cid.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("CIDFontType2"))
    cid.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")

    descendants = COSArray()
    descendants.add(cid)

    type0 = COSDictionary()
    type0.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    type0.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type0"))
    type0.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    type0.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H"))
    type0.set_item(COSName.get_pdf_name("DescendantFonts"), descendants)
    return PDType0Font(type0)


def test_non_embedded_font_does_not_hint() -> None:
    """Only an embedded outline carries bytecode we can execute."""
    font = _non_embedded()
    assert not font.get_descendant_font().is_embedded(), "font should not be embedded"
    gid = font.get_descendant_font().code_to_gid(ord("H"))
    assert font.get_normalized_path(gid), "expected the substitute font to produce an outline"
    assert font.get_hinted_normalized_path(gid, 16) is None
