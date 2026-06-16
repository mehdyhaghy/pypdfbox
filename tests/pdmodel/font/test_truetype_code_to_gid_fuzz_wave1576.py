"""Fuzz / parity hammering for ``PDTrueTypeFont`` code -> GID resolution.

Wave 1576. Pins :meth:`PDTrueTypeFont.code_to_gid` (and the internal
``_code_to_gid``) against the documented Apache PDFBox 3.0.7
``PDTrueTypeFont.codeToGID`` algorithm across the full cmap-subtable
selection cascade:

  * **non-symbolic** — ``/Encoding`` glyph name -> AGL unicode -> (3,1)
    Win-Unicode cmap; then the (1,0) Mac-Roman path via
    ``MacOSRomanEncoding.get_code(name)``; then the ``post``-table
    ``name_to_gid`` fallback;
  * **symbolic** — (3,1) Win-Unicode first (raw ``code`` unless the active
    encoding is WinAnsi/MacRoman, in which case via the glyph name); then
    (3,0) Win-Symbol with the ``raw`` / ``0xF000+`` / ``0xF100+`` /
    ``0xF200+`` cascade; then (1,0) Mac-Roman by raw ``code``;
  * the symbolic-flag-determines-strategy branch;
  * a code with no glyph anywhere -> GID 0 (``.notdef``);
  * ``/Differences`` feeding the non-symbolic unicode lookup.

The synthetic TTFs are built with fontTools, mirroring the reusable
builder pattern from
``tests/pdmodel/font/oracle/test_symbolic_ttf_oracle.py`` — controlled
cmap subtables, one distinct glyph per GID. The expected GID per case is
computed by hand from the upstream cascade, so a regression in the
ordering, the missing ``0xF000`` step, a wrong cmap selection, the Mac
path, or the ``name_to_gid`` last-resort fails loudly.

WAVE-1576 BUG FIXED HERE: the symbolic branch used to read the
*possibly-unresolved* ``self._encoding_typed`` cache instead of forcing
``get_encoding_typed()``. When ``code_to_gid`` was the first
encoding-consuming call on a symbolic font carrying a WinAnsi/MacRoman
``/Encoding``, the encoding looked like ``None`` and the (3,1) path fell
to the raw-code ``else`` branch — diverging from PDFBox, whose
``encoding`` field is always resolved. ``test_symbolic_winansi_first_call_*``
pins the fix.
"""

from __future__ import annotations

import io

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FtCmapSubtable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_NON_SYMBOLIC,
    FLAG_SYMBOLIC,
    PDFontDescriptor,
)
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

# Glyph order: index == GID. .notdef is GID 0; the rest are distinct boxes.
_GLYPH_ORDER = [".notdef", "g1", "g2", "g3", "g4", "g5", "g6"]


# ---------------------------------------------------------------------------
# synthetic TTF builder (controlled cmap subtables)
# ---------------------------------------------------------------------------


def _glyphs() -> dict:
    pens: dict = {}

    def box(name: str, pts: list[tuple[int, int]]) -> None:
        pen = TTGlyphPen(None)
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
        pens[name] = pen.glyph()

    base = [(50, 0), (50, 700), (550, 700), (550, 0)]
    for i, name in enumerate(_GLYPH_ORDER):
        shift = i * 10
        box(name, [(x + shift, y) for (x, y) in base])
    return pens


def _subtable(fmt: int, plat: int, enc: int, mapping: dict[int, str]):
    sub = FtCmapSubtable.getSubtableClass(fmt)(fmt)
    sub.format = fmt
    sub.platformID = plat
    sub.platEncID = enc
    sub.language = 0
    sub.cmap = mapping
    return sub


def _synth_ttf(
    subtables: list,
    *,
    post_names: dict[str, int] | None = None,
) -> bytes:
    """Build a TTF with ``_GLYPH_ORDER`` glyphs and the supplied cmap
    ``subtables`` (already-built fontTools subtable objects).

    ``post_names`` is unused for the explicit glyph names — the format-2
    ``post`` table that ``setupPost`` writes already carries the glyph
    order, so ``ttf.name_to_gid("g3")`` resolves. It is accepted for
    symmetry / documentation.
    """
    del post_names
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(_GLYPH_ORDER)
    fb.setupCharacterMap({})
    fb.setupGlyf(_glyphs())
    fb.setupHorizontalMetrics({n: (600, 50) for n in _GLYPH_ORDER})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {"familyName": "GidTest", "styleName": "Regular", "psName": "GidTest"}
    )
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = list(subtables)
    fb.font["cmap"] = cmap
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


