"""PDFBOX-6287: ``Encoding.get_code`` and the shared ``codepointEncoding``
cache on :class:`PDFont` (moved up from ``PDType1Font``)."""

from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSArray, COSInteger
from pypdfbox.pdmodel.font import PDTrueTypeFont, PDType0Font
from pypdfbox.pdmodel.font.encoding.mac_os_roman_encoding import MacOSRomanEncoding
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding

_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _ttf_bytes() -> bytes:
    if not _TTF.exists():
        pytest.skip(f"missing fixture {_TTF}")
    return _TTF.read_bytes()


def test_get_code_matches_name_to_code_map() -> None:
    for encoding in (WinAnsiEncoding.INSTANCE, MacOSRomanEncoding.INSTANCE):
        inverted = encoding.get_name_to_code_map()
        for name, code in inverted.items():
            assert encoding.get_code(name) == code
        assert encoding.get_code("no-such-glyph") is None


def test_true_type_encode_populates_shared_cache() -> None:
    with PDDocument() as doc:
        font = PDTrueTypeFont.load(doc, _ttf_bytes(), WinAnsiEncoding.INSTANCE)
        assert font._codepoint_encoding == {}
        first = font.encode_codepoint(ord("A"))
        assert first == b"A"
        assert font._codepoint_encoding[ord("A")] is first
        assert font.encode_codepoint(ord("A")) is first


def test_true_type_failed_encode_is_not_cached() -> None:
    with PDDocument() as doc:
        font = PDTrueTypeFont.load(doc, _ttf_bytes(), WinAnsiEncoding.INSTANCE)
        with pytest.raises(ValueError):
            font.encode_codepoint(0x4E00)
        assert 0x4E00 not in font._codepoint_encoding


def test_type0_encode_populates_shared_cache() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        uncached = font.encode("AB")
        assert ord("A") in font._codepoint_encoding
        assert ord("B") in font._codepoint_encoding
        assert font.encode("AB") == uncached
        assert font.encode(ord("A")) == uncached[:2]


def test_cid_font_width_cache_invalidated_by_set_w() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        cid_font = font.get_descendant_font()
        code = int.from_bytes(font.encode("A"), "big")
        width = cid_font.get_width(code)
        assert cid_font._cid_code_to_width[code] == width
        cid = cid_font.code_to_cid(code)
        w = COSArray()
        w.add(COSInteger.get(cid))
        inner = COSArray()
        inner.add(COSInteger.get(123))
        w.add(inner)
        cid_font.set_w(w)
        assert cid_font._cid_code_to_width == {}
        assert cid_font.get_width(code) == 123.0
        cid_font.set_dw(777)
        assert cid_font._cid_code_to_width == {}
