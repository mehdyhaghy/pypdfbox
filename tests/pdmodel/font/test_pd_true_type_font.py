"""Wave 1274 — final-gap tests for :class:`PDTrueTypeFont`.

Exercises the four upstream-Java methods we missed in earlier waves:

* :meth:`PDTrueTypeFont.generate_bounding_box` — the BBox builder upstream
  marks ``private`` (PDTrueTypeFont.java line 358); public on our side so
  parity tooling sees the match.
* :meth:`PDTrueTypeFont.get_parser` — static SFNT-flavour sniffer that
  returns ``TTFParser`` or ``OTFParser`` (PDTrueTypeFont.java line 781).
* :meth:`PDTrueTypeFont.get_path_from_outlines` — CFF-charstring glyph
  path resolver for OTF-CFF inputs (PDTrueTypeFont.java line 590).
* :meth:`PDTrueTypeFont.load` — static factory mirroring upstream's four
  load overloads (PDTrueTypeFont.java lines 206/226/246/266).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.encoding import (
    StandardEncoding,
    WinAnsiEncoding,
)

_TTF_FIXTURE = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not _TTF_FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_TTF_FIXTURE}")
    return _TTF_FIXTURE.read_bytes()


def _embedded_font(liberation_bytes: bytes) -> PDTrueTypeFont:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_raw_data(liberation_bytes)
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(TrueTypeFont.from_bytes(liberation_bytes))
    return font


# ---------- generate_bounding_box ---------------------------------------


def test_generate_bounding_box_uses_descriptor_when_available(
    liberation_bytes: bytes,
) -> None:
    """Descriptor /FontBBox wins over the embedded TTF's head table —
    matches upstream's ordering in ``generateBoundingBox()`` (line 358)."""
    from pypdfbox.cos import COSArray, COSFloat

    font = _embedded_font(liberation_bytes)
    bbox = COSArray()
    for v in (-100.0, -200.0, 1100.0, 900.0):
        bbox.add(COSFloat(v))
    font.get_font_descriptor().set_font_b_box(bbox)

    result = font.generate_bounding_box()
    assert result is not None
    assert result.get_lower_left_x() == -100.0
    assert result.get_upper_right_y() == 900.0


def test_generate_bounding_box_falls_back_to_ttf_head(
    liberation_bytes: bytes,
) -> None:
    """No descriptor /FontBBox — read xMin/yMin/xMax/yMax from head."""
    font = _embedded_font(liberation_bytes)
    # No /FontBBox on descriptor — fallback path.
    result = font.generate_bounding_box()
    assert result is not None
    # Liberation Sans head table carries a non-degenerate bbox.
    assert result.get_upper_right_x() > result.get_lower_left_x()
    assert result.get_upper_right_y() > result.get_lower_left_y()


def test_generate_bounding_box_none_without_font() -> None:
    """No descriptor, no embedded TTF — nothing to answer with."""
    font = PDTrueTypeFont()
    assert font.generate_bounding_box() is None


def test_generate_bounding_box_internal_alias_matches_public(
    liberation_bytes: bytes,
) -> None:
    """The underscore variant remains as an internal alias and returns
    the same value as the public method."""
    font = _embedded_font(liberation_bytes)
    public = font.generate_bounding_box()
    private = font._generate_bounding_box()
    assert public == private


# ---------- get_parser --------------------------------------------------


def test_get_parser_returns_ttf_parser_for_truetype_magic(
    liberation_bytes: bytes,
) -> None:
    """The standard 0x00010000 SFNT magic → TTFParser (the base class)."""
    parser = PDTrueTypeFont.get_parser(liberation_bytes)
    assert isinstance(parser, TTFParser)
    # OTFParser extends TTFParser; make sure we got the base, not the OTF variant.
    assert not isinstance(parser, OTFParser)


def test_get_parser_returns_otf_parser_for_otto_magic() -> None:
    """The ``OTTO`` SFNT magic → OTFParser (CFF-flavoured OpenType)."""
    fake_otf = b"OTTO" + b"\x00" * 28
    parser = PDTrueTypeFont.get_parser(fake_otf)
    assert isinstance(parser, OTFParser)


def test_get_parser_accepts_file_like(liberation_bytes: bytes) -> None:
    """File-like input is peeked + rewound, not consumed."""
    stream = io.BytesIO(liberation_bytes)
    parser = PDTrueTypeFont.get_parser(stream)
    assert isinstance(parser, TTFParser)
    # Cursor must be at 0 — the parser sniff is non-destructive.
    assert stream.tell() == 0


def test_get_parser_is_embedded_flag_propagates() -> None:
    """The is_embedded flag flows into the constructed parser."""
    fake_otf = b"OTTO" + b"\x00" * 28
    parser = PDTrueTypeFont.get_parser(fake_otf, is_embedded=False)
    assert isinstance(parser, OTFParser)
    assert parser.is_embedded is False


def test_get_parser_is_static() -> None:
    """``get_parser`` is callable without a font instance — mirrors how
    upstream uses it internally as a helper before the font is built."""
    parser = PDTrueTypeFont.get_parser(b"\x00\x01\x00\x00" + b"\x00" * 20)
    assert isinstance(parser, TTFParser)


# ---------- get_path_from_outlines --------------------------------------


def test_get_path_from_outlines_none_for_truetype_font(
    liberation_bytes: bytes,
) -> None:
    """TrueType-flavoured fonts have no CFF outlines — return None."""
    font = _embedded_font(liberation_bytes)
    # Encoding is irrelevant: upstream short-circuits when otf is null
    # (line 590 is only reached when ``otf.isPostScript()`` is true).
    assert font.get_path_from_outlines(ord("A")) is None