def _make_font(
    ttf_bytes: bytes,
    *,
    symbolic: bool,
    encoding: object = None,
    differences: dict[int, str] | None = None,
) -> PDTrueTypeFont:
    """Construct a :class:`PDTrueTypeFont` whose /FontFile2 carries
    ``ttf_bytes``. ``encoding`` is a /Encoding name string (e.g.
    ``"WinAnsiEncoding"``) or ``None``; ``differences`` builds a
    /Encoding dictionary with a /Differences array overlaid on
    ``encoding`` (used as the base)."""
    font_dict = COSDictionary()
    font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "GidTest")
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), 0)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), 255)
    widths = COSArray()
    for _ in range(256):
        widths.add(COSFloat(600.0))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)

    if differences is not None:
        enc_dict = COSDictionary()
        enc_dict.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding")
        )
        if isinstance(encoding, str):
            enc_dict.set_name(COSName.get_pdf_name("BaseEncoding"), encoding)
        # Build a /Differences array: int, name, int, name, ...
        diff_arr = COSArray()
        from pypdfbox.cos import COSInteger  # noqa: PLC0415

        for code in sorted(differences):
            diff_arr.add(COSInteger.get(code))
            diff_arr.add(COSName.get_pdf_name(differences[code]))
        enc_dict.set_item(COSName.get_pdf_name("Differences"), diff_arr)
        font_dict.set_item(COSName.get_pdf_name("Encoding"), enc_dict)
    elif isinstance(encoding, str):
        font_dict.set_name(COSName.get_pdf_name("Encoding"), encoding)

    descriptor = PDFontDescriptor()
    descriptor.set_font_name("GidTest")
    descriptor.set_flags(FLAG_SYMBOLIC if symbolic else FLAG_NON_SYMBOLIC)
    bbox = COSArray()
    for v in (0.0, -200.0, 800.0, 800.0):
        bbox.add(COSFloat(v))
    descriptor.set_font_b_box(bbox)
    cos = descriptor.get_cos_object()
    cos.set_int(COSName.get_pdf_name("Ascent"), 800)
    cos.set_int(COSName.get_pdf_name("Descent"), -200)
    cos.set_int(COSName.get_pdf_name("CapHeight"), 700)
    cos.set_int(COSName.get_pdf_name("StemV"), 80)
    cos.set_int(COSName.get_pdf_name("ItalicAngle"), 0)
    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)
    descriptor.set_font_file2(font_file2)
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDTrueTypeFont(font_dict)


# ---------------------------------------------------------------------------
# cmap fixtures (module-level so they're built once)
# ---------------------------------------------------------------------------

# Non-symbolic: a (3,1) Win-Unicode cmap. WinAnsi 'A'(0x41)->U+0041,
# 'B'(0x42)->U+0042, 'Euro'(0x80)->U+20AC, 'bullet'(0x95)->U+2022.
_WIN_UNICODE = _synth_ttf(
    [_subtable(4, 3, 1, {0x0041: "g1", 0x0042: "g2", 0x20AC: "g3", 0x2022: "g4"})]
)

# Non-symbolic with ONLY a (1,0) Mac-Roman cmap. Mac-Roman code for 'A'
# is 0x41, 'B' 0x42, 'bullet' is 0xA5. The mapping is keyed by Mac code.
_MAC_ROMAN_ONLY = _synth_ttf(
    [_subtable(0, 1, 0, {0x41: "g1", 0x42: "g2", 0xA5: "g4"})]
)

# Symbolic: ONLY a (3,0) Win-Symbol cmap keyed at 0xF000+code.
_WIN_SYMBOL_F000 = _synth_ttf(
    [_subtable(4, 3, 0, {0xF041: "g1", 0xF042: "g2", 0xF043: "g3"})]
)

# Symbolic: ONLY a (3,0) Win-Symbol cmap keyed at the RAW code.
_WIN_SYMBOL_RAW = _synth_ttf(
    [_subtable(4, 3, 0, {0x41: "g1", 0x42: "g2", 0x43: "g3"})]
)

# Symbolic: ONLY a (3,0) Win-Symbol cmap keyed at 0xF100+code (F1xx path).
_WIN_SYMBOL_F100 = _synth_ttf([_subtable(4, 3, 0, {0xF141: "g5", 0xF142: "g6"})])

