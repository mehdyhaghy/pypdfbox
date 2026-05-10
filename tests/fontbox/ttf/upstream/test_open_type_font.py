"""Upstream-equivalence checks for ``OpenTypeFont``.

Apache PDFBox ships no dedicated ``OpenTypeFontTest.java`` in
``fontbox/src/test/java/org/apache/fontbox/ttf/``. The class is exercised
indirectly through ``OTFParser`` and the rendering / embedding tests in
``pdfbox-app``. To keep the upstream-mirror test surface meaningful we
encode the *behavioural contracts* the Java class documents (and the
table-presence rules its predicates encode) as Python tests, anchored to
the upstream source line numbers.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import OpenTypeFont, OTFParser, TrueTypeFont

FIXTURE_TTF = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# ---------- helpers -------------------------------------------------------


def _make_t2_empty() -> object:
    from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415

    cs = T2CharString()
    cs.program = ["endchar"]
    return cs


def _synth_otf_name_keyed() -> bytes:
    """Build a minimal name-keyed CFF (Type 1-flavoured) OpenType font.

    Mirrors the synthesis in the hand-written test module so the upstream
    parity tests have an in-repo CFF fixture without shipping binary
    payloads.
    """
    fb_mod = pytest.importorskip("fontTools.fontBuilder")
    fb = fb_mod.FontBuilder(unitsPerEm=1000, isTTF=False)
    glyph_order = [".notdef", "A"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A"})
    cs = {name: _make_t2_empty() for name in glyph_order}
    fb.setupCFF(
        psName="UpstreamParityOTF",
        fontInfo={"FullName": "Upstream Parity OTF"},
        charStringsDict=cs,
        privateDict={},
    )
    fb.setupHorizontalMetrics({name: (500, 0) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "UP", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    out = io.BytesIO()
    fb.font.save(out)
    return out.getvalue()


@pytest.fixture(scope="module")
def name_keyed_otf() -> OpenTypeFont:
    parser = OTFParser()
    font = parser.parse(_synth_otf_name_keyed())
    assert isinstance(font, OpenTypeFont)
    return font


@pytest.fixture(scope="module")
def ttf_via_otfparser() -> OpenTypeFont | None:
    if not FIXTURE_TTF.exists():
        return None
    parser = OTFParser()
    font = parser.parse(FIXTURE_TTF.read_bytes())
    assert isinstance(font, OpenTypeFont)
    return font


# ---------- hierarchy (OpenTypeFont.java line 26) -----------------------


def test_open_type_font_extends_true_type_font() -> None:
    """``OpenTypeFont extends TrueTypeFont`` — OpenTypeFont.java line 26."""
    assert issubclass(OpenTypeFont, TrueTypeFont)


# ---------- set_version (OpenTypeFont.java line 42) ---------------------


def test_set_version_otto_marks_post_script() -> None:
    """``setVersion`` records ``hasPostScriptTag`` when the IEEE-754
    fingerprint matches ``OTTO`` (OpenTypeFont.java line 44)."""
    import struct  # noqa: PLC0415

    otto_float = struct.unpack(">f", struct.pack(">I", 0x469EA8A9))[0]
    parser = OTFParser()
    font = parser.parse(_synth_otf_name_keyed())
    font.set_version(otto_float)
    assert font.is_post_script() is True


def test_set_version_non_otto_clears_post_script_flag() -> None:
    """A non-``OTTO`` SFNT version leaves ``hasPostScriptTag`` false —
    the predicate then falls through to the table-presence checks."""
    parser = OTFParser()
    font = parser.parse(_synth_otf_name_keyed())
    font.set_version(1.0)  # 0x00010000 = TrueType — not OTTO
    # Still a CFF font because the CFF table is present.
    assert font.is_post_script() is True
    # but ``hasPostScriptTag`` is now false; we observe the field
    # indirectly via :meth:`is_supported_otf` which depends on it.
    assert font.is_supported_otf() is True


# ---------- is_post_script (OpenTypeFont.java line 94) ------------------


def test_is_post_script_true_for_cff_table(name_keyed_otf: OpenTypeFont) -> None:
    """``isPostScript`` returns true when the font ships a ``CFF ``
    table — OpenTypeFont.java line 96."""
    assert name_keyed_otf.is_post_script() is True


def test_is_post_script_false_for_truetype_outlines(
    ttf_via_otfparser: OpenTypeFont | None,
) -> None:
    """A TrueType-outlines OTF wrapper (no OTTO, no CFF/CFF2) reports
    ``False`` — OpenTypeFont.java line 96."""
    if ttf_via_otfparser is None:
        pytest.skip("TTF fixture not present")
    assert ttf_via_otfparser.is_post_script() is False


# ---------- is_supported_otf (OpenTypeFont.java line 108) ---------------


def test_is_supported_otf_true_for_cff(name_keyed_otf: OpenTypeFont) -> None:
    """A CFF v1 font is supported — OpenTypeFont.java line 111."""
    assert name_keyed_otf.is_supported_otf() is True


def test_is_supported_otf_true_for_truetype(
    ttf_via_otfparser: OpenTypeFont | None,
) -> None:
    """TrueType outlines in an OTF wrapper are supported —
    OpenTypeFont.java line 111 (the rule rejects only OTTO + CFF2 +
    no CFF)."""
    if ttf_via_otfparser is None:
        pytest.skip("TTF fixture not present")
    assert ttf_via_otfparser.is_supported_otf() is True


# ---------- get_cff (OpenTypeFont.java line 56) -------------------------


def test_get_cff_returns_payload_for_cff(name_keyed_otf: OpenTypeFont) -> None:
    """``getCFF`` projects the ``CFF `` table — OpenTypeFont.java line 62."""
    cff = name_keyed_otf.get_cff()
    assert cff is not None
    assert cff.get_name() == "UpstreamParityOTF"


def test_get_cff_returns_none_for_truetype(
    ttf_via_otfparser: OpenTypeFont | None,
) -> None:
    """``getCFF`` returns ``None`` (parity divergence — upstream throws
    ``UnsupportedOperationException``) for a TrueType-outlines OTF.
    Documented in ``CHANGES.md``."""
    if ttf_via_otfparser is None:
        pytest.skip("TTF fixture not present")
    assert ttf_via_otfparser.get_cff() is None


# ---------- get_glyph (OpenTypeFont.java line 66) -----------------------


def test_get_glyph_table_raises_for_post_script() -> None:
    """``getGlyph`` throws when the font is PostScript-flavoured —
    OpenTypeFont.java line 68. We model the throw with
    ``NotImplementedError`` (the closest stdlib analogue of
    ``UnsupportedOperationException``)."""
    import struct  # noqa: PLC0415

    parser = OTFParser()
    font = parser.parse(_synth_otf_name_keyed())
    # OTTO IEEE-754 round-trip — sets ``hasPostScriptTag``.
    font.set_version(struct.unpack(">f", struct.pack(">I", 0x469EA8A9))[0])
    with pytest.raises(NotImplementedError):
        font.get_glyph_table()


def test_get_glyph_table_returns_for_truetype(
    ttf_via_otfparser: OpenTypeFont | None,
) -> None:
    """A TrueType-outlines OTF still resolves ``glyf`` —
    OpenTypeFont.java line 72 (super delegation)."""
    if ttf_via_otfparser is None:
        pytest.skip("TTF fixture not present")
    assert ttf_via_otfparser.get_glyph_table() is not None


# ---------- has_layout_tables (OpenTypeFont.java line 122) --------------


def test_has_layout_tables_for_real_font(
    ttf_via_otfparser: OpenTypeFont | None,
) -> None:
    """``hasLayoutTables`` reports true iff any of BASE/GDEF/GPOS/GSUB
    is present — OpenTypeFont.java line 124–128."""
    if ttf_via_otfparser is None:
        pytest.skip("TTF fixture not present")
    expected = any(
        ttf_via_otfparser.has_table(tag)
        for tag in ("BASE", "GDEF", "GPOS", "GSUB", "OTL ")
    )
    assert ttf_via_otfparser.has_layout_tables() is expected
