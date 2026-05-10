"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.OTFParser`.

The repo does not ship an OTF fixture (we only have
LiberationSans-Regular.ttf), so the tests synthesise an OTTO-magic
stream at runtime using fontTools — same library the parser delegates
to internally — to keep the suite self-contained.
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

FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _synthesize_minimal_otf() -> bytes:
    """Build a minimal valid OTF (CFF-flavoured) byte stream in-memory.

    Uses fontTools' CFF builder to produce a real, parseable OTTO so
    the OTFParser can exercise the full directory-walk + table-decode
    path. Falls back to ``pytest.skip`` if the helper APIs aren't
    available in the installed fontTools version.
    """
    try:
        from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
    except ImportError:
        pytest.skip("fontTools FontBuilder not available")

    fb = FontBuilder(unitsPerEm=1000, isTTF=False)
    glyph_order = [".notdef", "A", "space"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A", 0x20: "space"})

    # Empty CFF charstrings (no outlines) — sufficient for parser tests.
    charstrings = {name: T2_EMPTY for name in glyph_order}
    fb.setupCFF(
        psName="TestOTF",
        fontInfo={"FullName": "Test OTF"},
        charStringsDict=charstrings,
        privateDict={},
    )
    fb.setupHorizontalMetrics({name: (500, 0) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()

    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


# Minimal CFF Type 2 charstring: just `endchar`. Stored as bytes the
# fontTools CFF builder accepts via T2CharString program API. We pass a
# raw T2CharString instance for safety.
def _make_t2_empty():
    from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415

    cs = T2CharString()
    cs.program = ["endchar"]
    return cs


T2_EMPTY = _make_t2_empty()


@pytest.fixture(scope="module")
def otf_bytes() -> bytes:
    return _synthesize_minimal_otf()


# ---------- subclass relationship -----------------------------------------


def test_otf_parser_extends_ttf_parser() -> None:
    assert issubclass(OTFParser, TTFParser)


def test_otf_parser_default_flags() -> None:
    parser = OTFParser()
    assert parser.is_embedded is False
    assert parser.parse_on_demand is True


# ---------- parse(...) produces OpenTypeFont -----------------------------


def test_parse_otto_returns_open_type_font(otf_bytes: bytes) -> None:
    parser = OTFParser()
    font = parser.parse(otf_bytes)
    assert isinstance(font, OpenTypeFont)
    # OpenTypeFont also ISA TrueTypeFont (preserves PDFBox hierarchy).
    assert isinstance(font, TrueTypeFont)


def test_parse_from_bytesio(otf_bytes: bytes) -> None:
    parser = OTFParser()
    font = parser.parse(io.BytesIO(otf_bytes))
    assert isinstance(font, OpenTypeFont)
    assert font.is_post_script() is True


def test_parse_lenient_accepts_truetype_magic() -> None:
    """OTFParser is lenient about scaler type — a TTF-magic stream is
    also accepted (mirrors upstream tolerance).

    Per upstream ``OpenTypeFont.isSupportedOTF()`` only the
    ``OTTO``+``CFF2``-without-``CFF `` triple is rejected; TrueType
    outlines in an OTF wrapper are reported as supported. ``getCFF()``
    still returns ``None`` because no CFF table is present.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    parser = OTFParser()
    font = parser.parse(FIXTURE_TTF.read_bytes())
    assert isinstance(font, OpenTypeFont)
    assert font.is_supported_otf() is True
    assert font.get_cff() is None


# ---------- magic-rejection for clearly-wrong streams --------------------


def test_parse_rejects_unknown_scaler() -> None:
    parser = OTFParser()
    with pytest.raises(OSError, match="scaler"):
        parser.parse(b"XXXX" + b"\x00" * 200)