# Symbolic: (3,0) and (1,0) — precedence pin. (3,0) keyed at 0xF0xx maps
# 0x41->g1, 0x42->g2; (1,0) maps raw 0x41->g3, 0x42->g4, 0x43->g5.
_SYMBOL_PLUS_MAC = _synth_ttf(
    [
        _subtable(4, 3, 0, {0xF041: "g1", 0xF042: "g2"}),
        _subtable(0, 1, 0, {0x41: "g3", 0x42: "g4", 0x43: "g5"}),
    ]
)

# No cmap subtables at all.
_NO_CMAP = _synth_ttf([])


def _synth_named_ttf(glyph_names: list[str], subtables: list) -> bytes:
    """Like :func:`_synth_ttf` but with an arbitrary glyph order so the
    ``post`` table carries real glyph names (e.g. ``A``) — needed to
    exercise the ``ttf.name_to_gid(name)`` last resort."""
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyph_names)
    fb.setupCharacterMap({})
    pens: dict = {}
    for i, name in enumerate(glyph_names):
        pen = TTGlyphPen(None)
        s = i * 10
        pen.moveTo((50 + s, 0))
        pen.lineTo((50 + s, 700))
        pen.lineTo((550 + s, 700))
        pen.closePath()
        pens[name] = pen.glyph()
    fb.setupGlyf(pens)
    fb.setupHorizontalMetrics({n: (600, 50) for n in glyph_names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {"familyName": "NamedTest", "styleName": "Regular", "psName": "NamedTest"}
    )
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = list(subtables)
    fb.font["cmap"] = cmap
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


# No cmap subtables, but glyphs named 'A' (GID 1) and 'B' (GID 2) so the
# post-table name_to_gid last resort can resolve them.
_NO_CMAP_NAMED = _synth_named_ttf([".notdef", "A", "B"], [])

# Symbolic with a (3,1) Win-Unicode cmap and a WinAnsi /Encoding — the
# branch where the active encoding routes the lookup through the glyph
# name's unicode rather than the raw code. Euro(0x80)->U+20AC->g3.
_WIN_UNICODE_FOR_SYMBOLIC = _synth_ttf(
    [_subtable(4, 3, 1, {0x0041: "g1", 0x20AC: "g3", 0x2022: "g4"})]
)


# ---------------------------------------------------------------------------
# non-symbolic: code -> name -> unicode -> (3,1) cmap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # 'A' -> U+0041 -> g1
        (0x42, 2),  # 'B' -> U+0042 -> g2
        (0x80, 3),  # WinAnsi Euro -> U+20AC -> g3
        (0x95, 4),  # WinAnsi bullet -> U+2022 -> g4
        (0x01, 0),  # control code, .notdef name -> 0
        (0x7F, 4),  # WinAnsi 0x7F -> 'bullet' -> U+2022 -> g4
    ],
    ids=["A", "B", "euro", "bullet", "ctrl01", "del7F"],
)
def test_nonsymbolic_winansi_unicode_path(code: int, expected: int) -> None:
    font = _make_font(_WIN_UNICODE, symbolic=False, encoding="WinAnsiEncoding")
    assert font.code_to_gid(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # StandardEncoding 'A' -> U+0041 -> g1
        (0x42, 2),  # 'B' -> g2
        (0x80, 0),  # StandardEncoding has no 0x80 glyph -> 0
    ],
    ids=["A", "B", "high80"],
)
def test_nonsymbolic_standard_encoding_default(code: int, expected: int) -> None:
    # No /Encoding entry on a non-symbolic embedded TTF -> StandardEncoding.
    font = _make_font(_WIN_UNICODE, symbolic=False, encoding=None)
    assert font.code_to_gid(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # 'A' -> mac code 0x41 -> g1
        (0x42, 2),  # 'B' -> mac code 0x42 -> g2
        (0x95, 4),  # WinAnsi bullet -> name 'bullet' -> mac 0xA5 -> g4
        (0x80, 0),  # Euro: MacOSRoman has no 'Euro' -> 0
    ],
    ids=["A", "B", "bullet", "euro"],
)
def test_nonsymbolic_mac_roman_path(code: int, expected: int) -> None:
    # Non-symbolic font whose only cmap is (1,0); the unicode (3,1) path is
    # absent, so resolution drops to the Mac-Roman branch via the glyph
    # name's MacOSRoman code.
    font = _make_font(_MAC_ROMAN_ONLY, symbolic=False, encoding="WinAnsiEncoding")
    assert font.code_to_gid(code) == expected