def test_get_path_from_outlines_none_without_font_program() -> None:
    """No embedded TTF at all — nothing to draw from."""
    assert PDTrueTypeFont().get_path_from_outlines(65) is None


def test_get_path_from_outlines_none_without_encoding(
    liberation_bytes: bytes,
) -> None:
    """No /Encoding to resolve the code → glyph name — return None.

    For our LiberationSans (TrueType, not CFF), the method bails out on
    the ``get_cff() is None`` check first; the encoding fallback is
    exercised when the font *is* CFF — verified through the OTF/CFF
    fixtures in the fontbox cluster. Here we just check the safety
    guard exists when no encoding is set.
    """
    font = PDTrueTypeFont()
    # No descriptor, no encoding, no TTF — should return None safely.
    assert font.get_path_from_outlines(65) is None


# ---------- load --------------------------------------------------------


def test_load_from_bytes_builds_simple_font(liberation_bytes: bytes) -> None:
    """``load`` accepts raw TTF bytes and builds a wired-up simple font."""
    font = PDTrueTypeFont.load(None, liberation_bytes, WinAnsiEncoding.INSTANCE)
    assert isinstance(font, PDTrueTypeFont)
    assert font.is_embedded()
    # /Subtype must be /TrueType.
    assert (
        font.get_cos_object().get_name_as_string(COSName.get_pdf_name("Subtype"))
        == "TrueType"
    )
    # /Encoding round-trips.
    enc_obj = font.get_cos_object().get_item(COSName.get_pdf_name("Encoding"))
    assert enc_obj is not None


def test_load_from_path_builds_simple_font(liberation_bytes: bytes) -> None:
    """``load`` accepts a filesystem path."""
    font = PDTrueTypeFont.load(None, _TTF_FIXTURE, WinAnsiEncoding.INSTANCE)
    assert font.is_embedded()
    assert font.get_font_descriptor() is not None
    assert font.get_font_descriptor().get_font_file2() is not None


def test_load_from_stream_builds_simple_font(liberation_bytes: bytes) -> None:
    """``load`` accepts a file-like binary stream."""
    stream = io.BytesIO(liberation_bytes)
    font = PDTrueTypeFont.load(None, stream, WinAnsiEncoding.INSTANCE)
    assert font.is_embedded()


def test_load_from_pre_parsed_true_type_font(liberation_bytes: bytes) -> None:
    """``load`` accepts an already-parsed TrueTypeFont (mirrors
    upstream's ``load(PDDocument, TrueTypeFont, Encoding)`` overload)."""
    ttf = TrueTypeFont.from_bytes(liberation_bytes)
    font = PDTrueTypeFont.load(None, ttf, WinAnsiEncoding.INSTANCE)
    assert font.is_embedded()
    # The pre-parsed TTF is reused — same instance returned from the font.
    assert font.get_true_type_font() is ttf


def test_load_defaults_to_winansi_encoding(liberation_bytes: bytes) -> None:
    """``encoding=None`` defaults to WinAnsiEncoding — matches the spirit
    of upstream's embedder defaults for simple TrueType fonts."""
    font = PDTrueTypeFont.load(None, liberation_bytes)
    encoding = font.get_encoding_typed()
    assert isinstance(encoding, WinAnsiEncoding)


def test_load_accepts_custom_encoding(liberation_bytes: bytes) -> None:
    """A caller-supplied encoding is honoured."""
    font = PDTrueTypeFont.load(None, liberation_bytes, StandardEncoding.INSTANCE)
    encoding = font.get_encoding_typed()
    assert isinstance(encoding, StandardEncoding)


def test_load_populates_widths(liberation_bytes: bytes) -> None:
    """``/Widths`` is built from the TTF's hmtx table — the slot for 'A'
    should be a positive advance width in 1/1000 em."""
    font = PDTrueTypeFont.load(None, liberation_bytes, WinAnsiEncoding.INSTANCE)
    widths = font.get_widths()
    assert widths is not None
    assert len(widths) == 256
    # Liberation Sans 'A' is around 667 units in 1000-unit em.
    width_a = widths[ord("A")]
    assert 100 < width_a < 2000


def test_load_populates_font_descriptor_metrics(liberation_bytes: bytes) -> None:
    """``/FontDescriptor`` carries the TTF's bbox, ascent, descent."""
    font = PDTrueTypeFont.load(None, liberation_bytes, WinAnsiEncoding.INSTANCE)
    fd = font.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_bounding_box() is not None
    # Bare minimum: ascent should be set and positive.
    cos = fd.get_cos_object()
    ascent = cos.get_int(COSName.get_pdf_name("Ascent"), 0)
    assert ascent > 0


def test_load_embeds_font_file2(liberation_bytes: bytes) -> None:
    """The TTF bytes round-trip through /FontFile2."""
    font = PDTrueTypeFont.load(None, liberation_bytes, WinAnsiEncoding.INSTANCE)
    fd = font.get_font_descriptor()
    assert fd is not None
    ff2 = fd.get_font_file2()
    assert ff2 is not None
    embedded_bytes = ff2.to_byte_array()
    assert embedded_bytes == liberation_bytes


def test_load_rejects_str_from_stream(liberation_bytes: bytes) -> None:
    """A file-like that yields ``str`` (text mode) is rejected — same
    convention :meth:`PDType0Font.load_ttf` uses."""

    class TextStream:
        def read(self, _size: int = -1) -> str:
            return "not bytes"

    with pytest.raises(TypeError, match="open in binary mode"):
        PDTrueTypeFont.load(None, TextStream())


def test_load_rejects_unrecognised_source_type() -> None:
    """A source we can't interpret raises TypeError with a clear message."""
    with pytest.raises(TypeError, match="cannot read font bytes"):
        PDTrueTypeFont.load(None, 12345)  # type: ignore[arg-type]
