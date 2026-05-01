"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.OpenTypeFont`.

Covers:
* ``OpenTypeFont`` is-a ``TrueTypeFont`` (PDFBox hierarchy preserved).
* :meth:`get_cff` returns the appropriate :class:`CFFFont` subclass
  (CFFType1Font for name-keyed CFF, ``None`` when no CFF present).
* :meth:`is_post_script` and :meth:`is_supported_otf` predicates.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.ttf import OpenTypeFont, OTFParser, TrueTypeFont

FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _make_t2_empty():
    from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415

    cs = T2CharString()
    cs.program = ["endchar"]
    return cs


def _synth_otf_name_keyed() -> bytes:
    """Build a minimal name-keyed CFF (Type 1-flavoured) OpenType font."""
    try:
        from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
    except ImportError:
        pytest.skip("fontTools FontBuilder not available")

    fb = FontBuilder(unitsPerEm=1000, isTTF=False)
    glyph_order = [".notdef", "A"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A"})
    cs = {name: _make_t2_empty() for name in glyph_order}
    fb.setupCFF(
        psName="NameKeyedOTF",
        fontInfo={"FullName": "Name Keyed OTF"},
        charStringsDict=cs,
        privateDict={},
    )
    fb.setupHorizontalMetrics({name: (500, 0) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "NK", "styleName": "Regular"})
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


# ---------- inheritance / hierarchy ---------------------------------------


def test_open_type_font_is_truetypefont() -> None:
    assert issubclass(OpenTypeFont, TrueTypeFont)


# ---------- predicates -----------------------------------------------------


def test_is_post_script_returns_true(name_keyed_otf: OpenTypeFont) -> None:
    assert name_keyed_otf.is_post_script() is True


def test_is_supported_otf_true_when_cff_present(
    name_keyed_otf: OpenTypeFont,
) -> None:
    assert name_keyed_otf.is_supported_otf() is True


def test_is_supported_otf_false_when_no_cff() -> None:
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    parser = OTFParser()
    font = parser.parse(FIXTURE_TTF.read_bytes())
    # The TTF fixture has no CFF table.
    assert isinstance(font, OpenTypeFont)
    assert font.is_supported_otf() is False


# ---------- get_cff() ------------------------------------------------------


def test_get_cff_returns_cfffont(name_keyed_otf: OpenTypeFont) -> None:
    cff = name_keyed_otf.get_cff()
    assert cff is not None
    assert isinstance(cff, CFFFont)


def test_get_cff_returns_type1_for_name_keyed(
    name_keyed_otf: OpenTypeFont,
) -> None:
    cff = name_keyed_otf.get_cff()
    assert isinstance(cff, CFFType1Font)
    assert not isinstance(cff, CFFCIDFont)
    assert cff.is_cid_font() is False
    assert cff.get_name() == "NameKeyedOTF"


def test_get_cff_caches_result(name_keyed_otf: OpenTypeFont) -> None:
    cff1 = name_keyed_otf.get_cff()
    cff2 = name_keyed_otf.get_cff()
    assert cff1 is cff2


def test_get_cff_returns_none_when_no_cff_table() -> None:
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    parser = OTFParser()
    font = parser.parse(FIXTURE_TTF.read_bytes())
    assert isinstance(font, OpenTypeFont)
    assert font.get_cff() is None


# ---------- has_layout_tables -------------------------------------------


def test_has_layout_tables_false_for_minimal_otf(
    name_keyed_otf: OpenTypeFont,
) -> None:
    # Synthesised CFF font has no GPOS/GSUB/BASE/GDEF/OTL — predicate must
    # return False.
    assert name_keyed_otf.has_layout_tables() is False


def test_has_layout_tables_true_when_gsub_present() -> None:
    """A real font shipped with a GSUB table (LiberationSans) reports
    ``has_layout_tables()`` as True even when consumed via OTFParser.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    parser = OTFParser()
    font = parser.parse(FIXTURE_TTF.read_bytes())
    assert isinstance(font, OpenTypeFont)
    # LiberationSans ships GSUB / GPOS — pick whichever the predicate sees.
    assert font.has_layout_tables() is (
        font.has_table("GSUB")
        or font.has_table("GPOS")
        or font.has_table("BASE")
        or font.has_table("GDEF")
        or font.has_table("OTL ")
    )
    assert font.has_layout_tables() is True