def test_nonsymbolic_post_table_fallback() -> None:
    # A (3,1) cmap that does NOT carry U+0041, plus a /Differences that
    # maps a code to a glyph the post table names. With no cmap hit, the
    # last resort is ttf.name_to_gid(name).
    ttf = _synth_ttf([_subtable(4, 3, 1, {0x2022: "g4"})])
    font = _make_font(
        ttf,
        symbolic=False,
        encoding="WinAnsiEncoding",
        differences={0x60: "g5"},  # map code 0x60 directly to glyph name "g5"
    )
    # "g5" has no AGL unicode and isn't in the cmap, so it falls to the
    # post-table name_to_gid("g5") -> GID 5.
    assert font.code_to_gid(0x60) == 5


# ---------------------------------------------------------------------------
# non-symbolic: /Differences feeds the unicode lookup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "name", "expected"),
    [
        (0x41, "Euro", 3),  # override 0x41 to 'Euro' -> U+20AC -> g3
        (0x42, "bullet", 4),  # override 0x42 to 'bullet' -> U+2022 -> g4
        (0x43, "A", 1),  # override 0x43 to 'A' -> U+0041 -> g1
        (0x44, "space", 0),  # 'space' -> U+0020, not in cmap -> 0
    ],
    ids=["euro", "bullet", "A", "space"],
)
def test_nonsymbolic_differences_unicode(
    code: int, name: str, expected: int
) -> None:
    font = _make_font(
        _WIN_UNICODE,
        symbolic=False,
        encoding="WinAnsiEncoding",
        differences={code: name},
    )
    assert font.code_to_gid(code) == expected


# ---------------------------------------------------------------------------
# symbolic: (3,0) Win-Symbol 0xF000 / raw / 0xF100 cascade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # raw miss, 0xF041 hit -> g1
        (0x42, 2),  # 0xF042 -> g2
        (0x43, 3),  # 0xF043 -> g3
        (0x44, 0),  # nothing -> 0
        (0x01, 0),  # low code, nothing -> 0
    ],
    ids=["A", "B", "C", "D", "low01"],
)
def test_symbolic_win_symbol_f000(code: int, expected: int) -> None:
    font = _make_font(_WIN_SYMBOL_F000, symbolic=True, encoding=None)
    assert font.code_to_gid(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # raw 0x41 hit directly -> g1
        (0x42, 2),
        (0x43, 3),
        (0x44, 0),
    ],
    ids=["A", "B", "C", "D"],
)
def test_symbolic_win_symbol_raw(code: int, expected: int) -> None:
    font = _make_font(_WIN_SYMBOL_RAW, symbolic=True, encoding=None)
    assert font.code_to_gid(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 5),  # raw + 0xF000 miss, 0xF141 hit -> g5
        (0x42, 6),  # 0xF142 -> g6
        (0x43, 0),
    ],
    ids=["A", "B", "C"],
)
def test_symbolic_win_symbol_f100(code: int, expected: int) -> None:
    font = _make_font(_WIN_SYMBOL_F100, symbolic=True, encoding=None)
    assert font.code_to_gid(code) == expected


# ---------------------------------------------------------------------------
# symbolic: (3,0) before (1,0) precedence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # in both; (3,0) 0xF041 wins -> g1
        (0x42, 2),  # in both; (3,0) 0xF042 wins -> g2
        (0x43, 5),  # only in (1,0) raw -> g5 (Mac fallthrough)
        (0x44, 0),  # in neither -> 0
    ],
    ids=["both_A", "both_B", "mac_only_C", "none_D"],
)
def test_symbolic_symbol_before_mac(code: int, expected: int) -> None:
    font = _make_font(_SYMBOL_PLUS_MAC, symbolic=True, encoding=None)
    assert font.code_to_gid(code) == expected


# ---------------------------------------------------------------------------
# symbolic: (3,1) present + WinAnsi /Encoding routes through the glyph name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # WinAnsi 'A' -> U+0041 -> g1
        (0x80, 3),  # WinAnsi Euro -> U+20AC -> g3 (NOT the raw 0x80!)
        (0x95, 4),  # WinAnsi bullet -> U+2022 -> g4
    ],
    ids=["A", "euro", "bullet"],
)
def test_symbolic_winansi_name_routes_unicode(code: int, expected: int) -> None:
    # Symbolic flag set, but a WinAnsi /Encoding present and a (3,1) cmap:
    # the lookup goes through the glyph name's unicode, not the raw code.
    font = _make_font(
        _WIN_UNICODE_FOR_SYMBOLIC, symbolic=True, encoding="WinAnsiEncoding"
    )
    assert font.code_to_gid(code) == expected


