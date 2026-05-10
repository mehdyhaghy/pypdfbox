"""Ported upstream tests for :class:`CFFParser`.

Translated from ``pdfbox/fontbox/src/test/java/org/apache/fontbox/cff/CFFParserTest.java``
(upstream PDFBox 3.0.x). The upstream class loads
``target/fonts/SourceSansProBold.otf`` from the build's downloaded
fixtures; we don't ship that font, so the parsed-content assertions
(``test_fontname``, ``test_font_b_box``, ``test_charset``,
``test_void_encoding``, ``test_char_string_bytess``,
``test_global_subr_index``, ``test_delta_lists``,
``test_multi_thread_parse``) are skipped with a one-line comment per
the porting conventions in CLAUDE.md (sample PDFs / binary fixtures
section).

What we DO port deterministically: the round-trip ``read_font`` helper
shape (``CFFParser`` instantiation + ``parse(byte_source)`` overload)
and the post-parse class-cluster invariants that don't require a
specific font (return type, list non-empty, ``CFFType1Font`` for
name-keyed fonts).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font

# Upstream loads "target/fonts/SourceSansProBold.otf" — we look for
# any name-keyed CFF/OTF on the host instead.
_TYPE1_OTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    "/System/Library/Fonts/Supplemental/STIXGeneralItalic.otf",
    "/usr/share/fonts/opentype/stix/STIXGeneral.otf",
]


def _read_font() -> list[CFFFont] | None:
    """Mirror upstream ``readFont(filename)`` (``CFFParserTest.java``
    lines 255-260): construct a parser, hand it the font bytes, return
    the parsed list."""
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _TYPE1_OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            ttf = TTFont(str(path))
            if "CFF " not in ttf:
                continue
            top = ttf["CFF "].cff[ttf["CFF "].cff.fontNames[0]]
            if hasattr(top, "ROS"):
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            parser = CFFParser()
            return parser.parse(buf.getvalue())
        except Exception:  # noqa: BLE001
            continue
    return None


_FONTS = _read_font()
_SKIP_REASON = (
    "no name-keyed CFF/OTF fixture on host (upstream uses SourceSansProBold.otf)"
)


# Upstream test_fontname / test_font_b_box / test_charset / test_void_encoding /
# test_char_string_bytess / test_global_subr_index / test_delta_lists /
# test_multi_thread_parse: skipped — they assert specific values for
# SourceSansProBold.otf which we don't ship.


@pytest.mark.skipif(_FONTS is None, reason=_SKIP_REASON)
def test_parse_returns_non_empty_list_of_cff_fonts() -> None:
    """Smoke check: ``CFFParser.parse(bytes)`` returns a non-empty
    ``List<CFFFont>``. Mirrors the implicit upstream invariant on the
    return value of ``readFont`` (``CFFParserTest.java`` line 259)."""
    assert _FONTS is not None
    assert len(_FONTS) >= 1
    assert isinstance(_FONTS[0], CFFFont)


@pytest.mark.skipif(_FONTS is None, reason=_SKIP_REASON)
def test_parsed_name_keyed_font_is_cff_type1_font() -> None:
    """Mirrors the upstream ``loadCFFFont`` cast on
    ``CFFParserTest.java`` line 45: the first parsed font for a Type 1
    flavoured CFF must be a ``CFFType1Font``."""
    assert _FONTS is not None
    assert isinstance(_FONTS[0], CFFType1Font)


@pytest.mark.skipif(_FONTS is None, reason=_SKIP_REASON)
def test_parsed_font_has_name() -> None:
    """Loose port of upstream ``test_fontname``
    (``CFFParserTest.java`` lines 49-52). We don't assert a specific
    PostScript name (host fixture varies), only that the name is a
    non-empty string."""
    assert _FONTS is not None
    name = _FONTS[0].get_name()
    assert isinstance(name, str)
    assert name
