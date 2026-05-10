"""Tests for ``OTFParser`` mirroring the surface upstream PDFBox 3.0
exercises across its fontbox tests (``GlyfCompositeDescriptTest``,
``TestCMapSubtable``, ``GsubWorkerFor{Latin,Aalt}Test``,
``GlyphSubstitutionTableLiberationFontTest``). Upstream does not ship
a standalone ``OTFParserTest.java``; these tests target the public
API surface those tests exercise on ``OTFParser`` itself
(constructors, ``parse``, ``newFont``, ``readTable``, ``allowCFF``).

Translated to pytest per the conventions in ``CLAUDE.md``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import (
    OpenTypeFont,
    OTFParser,
    TrueTypeFont,
    TTFParser,
)
from pypdfbox.fontbox.ttf.ttf_table import TTFTable

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _synthesize_minimal_otf() -> bytes:
    """Build a minimal valid OTF (CFF-flavoured) byte stream.

    Mirrors how upstream ``GsubWorkerFor*Test`` open an OTF file —
    we build one in-memory because the repo does not ship an OTF
    fixture, and skip when fontTools' builder API is unavailable.
    """
    try:
        from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
        from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415
    except ImportError:
        pytest.skip("fontTools FontBuilder / T2CharString unavailable")

    cs = T2CharString()
    cs.program = ["endchar"]

    fb = FontBuilder(unitsPerEm=1000, isTTF=False)
    glyph_order = [".notdef", "A"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A"})
    fb.setupCFF(
        psName="ParityOTF",
        fontInfo={"FullName": "Parity OTF"},
        charStringsDict=dict.fromkeys(glyph_order, cs),
        privateDict={},
    )
    fb.setupHorizontalMetrics(dict.fromkeys(glyph_order, (500, 0)))
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Parity", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()

    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def otf_bytes() -> bytes:
    return _synthesize_minimal_otf()


# ---- constructors --------------------------------------------------------
# Mirrors upstream ``new OTFParser()`` and ``new OTFParser(false)``.


def test_default_constructor_flags() -> None:
    """Mirrors ``new OTFParser()`` — embedded flag defaults to false."""
    parser = OTFParser()
    assert parser.is_embedded is False
    assert parser.parse_on_demand is True


def test_constructor_takes_is_embedded() -> None:
    """Mirrors ``new OTFParser(false)`` / ``new OTFParser(true)``."""
    assert OTFParser(is_embedded=False).is_embedded is False
    assert OTFParser(is_embedded=True).is_embedded is True


def test_extends_ttf_parser() -> None:
    """Hierarchy preservation per CLAUDE.md (PDFBox §3 — preserve
    inheritance hierarchies)."""
    assert issubclass(OTFParser, TTFParser)


# ---- allow_cff() ---------------------------------------------------------


def test_allow_cff_returns_true() -> None:
    """Mirrors ``boolean allowCFF()`` (OTFParser.java L85-L88).

    OTFParser must override TTFParser to accept CFF outlines.
    """
    assert OTFParser().allow_cff() is True


def test_ttf_parser_disallows_cff_otf_parser_allows() -> None:
    """Sanity-check the override actually overrides — TTFParser
    rejects CFF, OTFParser accepts it."""
    assert TTFParser()._allow_cff() is False
    assert OTFParser().allow_cff() is True


# ---- new_font() factory --------------------------------------------------


def test_new_font_returns_open_type_font(otf_bytes: bytes) -> None:
    """Mirrors ``OpenTypeFont newFont(TTFDataStream)``
    (OTFParser.java L60-L63). Factory returns an ``OpenTypeFont``,
    never a plain ``TrueTypeFont``."""
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream  # noqa: PLC0415

    parser = OTFParser()
    font = parser.new_font(MemoryTTFDataStream(otf_bytes))
    assert isinstance(font, OpenTypeFont)
    assert isinstance(font, TrueTypeFont)


# ---- read_table() switch -------------------------------------------------


def test_read_table_dispatches_otl_tags() -> None:
    """Mirrors ``readTable("BASE"/"GDEF"/"GPOS"/"GSUB"/"JSTF")``
    branch in OTFParser.java L66-L82 (returns ``OTLTable``).
    The tag must round-trip through the produced table."""
    parser = OTFParser()
    for tag in ("BASE", "GDEF", "GPOS", "GSUB", "JSTF"):
        table = parser.read_table(tag)
        assert isinstance(table, TTFTable)
        assert table.get_tag() == tag


def test_read_table_dispatches_cff_tag() -> None:
    """Mirrors ``case CFFTable.TAG`` branch (OTFParser.java L77-L78)."""
    table = OTFParser().read_table("CFF ")
    assert isinstance(table, TTFTable)
    assert table.get_tag() == "CFF "


def test_read_table_falls_through_to_super_for_unknown() -> None:
    """Mirrors ``default: return super.readTable(tag);``
    (OTFParser.java L79-L80)."""
    table = OTFParser().read_table("ZZZZ")
    assert isinstance(table, TTFTable)


# ---- parse() returns OpenTypeFont ----------------------------------------


def test_parse_otto_returns_open_type_font(otf_bytes: bytes) -> None:
    """Mirrors ``OpenTypeFont parse(RandomAccessRead)`` — the override
    narrows the return type from TTFParser's ``TrueTypeFont``."""
    font = OTFParser().parse(otf_bytes)
    assert isinstance(font, OpenTypeFont)
    assert isinstance(font, TrueTypeFont)


def test_parse_random_access_read(otf_bytes: bytes) -> None:
    """Mirrors how upstream tests call ``parse(new
    RandomAccessReadBuffer(stream))``."""
    from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer  # noqa: PLC0415

    font = OTFParser().parse(RandomAccessReadBuffer(otf_bytes))
    assert isinstance(font, OpenTypeFont)


def test_parse_lenient_accepts_truetype_magic() -> None:
    """OTFParser is lenient about scaler type — TTF magic is also
    accepted (mirrors upstream tolerance — see GlyfCompositeDescriptTest
    which feeds a Glyf-bearing font through OTFParser)."""
    if not _FIXTURE_TTF.exists():
        pytest.skip(f"TTF fixture not present: {_FIXTURE_TTF}")
    font = OTFParser().parse(_FIXTURE_TTF.read_bytes())
    assert isinstance(font, OpenTypeFont)
    assert font.is_supported_otf() is False
    assert font.get_cff() is None


def test_parse_rejects_unknown_scaler() -> None:
    """OTF magic check rejects a stream whose scaler is neither
    ``OTTO`` nor ``0x00010000``."""
    with pytest.raises(OSError, match="scaler"):
        OTFParser().parse(b"XXXX" + b"\x00" * 200)