def test_symbolic_winansi_first_call_euro() -> None:
    """Regression for the wave-1576 fix: ``code_to_gid`` as the FIRST
    encoding-consuming call on a symbolic WinAnsi font must still route
    0x80 through the glyph name (Euro -> U+20AC -> g3), not the raw code
    (which would miss -> 0)."""
    font = _make_font(
        _WIN_UNICODE_FOR_SYMBOLIC, symbolic=True, encoding="WinAnsiEncoding"
    )
    # Do NOT touch get_encoding_typed() first.
    assert font.code_to_gid(0x80) == 3


def test_symbolic_winansi_first_call_matches_resolved() -> None:
    """The first-call result must equal the post-resolution result for
    every code 0..255 — the lazy encoding cache must not change the GID."""
    fresh = _make_font(
        _WIN_UNICODE_FOR_SYMBOLIC, symbolic=True, encoding="WinAnsiEncoding"
    )
    primed = _make_font(
        _WIN_UNICODE_FOR_SYMBOLIC, symbolic=True, encoding="WinAnsiEncoding"
    )
    primed.get_encoding_typed()
    for code in range(256):
        assert fresh.code_to_gid(code) == primed.code_to_gid(code), code


# ---------------------------------------------------------------------------
# symbolic without a recognised encoding: (3,1) by raw code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x41, 1),  # no WinAnsi/MacRoman encoding -> raw code into (3,1) -> g1
        (0x20AC, 3),  # raw U+20AC into (3,1) -> g3 (code > 0xFF still works)
        (0x99, 0),  # raw, not in cmap -> 0
    ],
    ids=["A", "rawEuro", "miss99"],
)
def test_symbolic_no_encoding_raw_into_unicode(
    code: int, expected: int
) -> None:
    # Symbolic, no /Encoding -> the (3,1) else branch uses the raw code.
    font = _make_font(_WIN_UNICODE_FOR_SYMBOLIC, symbolic=True, encoding=None)
    assert font.code_to_gid(code) == expected


# ---------------------------------------------------------------------------
# no glyph anywhere -> GID 0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [0x00, 0x41, 0x80, 0xFF], ids=lambda c: hex(c))
def test_no_cmap_symbolic_all_notdef(code: int) -> None:
    font = _make_font(_NO_CMAP, symbolic=True, encoding=None)
    assert font.code_to_gid(code) == 0


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x00, 0),  # .notdef name -> 0
        (0x41, 1),  # 'A' -> post name_to_gid -> g1 (post-table last resort)
        (0x80, 0),  # 'Euro' name not in post table -> 0
        (0xFF, 0),  # 'ydieresis' name not in post table -> 0
    ],
    ids=["nul", "A", "euro", "yd"],
)
def test_no_cmap_nonsymbolic_post_fallback(code: int, expected: int) -> None:
    # No cmap subtables at all + a glyph-name encoding. Upstream's
    # non-symbolic last resort is ttf.name_to_gid(name), so glyph names
    # present in the post table ('A' here) still resolve.
    font = _make_font(_NO_CMAP_NAMED, symbolic=False, encoding="WinAnsiEncoding")
    assert font.code_to_gid(code) == expected


# ---------------------------------------------------------------------------
# public surface sanity: has_glyph / get_gid_to_code agree with code_to_gid
# ---------------------------------------------------------------------------


def test_has_glyph_int_agrees_with_code_to_gid() -> None:
    font = _make_font(_WIN_SYMBOL_F000, symbolic=True, encoding=None)
    for code in (0x41, 0x42, 0x43, 0x44, 0x01):
        assert font.has_glyph(code) == (font.code_to_gid(code) != 0)


def test_gid_to_code_first_wins() -> None:
    font = _make_font(_WIN_SYMBOL_RAW, symbolic=True, encoding=None)
    mapping = font.get_gid_to_code()
    # g1..g3 resolved from codes 0x41..0x43; GID 0 keyed by the first code
    # that resolves to .notdef (code 0).
    assert mapping[1] == 0x41
    assert mapping[2] == 0x42
    assert mapping[3] == 0x43
    assert mapping[0] == 0  # first code resolving to .notdef
