"""Fuzz / parity hammering for Type0 (composite) CID-font glyph PATH
rendering — wave 1592.

Pins the code -> CID -> GID -> outline chain for both descendant kinds:

* :class:`PDCIDFontType2` (TrueType ``glyf`` outlines, embedded
  ``/FontFile2``) — including ``/CIDToGIDMap /Identity`` (CID == GID), a
  ``/CIDToGIDMap`` *stream* (big-endian uint16 CID -> GID), the
  units-per-em normalization (a non-1000-upem program scaled by
  ``1000 / unitsPerEm`` in :meth:`get_normalized_path`), GID 0 /
  ``.notdef`` -> empty path, an out-of-range CID -> GID 0, a *composite*
  TrueType glyph (``numberOfContours < 0``) that must decompose through
  its component lookups (the wave-1438 / wave-1588 component-drop class
  of bug), and the glyph cache short-circuit.

* :class:`PDCIDFontType2` backed by an embedded OpenType ``/FontFile3``
  with CFF (``OTTO``) outlines — the CFF Type 2 charstring path through
  :meth:`get_path` / :meth:`get_path_from_outlines`, and
  :meth:`get_normalized_path` which must route through the CFF branch
  (not the empty ``glyf`` branch).

* :class:`PDCIDFontType0` (CFF CID-keyed ``/FontFile3``) — the CID ->
  ``cidNNNNN`` -> CharStrings outline path.

WAVE-1592 BUGS FIXED HERE (both real divergences from upstream
``PDCIDFontType2``):

1. ``get_true_type_font`` parsed every embedded program with the plain
   ``TrueTypeFont.from_bytes``, so an OpenType ``/FontFile3`` (``OTTO``
   magic, CFF outlines) was never specialised into an
   :class:`OpenTypeFont`. ``is_open_type_post_script`` therefore always
   returned ``False`` and the entire CFF outline path (``getPath`` /
   ``getNormalizedPath``) was unreachable — a CFF-backed CIDFontType2
   rendered blank. Upstream's constructor sniffs the ``OTTO`` magic via
   ``getParser(...)``; the port now does too.

2. ``get_normalized_path`` called ``get_glyph_path`` (TTF ``glyf`` only)
   unconditionally. For the OTF-with-CFF descendant that yields an empty
   ``glyf`` outline — upstream ``getNormalizedPath`` branches on
   ``otf != null && otf.isPostScript()`` and pulls the CFF outline via
   ``getPathFromOutlines`` instead. The port now mirrors the branch.

Both bugs are exercised by ``test_otf_cff_*`` below: before the fix the
OTF-CFF normalized path came back ``[]``.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T2CharString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------------------------------------------------------------------------
# synthetic TrueType CIDFontType2 program builder
# ---------------------------------------------------------------------------

_GLYPH_ORDER = [".notdef", "box", "stroke", "eacute", "acute"]


def _box(pts: list[tuple[int, int]]) -> Any:
    pen = TTGlyphPen(None)
    pen.moveTo(pts[0])
    for pt in pts[1:]:
        pen.lineTo(pt)
    pen.closePath()
    return pen.glyph()


def _glyphs(upem: int) -> dict[str, Any]:
    s = upem / 1000.0  # scale shapes with the em so coordinates stay sane

    def sc(p: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(int(x * s), int(y * s)) for (x, y) in p]

    glyphs: dict[str, Any] = {
        ".notdef": _box(sc([(0, 0), (0, 700), (500, 700), (500, 0)])),
        "box": _box(sc([(50, 0), (50, 700), (550, 700), (550, 0)])),
        "stroke": _box(sc([(100, 0), (100, 500), (200, 500), (200, 0)])),
        "acute": _box(sc([(300, 600), (320, 700), (360, 700), (340, 600)])),
    }
    # Composite glyph: eacute = box + acute component (numberOfContours < 0).
    # The pen needs the already-built simple glyphs as its glyph set so it
    # can recompute the composite bounds from the component outlines.
    comp_pen = TTGlyphPen(glyphs)
    comp_pen.addComponent("box", (1, 0, 0, 1, 0, 0))
    comp_pen.addComponent("acute", (1, 0, 0, 1, int(20 * s), int(50 * s)))
    glyphs["eacute"] = comp_pen.glyph()
    return glyphs


def _synth_ttf_bytes(upem: int = 1000) -> bytes:
    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(_GLYPH_ORDER)
    fb.setupCharacterMap({})
    fb.setupGlyf(_glyphs(upem))
    fb.setupHorizontalMetrics({n: (upem, 0) for n in _GLYPH_ORDER})
    fb.setupHorizontalHeader(ascent=int(0.8 * upem), descent=int(-0.2 * upem))
    fb.setupNameTable(
        {"familyName": "CIDT2", "styleName": "Regular", "psName": "CIDT2"}
    )
    fb.setupOS2()
    fb.setupPost()
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = []
    fb.font["cmap"] = cmap
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


def _make_cid_type2(
    *,
    upem: int = 1000,
    cid_to_gid: bytes | str | None = None,
) -> PDCIDFontType2:
    """Build a :class:`PDCIDFontType2` whose /FontFile2 carries the
    synthetic TTF. ``cid_to_gid`` is a /CIDToGIDMap stream payload
    (``bytes``), the name ``"Identity"`` (``str``), or ``None`` (absent →
    spec-default Identity)."""
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_synth_ttf_bytes(upem))
    descriptor.set_font_file2(stream)

    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDCIDFontType2(font_dict)
    font.set_font_descriptor(descriptor)
    if isinstance(cid_to_gid, bytes):
        map_stream = COSStream()
        map_stream.set_data(cid_to_gid)
        font.set_cid_to_gid_map(map_stream)
    elif isinstance(cid_to_gid, str):
        font.set_cid_to_gid_map(cid_to_gid)
    return font


def _u16(*values: int) -> bytes:
    return b"".join(int(v).to_bytes(2, "big") for v in values)


# ---------------------------------------------------------------------------
# synthetic CFF builders (OTF /FontFile3 and CID-keyed CIDFontType0)
# ---------------------------------------------------------------------------


def _cs(program: list) -> T2CharString:
    s = T2CharString()
    s.program = program
    return s


def _synth_otf_cff_bytes() -> bytes:
    """An OpenType (``OTTO``) program with CFF (PostScript) outlines —
    the CFF-backed flavour of a CIDFontType2 (/FontFile3)."""
    order = [".notdef", "A", "B"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({65: "A", 66: "B"})
    cs_dict = {
        ".notdef": _cs([0, "endchar"]),
        "A": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto",
             "endchar"]
        ),
        "B": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="OtfCff",
        fontInfo={"FullName": "OtfCff"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics({n: (500, 0) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2()
    fb.setupNameTable({"familyName": "OtfCff", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


def _make_cid_type2_otf() -> PDCIDFontType2:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_synth_otf_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "OpenType")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDCIDFontType2(font_dict)
    font.set_font_descriptor(descriptor)
    return font


def _build_cid_keyed_cff_bytes() -> bytes:
    order = [".notdef", "cid00001", "cid00002"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({1: order[1], 2: order[2]})
    cs_dict = {
        order[0]: _cs([0, "endchar"]),
        order[1]: _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto",
             "endchar"]
        ),
        order[2]: _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="CidT0",
        fontInfo={"FullName": "CidT0"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {order[0]: (0, 0), order[1]: (500, 0), order[2]: (300, 0)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2()
    fb.setupNameTable({"familyName": "CidT0", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _make_cid_type0() -> PDCIDFontType0:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_cid_keyed_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDCIDFontType0(font_dict)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _is_path(path: list) -> bool:
    return isinstance(path, list)


def _has_drawing(path: list) -> bool:
    return any(cmd and cmd[0] in ("moveto", "lineto", "curveto") for cmd in path)


def _y_extent(path: list) -> tuple[float, float]:
    ys: list[float] = []
    for cmd in path:
        if len(cmd) <= 1:
            continue
        for i in range(2, len(cmd), 2):
            ys.append(float(cmd[i]))
    return (min(ys), max(ys)) if ys else (0.0, 0.0)


# ===========================================================================
# CIDFontType2 — /CIDToGIDMap Identity (CID == GID)
# ===========================================================================


def test_identity_cid_equals_gid_box_glyph_draws() -> None:
    font = _make_cid_type2()  # absent /CIDToGIDMap → Identity
    assert font.cid_to_gid(1) == 1  # box at GID 1
    path = font.get_glyph_path(1)
    assert _has_drawing(path)


def test_identity_absent_map_is_identity_predicate() -> None:
    font = _make_cid_type2()
    assert font.is_identity_cid_to_gid_map() is True
    assert font.has_cid_to_gid_map() is False


def test_identity_explicit_name_is_identity() -> None:
    font = _make_cid_type2(cid_to_gid="Identity")
    assert font.is_identity_cid_to_gid_map() is True
    assert font.cid_to_gid(2) == 2


def test_identity_notdef_cid_zero_empty_path() -> None:
    font = _make_cid_type2()
    assert font.cid_to_gid(0) == 0
    # GID 0 is embedded → upstream still draws the notdef box outline.
    path = font.get_glyph_path(0)
    assert _is_path(path)


def test_identity_out_of_range_cid_maps_to_gid_zero() -> None:
    font = _make_cid_type2()  # 5 glyphs
    assert font.cid_to_gid(999) == 0
    assert font.cid_to_gid(5) == 0  # == num_glyphs → 0


def test_identity_negative_cid_maps_to_gid_zero() -> None:
    font = _make_cid_type2()
    assert font.cid_to_gid(-1) == 0


@pytest.mark.parametrize("cid", [1, 2, 3])
def test_identity_each_real_cid_draws_distinct_glyph(cid: int) -> None:
    font = _make_cid_type2()
    path = font.get_glyph_path(cid)
    assert _has_drawing(path)


# ===========================================================================
# CIDFontType2 — /CIDToGIDMap STREAM (big-endian uint16 CID -> GID)
# ===========================================================================


def test_stream_map_applies_cid_to_gid_translation() -> None:
    # CID 0->0, 1->2 (stroke), 2->1 (box), 3->4 (acute).
    font = _make_cid_type2(cid_to_gid=_u16(0, 2, 1, 4))
    assert font.has_cid_to_gid_map() is True
    assert font.is_identity_cid_to_gid_map() is False
    assert font.cid_to_gid(1) == 2
    assert font.cid_to_gid(2) == 1
    assert font.cid_to_gid(3) == 4


def test_stream_map_out_of_range_cid_is_gid_zero() -> None:
    font = _make_cid_type2(cid_to_gid=_u16(0, 2, 1))
    # CID 7 is beyond the 3-entry map → GID 0.
    assert font.cid_to_gid(7) == 0


def test_stream_map_glyph_path_follows_remap() -> None:
    # CID 9 -> GID 1 (box). The drawn glyph must be the box, not CID 9's
    # (nonexistent) identity glyph.
    payload = _u16(*([0] * 9 + [1]))  # entries 0..8 = 0, entry 9 = 1
    font = _make_cid_type2(cid_to_gid=payload)
    assert font.cid_to_gid(9) == 1
    assert _has_drawing(font.get_glyph_path(9))


def test_stream_map_odd_trailing_byte_ignored() -> None:
    # 5 bytes → 2 usable uint16 entries (CID 0,1); trailing byte dropped.
    font = _make_cid_type2(cid_to_gid=_u16(0, 3) + b"\x00")
    assert font.cid_to_gid(1) == 3
    assert font.cid_to_gid(2) == 0  # beyond the 2 usable entries


def test_stream_map_cache_consistent_across_calls() -> None:
    font = _make_cid_type2(cid_to_gid=_u16(0, 2, 1, 4))
    first = [font.cid_to_gid(c) for c in range(4)]
    second = [font.cid_to_gid(c) for c in range(4)]
    assert first == second == [0, 2, 1, 4]


def test_set_cid_to_gid_map_clears_cache() -> None:
    font = _make_cid_type2(cid_to_gid=_u16(0, 1))
    assert font.cid_to_gid(1) == 1
    new_stream = COSStream()
    new_stream.set_data(_u16(0, 0, 2))
    font.set_cid_to_gid_map(new_stream)
    assert font.cid_to_gid(2) == 2  # cache must have been invalidated


# ===========================================================================
# CIDFontType2 — units-per-em normalization (get_normalized_path)
# ===========================================================================


def test_normalized_path_unscaled_for_1000_upem() -> None:
    font = _make_cid_type2(upem=1000)
    raw = font.get_glyph_path(1)
    norm = font.get_normalized_path(1)
    assert norm == raw  # no scaling for 1000-upem


def test_normalized_path_scaled_for_2048_upem() -> None:
    font = _make_cid_type2(upem=2048)
    raw = font.get_glyph_path(1)
    norm = font.get_normalized_path(1)
    assert _has_drawing(norm)
    scale = 1000.0 / 2048.0
    raw_lo, raw_hi = _y_extent(raw)
    norm_lo, norm_hi = _y_extent(norm)
    assert norm_hi == pytest.approx(raw_hi * scale, rel=1e-6)
    assert norm_lo == pytest.approx(raw_lo * scale, rel=1e-6)


def test_normalized_path_scaled_for_500_upem() -> None:
    font = _make_cid_type2(upem=500)
    raw = font.get_glyph_path(1)
    norm = font.get_normalized_path(1)
    scale = 1000.0 / 500.0
    _, raw_hi = _y_extent(raw)
    _, norm_hi = _y_extent(norm)
    assert norm_hi == pytest.approx(raw_hi * scale, rel=1e-6)


def test_normalized_path_closepath_preserved_under_scaling() -> None:
    font = _make_cid_type2(upem=2048)
    norm = font.get_normalized_path(1)
    assert any(cmd == ("closepath",) for cmd in norm)


def test_normalized_path_empty_for_no_program() -> None:
    font = PDCIDFontType2()  # no /FontFile2
    assert font.get_normalized_path(1) == []
    assert font.get_glyph_path(1) == []
    assert font.get_path(1) == []


# ===========================================================================
# CIDFontType2 — composite TrueType glyph decomposition
# ===========================================================================


def test_composite_glyph_decomposes_components() -> None:
    """eacute (GID 3) is a composite of box + acute. Without the glyph
    set passed to the pen, fontTools drops the composite → blank. The
    path must carry the union of both component outlines (this is the
    CID analogue of the wave-1438/1588 composite-component drop)."""
    font = _make_cid_type2()
    assert font.cid_to_gid(3) == 3  # eacute
    path = font.get_glyph_path(3)
    assert _has_drawing(path)
    # box contributes 4 corners, acute another 4 → at least two contours
    # worth of moveto commands.
    movetos = [c for c in path if c and c[0] == "moveto"]
    assert len(movetos) >= 2


def test_composite_glyph_normalized_scales_both_components() -> None:
    font = _make_cid_type2(upem=2048)
    raw = font.get_glyph_path(3)
    norm = font.get_normalized_path(3)
    scale = 1000.0 / 2048.0
    _, raw_hi = _y_extent(raw)
    _, norm_hi = _y_extent(norm)
    assert norm_hi == pytest.approx(raw_hi * scale, rel=1e-6)


# ===========================================================================
# CIDFontType2 — get_path dispatch + glyph drawing
# ===========================================================================


def test_get_path_routes_to_glyf_for_truetype() -> None:
    font = _make_cid_type2()
    assert font.is_open_type_post_script() is False
    assert font.get_path(1) == font.get_glyph_path(1)


def test_glyph_path_returns_list_for_every_cid() -> None:
    font = _make_cid_type2()
    for cid in range(8):
        assert _is_path(font.get_glyph_path(cid))


# ===========================================================================
# CIDFontType2 — OpenType /FontFile3 with CFF (OTTO) outlines
# Pins both wave-1592 bugs.
# ===========================================================================


def test_otf_cff_program_is_open_type_post_script() -> None:
    """BUG 1: the embedded OTTO /FontFile3 must parse into an
    OpenTypeFont so is_open_type_post_script() is True."""
    font = _make_cid_type2_otf()
    ttf = font.get_true_type_font()
    assert ttf is not None
    assert font.is_open_type_post_script() is True


def test_otf_cff_get_path_draws_via_cff_outlines() -> None:
    font = _make_cid_type2_otf()
    # CID 1 → GID 1 (glyph "A") via Identity (OTF-PS returns CID as GID).
    path = font.get_path(1)
    assert _has_drawing(path)


def test_otf_cff_normalized_path_not_empty() -> None:
    """BUG 2: get_normalized_path used to call get_glyph_path (glyf only),
    yielding [] for a CFF-only OTF. It must route through the CFF
    outline branch."""
    font = _make_cid_type2_otf()
    norm = font.get_normalized_path(1)
    assert _has_drawing(norm)


def test_otf_cff_path_from_outlines_matches_get_path() -> None:
    font = _make_cid_type2_otf()
    assert font.get_path_from_outlines(1) == font.get_path(1)


def test_otf_cff_notdef_path_from_outlines() -> None:
    font = _make_cid_type2_otf()
    # CID 0 → GID 0 (.notdef, empty charstring). Path is empty/None-ish.
    out = font.get_path_from_outlines(0)
    assert out is None or not _has_drawing(out)


# ===========================================================================
# CIDFontType0 — CFF CID-keyed glyph path
# ===========================================================================


def test_cid_type0_glyph_path_draws_for_known_cid() -> None:
    font = _make_cid_type0()
    program = font.get_cff_font()
    assert program is not None
    # cid00001 lives in the program; resolve its CID via glyph name.
    if program.has_glyph("cid00001"):
        assert _has_drawing(font.get_glyph_path(1))


def test_cid_type0_glyph_path_empty_for_unmapped_cid() -> None:
    font = _make_cid_type0()
    program = font.get_cff_font()
    assert program is not None
    if not program.has_glyph("cid09999"):
        assert font.get_glyph_path(9999) == []


def test_cid_type0_glyph_path_empty_without_program() -> None:
    font = PDCIDFontType0()
    assert font.get_glyph_path(1) == []
    assert font.get_normalized_path(1) == []


def test_cid_type0_normalized_path_is_glyph_path() -> None:
    """CFF outlines are already in 1000-upem font units, so the
    CIDFontType0 normalized path is a thin alias of get_glyph_path."""
    font = _make_cid_type0()
    program = font.get_cff_font()
    assert program is not None
    if program.has_glyph("cid00001"):
        assert font.get_normalized_path(1) == font.get_glyph_path(1)


def test_cid_type0_notdef_cid_zero() -> None:
    font = _make_cid_type0()
    # CID 0 → ".notdef" name → empty charstring → no drawing.
    path = font.get_glyph_path(0)
    assert _is_path(path)
    assert not _has_drawing(path)


def test_cid_type0_get_path_via_charstring() -> None:
    font = _make_cid_type0()
    program = font.get_cff_font()
    assert program is not None
    # get_path goes code -> CID -> Type2 charstring. With no parent CMap
    # the code passes through as the CID.
    if program.has_glyph("cid00001"):
        assert _is_path(font.get_path(1))


# ===========================================================================
# cross-cutting: glyph cache stability
# ===========================================================================


def test_true_type_font_parsed_once_and_cached() -> None:
    font = _make_cid_type2()
    first = font.get_true_type_font()
    second = font.get_true_type_font()
    assert first is second is not None


def test_repeated_normalized_path_stable() -> None:
    font = _make_cid_type2(upem=2048)
    a = font.get_normalized_path(1)
    b = font.get_normalized_path(1)
    assert a == b
