from __future__ import annotations

import io

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- helpers ----------


def _build_cid_keyed_cff_bytes() -> bytes:
    """Build a tiny in-memory CFF font set using ``cidNNNNN`` glyph
    names (the form fontTools surfaces for CID-keyed CFF charstrings).

    This mirrors the byte form a PDF ``/FontFile3`` stream with
    ``/Subtype /CIDFontType0C`` carries — for the purposes of our
    glyph lookup, fontTools doesn't care whether the underlying
    charset is technically a CID charset, it cares that the lookup
    name matches.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "cid00001", "cid00002"])
    fb.setupCharacterMap({1: "cid00001", 2: "cid00002"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    cs_dict = {
        ".notdef": _cs([0, "endchar"]),
        # CID 1: width 500, 100x700 box outline.
        "cid00001": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        # CID 2: width 300, single vertical stroke.
        "cid00002": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestCIDFontType0C",
        fontInfo={"FullName": "Test CID Font Type0C"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {".notdef": (0, 0), "cid00001": (500, 0), "cid00002": (300, 0)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)

    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _make_font_with_descriptor(
    *, font_file3_subtype: str | None = "CIDFontType0C", with_data: bool = True
) -> PDCIDFontType0:
    """Build a CIDFontType0 with an attached descriptor whose
    ``/FontFile3`` stream carries the specified ``/Subtype``. When
    ``with_data`` is False the stream is omitted entirely (no
    ``/FontFile3``)."""
    descriptor = PDFontDescriptor()
    if with_data:
        stream = COSStream()
        stream.set_data(_build_cid_keyed_cff_bytes())
        if font_file3_subtype is not None:
            stream.set_name(COSName.SUBTYPE, font_file3_subtype)  # type: ignore[attr-defined]
        descriptor.set_font_file3(stream)

    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedCIDFontType0C")
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDCIDFontType0(font_dict)


# ---------- code_to_cid identity ----------


def test_code_to_cid_is_identity_at_cid_layer() -> None:
    """At the CIDFontType0 layer the "code" arriving has already been
    CMap-decoded by the parent Type0 font, so this method is identity."""
    font = PDCIDFontType0()
    assert font.code_to_cid(0) == 0
    assert font.code_to_cid(1) == 1
    assert font.code_to_cid(0x4E00) == 0x4E00
    assert font.code_to_cid(65535) == 65535


# ---------- get_cff_font ----------


def test_get_cff_font_returns_none_when_no_descriptor() -> None:
    font = PDCIDFontType0()
    assert font.get_cff_font() is None


def test_get_cff_font_returns_none_when_no_font_file3() -> None:
    font = _make_font_with_descriptor(with_data=False)
    assert font.get_cff_font() is None


def test_get_cff_font_parses_font_file3_stream() -> None:
    font = _make_font_with_descriptor()
    cff = font.get_cff_font()
    assert isinstance(cff, CFFFont)
    assert cff.units_per_em == 1000


def test_get_cff_font_caches_result() -> None:
    font = _make_font_with_descriptor()
    first = font.get_cff_font()
    second = font.get_cff_font()
    assert first is second


def test_get_cff_font_returns_none_after_failed_parse() -> None:
    """A garbage /FontFile3 stream should be tolerated — parse failure
    is logged once and subsequent calls keep returning None without
    re-parsing."""
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not a valid CFF font set")
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDCIDFontType0(font_dict)
    assert font.get_cff_font() is None
    # Cached negative result.
    assert font.get_cff_font() is None


# ---------- set_cff_font injector ----------


def test_set_cff_font_injects_program_and_bypasses_parse() -> None:
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()  # no descriptor
    font.set_cff_font(cff)
    assert font.get_cff_font() is cff


def test_set_cff_font_none_clears_program() -> None:
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    font.set_cff_font(None)
    assert font.get_cff_font() is None


# ---------- is_embedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    assert PDCIDFontType0().is_embedded() is False
    assert PDCIDFontType0().is_cff_embedded() is False


def test_is_embedded_false_when_no_font_file3() -> None:
    font = _make_font_with_descriptor(with_data=False)
    assert font.is_embedded() is False
    assert font.is_cff_embedded() is False


def test_is_embedded_true_for_cid_font_type0c_subtype() -> None:
    font = _make_font_with_descriptor(font_file3_subtype="CIDFontType0C")
    assert font.is_embedded() is True
    assert font.is_cff_embedded() is True


def test_is_embedded_true_for_open_type_subtype() -> None:
    """OpenType-wrapped CFF programs are also considered embedded."""
    font = _make_font_with_descriptor(font_file3_subtype="OpenType")
    assert font.is_embedded() is True
    assert font.is_cff_embedded() is True


def test_is_cff_embedded_false_for_unknown_font_file3_subtype() -> None:
    """Strict CFF check rejects /Type1C even though base is_embedded
    accepts the /FontFile3 stream as a generic embedded program."""
    font = _make_font_with_descriptor(font_file3_subtype="Type1C")
    # Base liveness check still passes because /FontFile3 is present.
    assert font.is_embedded() is True
    # ...but the strict CFF check rejects the wrong subtype.
    assert font.is_cff_embedded() is False


def test_is_cff_embedded_false_when_font_file3_subtype_missing() -> None:
    font = _make_font_with_descriptor(font_file3_subtype=None)
    assert font.is_cff_embedded() is False


# ---------- get_glyph_width: /W -> CFF program -> /DW ----------


def test_get_glyph_width_uses_explicit_w_entry_first() -> None:
    """An entry in /W wins over both the CFF program and /DW."""
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    # /W: CID 1 -> 999
    w = COSArray([COSInteger.get(1), COSArray([COSInteger.get(999)])])
    font.set_w(w)
    assert font.get_glyph_width(1) == 999.0


def test_get_glyph_width_falls_through_w_to_cff_program() -> None:
    """No /W entry for CID 1 → CFF program advance is consulted."""
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    # CID 1 has CFF width 500 in our fixture.
    assert font.get_glyph_width(1) == 500.0
    assert font.get_glyph_width(2) == 300.0


def test_get_glyph_width_falls_through_to_dw_default() -> None:
    """No /W and no CFF program → /DW (which itself defaults to 1000)."""
    font = PDCIDFontType0()
    # No descriptor, no CFF program, no /W, no /DW -> spec default 1000.
    assert font.get_glyph_width(7) == 1000.0


def test_get_glyph_width_falls_through_to_explicit_dw() -> None:
    font = PDCIDFontType0()
    font.set_dw(500)
    assert font.get_glyph_width(7) == 500.0


def test_get_glyph_width_cff_unmapped_cid_falls_through_to_dw() -> None:
    """CID not in the CFF program → /DW fallback."""
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    font.set_dw(444)
    # CID 9999 is not in our fixture.
    assert font.get_glyph_width(9999) == 444.0


def test_get_glyph_width_w_takes_precedence_over_cff_for_same_cid() -> None:
    """Even when the CFF program has the glyph, /W wins."""
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    # /W overrides CID 1's CFF width (500) with 123.
    w = COSArray([COSInteger.get(1), COSArray([COSInteger.get(123)])])
    font.set_w(w)
    assert font.get_glyph_width(1) == 123.0
    # CID 2 not in /W → CFF wins.
    assert font.get_glyph_width(2) == 300.0


# ---------- get_glyph_path ----------


def test_get_glyph_path_returns_empty_when_no_program() -> None:
    font = PDCIDFontType0()
    assert font.get_glyph_path(1) == []


def test_get_glyph_path_returns_outline_for_known_cid() -> None:
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    path = font.get_glyph_path(1)
    assert len(path) >= 2
    assert path[0][0] == "moveto"
    assert path[-1] == ("closepath",)


def test_get_glyph_path_returns_empty_for_unmapped_cid() -> None:
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    assert font.get_glyph_path(9999) == []


def test_get_glyph_path_cid_zero_is_notdef() -> None:
    """CID 0 maps to ``.notdef`` in CID-keyed CFF; our fixture's
    .notdef is a single ``endchar`` — no draw commands emitted."""
    cff = CFFFont.from_bytes(_build_cid_keyed_cff_bytes())
    font = PDCIDFontType0()
    font.set_cff_font(cff)
    # No moveto in .notdef — empty draw output.
    assert font.get_glyph_path(0) == []


# ---------- subtype scaffolding sanity ----------


def test_subtype_constant_unchanged() -> None:
    """SUB_TYPE remains 'CIDFontType0' regardless of /FontFile3 contents."""
    assert PDCIDFontType0.SUB_TYPE == "CIDFontType0"
    assert PDCIDFontType0().get_subtype() == "CIDFontType0"


# ---------- end-to-end via real /FontFile3 (no injector) ----------


def test_get_glyph_width_via_real_font_file3_stream() -> None:
    """End-to-end: build /FontDescriptor with /FontFile3 + /Subtype
    /CIDFontType0C and verify the parse path lights up without
    ``set_cff_font``."""
    font = _make_font_with_descriptor(font_file3_subtype="CIDFontType0C")
    assert font.is_embedded() is True
    assert font.get_glyph_width(1) == 500.0
    assert font.get_glyph_width(2) == 300.0


def test_get_glyph_path_via_real_font_file3_stream() -> None:
    font = _make_font_with_descriptor(font_file3_subtype="CIDFontType0C")
    path = font.get_glyph_path(1)
    assert path[0][0] == "moveto"
    assert path[-1] == ("closepath",)
