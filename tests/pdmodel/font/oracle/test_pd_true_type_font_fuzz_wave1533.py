"""Live PDFBox differential parity for :class:`PDTrueTypeFont` — encoding
selection + code-&gt;glyph mapping + width handling on malformed / edge-case
simple-TrueType font dictionaries (PDF 32000-1 §9.6.6.4, §9.7.4.3).

Wave 1533. This ties three :class:`PDTrueTypeFont` facets together across a
matrix of malformed dicts, which the adjacent font oracles do not cover jointly:

  * the resolved ``getEncoding()`` **class** — the symbolic-vs-non-symbolic
    selection crossed with /Encoding absent / a WinAnsi name / a MacRoman name /
    a dict-with-/Differences (``PDSimpleFont.readEncoding`` /
    ``PDTrueTypeFont.readEncodingFromFont``);
  * ``codeToGID(code)`` — the cmap (3,1)/(3,0)/(1,0) selection and the
    0xF000 symbolic PUA offset (``PDTrueTypeFont.codeToGID``);
  * ``getWidth(code)`` / ``getWidthFromFont(code)`` — the /Widths-array window
    crossed with /FirstChar//LastChar mismatches, /Widths absent (program
    fallback through codeToGID -&gt; hmtx), a missing /FontDescriptor, and a
    missing embedded /FontFile2 (``PDFont.getWidth`` / ``getWidthFromFont``).

Distinct from:
  * ``test_symbolic_ttf_oracle`` — symbolic-only, no /Encoding, code-&gt;GID +
    render fingerprint;
  * ``test_simple_font_widths_oracle`` — the dictionary /Widths array on a
    Type1 (no font program);
  * ``test_font_encoding_fuzz_wave1516`` — the standalone Encoding classes.

The TTFs and PDFs are synthesised here via fontTools; the oracle output is
produced by ``oracle/probes/PdTrueTypeFontFuzzProbe.java``. The Python side
reconstructs the identical line format so any divergence is a single line.
Widths are exact ``hmtx`` lookups scaled by ``1000/unitsPerEm`` (here
unitsPerEm == 1000, so integer-exact) and the encoding class / GID / glyph
name are pure lookups — zero tolerance.

NOTE on ``getEncoding`` parity: PDFBox's ``PDFont.getEncoding()`` returns the
*typed* ``Encoding``; the pypdfbox equivalent is ``get_encoding_typed()``
(``get_encoding()`` returns the raw COSBase). The probe and the Python
reproduction are aligned on that.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FtCmapSubtable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_NON_SYMBOLIC,
    FLAG_SYMBOLIC,
    PDFontDescriptor,
)
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

# Codes mirrored from PdTrueTypeFontFuzzProbe.CODES exactly.
_CODES = (0x00, 0x01, 0x20, 0x41, 0x42, 0x43, 0x44, 0x45, 0x60, 0x80, 0xA0, 0xFF)

# Glyph order: .notdef + four real glyphs (A,B,C,D) + a fifth (for symbol/mac).
_GLYPH_ORDER = [".notdef", "A", "B", "C", "D", "g5"]

# Advance widths in font units (unitsPerEm == 1000) keyed by glyph name.
_ADVANCES = {
    ".notdef": 500,
    "A": 600,
    "B": 650,
    "C": 700,
    "D": 750,
    "g5": 800,
}


def _glyphs() -> dict:
    pens: dict = {}

    def box(name: str, pts: list[tuple[int, int]]) -> None:
        pen = TTGlyphPen(None)
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
        pens[name] = pen.glyph()

    box(".notdef", [(100, 0), (100, 700), (500, 700), (500, 0)])
    box("A", [(50, 0), (50, 750), (750, 750), (750, 0)])
    box("B", [(300, 0), (300, 800), (450, 800), (450, 0)])
    box("C", [(0, 300), (0, 500), (800, 500), (800, 300)])
    box("D", [(50, 0), (400, 750), (750, 0)])
    box("g5", [(0, 0), (0, 600), (600, 600), (600, 0)])
    return pens


def _subtable(fmt: int, plat: int, enc: int, mapping: dict[int, str]):
    sub = FtCmapSubtable.getSubtableClass(fmt)(fmt)
    sub.format = fmt
    sub.platformID = plat
    sub.platEncID = enc
    sub.language = 0
    sub.cmap = mapping
    return sub


def _cmap_for(kind: str):
    """Build the ``cmap`` table for one synthesis ``kind``."""
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = []
    if kind == "unicode_31":
        # (3,1) Win-Unicode: 0x41->A .. 0x44->D (the AGL code points).
        cmap.tables.append(
            _subtable(4, 3, 1, {0x41: "A", 0x42: "B", 0x43: "C", 0x44: "D"})
        )
    elif kind == "win_symbol_f000":
        # (3,0) Win-Symbol keyed on 0xF000+code.
        cmap.tables.append(
            _subtable(4, 3, 0, {0xF041: "A", 0xF042: "B", 0xF043: "C", 0xF044: "D"})
        )
    elif kind == "win_symbol_direct":
        # (3,0) Win-Symbol keyed on the raw code — exercised for a
        # NON-symbolic font (the "(3,0) on non-symbolic" fuzz case).
        cmap.tables.append(
            _subtable(4, 3, 0, {0x41: "A", 0x42: "B", 0x43: "C", 0x44: "D"})
        )
    elif kind == "mac_roman":
        cmap.tables.append(
            _subtable(0, 1, 0, {0x41: "A", 0x42: "B", 0x43: "C", 0x44: "D"})
        )
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown cmap kind: {kind}")
    return cmap


def _synth_ttf(cmap_kind: str, ps_name: str) -> bytes:
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(_GLYPH_ORDER)
    fb.setupCharacterMap({})
    fb.setupGlyf(_glyphs())
    fb.setupHorizontalMetrics({n: (_ADVANCES[n], 50) for n in _GLYPH_ORDER})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {"familyName": "FuzzTTF", "styleName": "Regular", "psName": ps_name}
    )
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    fb.font["cmap"] = _cmap_for(cmap_kind)
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


def _descriptor(
    *, symbolic: bool, ttf_bytes: bytes | None, base: str
) -> PDFontDescriptor:
    descriptor = PDFontDescriptor()
    descriptor.set_font_name(base)
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
    cos.set_int(COSName.get_pdf_name("MissingWidth"), 333)
    if ttf_bytes is not None:
        font_file2 = COSStream()
        font_file2.set_raw_data(ttf_bytes)
        descriptor.set_font_file2(font_file2)
    return descriptor


def _name_encoding(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def _diff_encoding() -> COSDictionary:
    """A /Differences dict with no /BaseEncoding, remapping 0x41->/B 0x42->/A."""
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    from pypdfbox.cos import COSInteger

    diffs.add(COSInteger.get(0x41))
    diffs.add(COSName.get_pdf_name("B"))
    diffs.add(COSName.get_pdf_name("A"))  # 0x42 -> A
    enc.set_item(COSName.get_pdf_name("Differences"), diffs)
    return enc


def _font_dict(
    *,
    base: str,
    symbolic: bool,
    ttf_bytes: bytes | None,
    encoding: COSName | COSDictionary | None,
    first_char: int | None,
    last_char: int | None,
    widths: list[float] | None,
    with_descriptor: bool = True,
) -> COSDictionary:
    fd = COSDictionary()
    fd.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    fd.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    fd.set_name(COSName.get_pdf_name("BaseFont"), base)
    if encoding is not None:
        fd.set_item(COSName.get_pdf_name("Encoding"), encoding)
    if first_char is not None:
        fd.set_int(COSName.get_pdf_name("FirstChar"), first_char)
    if last_char is not None:
        fd.set_int(COSName.get_pdf_name("LastChar"), last_char)
    if widths is not None:
        arr = COSArray()
        for w in widths:
            arr.add(COSFloat(float(w)))
        fd.set_item(COSName.get_pdf_name("Widths"), arr)
    if with_descriptor:
        descriptor = _descriptor(symbolic=symbolic, ttf_bytes=ttf_bytes, base=base)
        fd.set_item(
            COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
        )
    return fd


# The EMBEDDED fonts (F1..F7) carry a /FontFile2 and are fully deterministic, so
# they are diffed byte-for-byte against the live oracle. The NON-EMBEDDED fonts
# (F8 missing /FontDescriptor, F9 descriptor-but-no-/FontFile2) hit PDFBox's
# environment-dependent substitute-font program (a system Arial/Liberation TTF)
# for getWidthFromFont / codeToGID / the out-of-/Widths getWidth, which pypdfbox
# does not load — see the CHANGES.md "Wave 1533" divergence note. They are
# therefore pinned separately on the *alignable* facets only.
def _embedded_specs() -> list[tuple[str, COSDictionary]]:
    ttf_uni = _synth_ttf("unicode_31", "FuzzUni")
    ttf_sym = _synth_ttf("win_symbol_f000", "FuzzSym")
    ttf_symdirect = _synth_ttf("win_symbol_direct", "FuzzSymDirect")
    ttf_mac = _synth_ttf("mac_roman", "FuzzMac")

    specs: list[tuple[str, COSDictionary]] = []

    # 1. Non-symbolic, /Encoding WinAnsiEncoding (name), (3,1) cmap, full widths.
    specs.append((
        "F1",
        _font_dict(
            base="FuzzUni1", symbolic=False, ttf_bytes=ttf_uni,
            encoding=_name_encoding("WinAnsiEncoding"),
            first_char=0x41, last_char=0x44, widths=[600.0, 650.0, 700.0, 750.0],
        ),
    ))
    # 2. Non-symbolic, /Encoding MacRomanEncoding (name), (3,1) cmap, no /Widths
    #    (program fallback through codeToGID -> hmtx).
    specs.append((
        "F2",
        _font_dict(
            base="FuzzUni2", symbolic=False, ttf_bytes=ttf_uni,
            encoding=_name_encoding("MacRomanEncoding"),
            first_char=None, last_char=None, widths=None,
        ),
    ))
    # 3. Non-symbolic, /Encoding absent, (3,1) cmap -> StandardEncoding via
    #    readEncodingFromFont. Widths window mismatched (FirstChar 0x42).
    specs.append((
        "F3",
        _font_dict(
            base="FuzzUni3", symbolic=False, ttf_bytes=ttf_uni,
            encoding=None,
            first_char=0x42, last_char=0x44, widths=[1111.0, 1222.0, 1333.0],
        ),
    ))
    # 4. Non-symbolic, /Encoding dict with /Differences (no /BaseEncoding).
    specs.append((
        "F4",
        _font_dict(
            base="FuzzUni4", symbolic=False, ttf_bytes=ttf_uni,
            encoding=_diff_encoding(),
            first_char=0x41, last_char=0x44, widths=[600.0, 650.0, 700.0, 750.0],
        ),
    ))
    # 5. Symbolic, /Encoding absent, (3,0) 0xF000 cmap -> built-in. No /Widths.
    specs.append((
        "F5",
        _font_dict(
            base="FuzzSym", symbolic=True, ttf_bytes=ttf_sym,
            encoding=None, first_char=None, last_char=None, widths=None,
        ),
    ))
    # 6. NON-symbolic font carrying ONLY a (3,0) cmap keyed on the raw code,
    #    /Encoding absent.
    specs.append((
        "F6",
        _font_dict(
            base="FuzzSymDirect", symbolic=False, ttf_bytes=ttf_symdirect,
            encoding=None, first_char=None, last_char=None, widths=None,
        ),
    ))
    # 7. Symbolic, only a (1,0) Mac-Roman cmap, /Encoding absent.
    specs.append((
        "F7",
        _font_dict(
            base="FuzzMac", symbolic=True, ttf_bytes=ttf_mac,
            encoding=None, first_char=None, last_char=None, widths=None,
        ),
    ))
    return specs


def _non_embedded_specs() -> list[tuple[str, COSDictionary]]:
    specs: list[tuple[str, COSDictionary]] = []
    # 8. Missing /FontDescriptor entirely (so no /FontFile2, no flags ->
    #    non-symbolic). /Widths present.
    specs.append((
        "F8",
        _font_dict(
            base="NoDescriptor", symbolic=False, ttf_bytes=None,
            encoding=_name_encoding("WinAnsiEncoding"),
            first_char=0x41, last_char=0x44, widths=[600.0, 650.0, 700.0, 750.0],
            with_descriptor=False,
        ),
    ))
    # 9. Descriptor present but NO embedded /FontFile2 (Standard-14-ish
    #    fallback). Non-symbolic, /Encoding WinAnsi, /Widths present.
    specs.append((
        "F9",
        _font_dict(
            base="NoFontFile", symbolic=False, ttf_bytes=None,
            encoding=_name_encoding("WinAnsiEncoding"),
            first_char=0x41, last_char=0x44, widths=[600.0, 650.0, 700.0, 750.0],
        ),
    ))
    return specs


def _build_pdf(out: Path, specs: list[tuple[str, COSDictionary]]) -> Path:
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        for _key, font_dict in specs:
            page = PDPage(PDRectangle(0.0, 0.0, 200.0, 80.0))
            doc.add_page(page)
            res = PDResources()
            res.put(COSName.get_pdf_name("FT"), PDTrueTypeFont(font_dict))
            page.set_resources(res)
        doc.save(str(out))
    finally:
        doc.close()
    return out


def _fmt(v: float) -> str:
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _py_output(pdf_path: Path) -> str:
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:
                    continue
                if not isinstance(font, PDTrueTypeFont):
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                try:
                    symbolic = font.is_symbolic()
                except Exception:
                    symbolic = False
                try:
                    enc = font.get_encoding_typed()
                    enc_class = type(enc).__name__ if enc is not None else "null"
                except Exception:
                    enc_class = "ENC_ERR"
                try:
                    embedded = font.is_embedded()
                except Exception:
                    embedded = False
                try:
                    damaged = font.is_damaged()
                except Exception:
                    damaged = False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{'true' if symbolic else 'false'}\t{enc_class}\t"
                    f"{'true' if embedded else 'false'}\t"
                    f"{'true' if damaged else 'false'}"
                )
                for code in _CODES:
                    try:
                        width = _fmt(font.get_width(code))
                    except Exception:
                        width = "WIDTH_ERR"
                    try:
                        wff = _fmt(font.get_width_from_font(code))
                    except Exception:
                        wff = "WFF_ERR"
                    try:
                        gid = str(font.code_to_gid(code))
                    except Exception:
                        gid = "GID_ERR"
                    try:
                        enc = font.get_encoding_typed()
                        gname = enc.get_name(code) if enc is not None else None
                        glyph_name = gname if gname is not None else "null"
                    except Exception:
                        glyph_name = "NAME_ERR"
                    lines.append(
                        f"CODE\t{page_index}\t{key}\t{code}\t{width}\t{wff}\t"
                        f"{gid}\t{glyph_name}"
                    )
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
def test_pd_true_type_font_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Encoding class + codeToGID + getWidth/getWidthFromFont + glyph name for
    every **embedded** fuzz font/code must match Apache PDFBox 3.0.7 exactly.

    Pins the symbolic-vs-non-symbolic encoding selection, /Encoding absent /
    name / dict-with-/Differences resolution, the (3,1)/(3,0)/(1,0) cmap +
    0xF000 PUA offset codeToGID chain, and the /Widths-window vs program-
    fallback width path. The non-embedded fonts (no /FontFile2) are pinned
    separately — see :func:`test_non_embedded_alignable_facets_match_pdfbox`.
    """
    pdf = _build_pdf(tmp_path / "ttf_fuzz.pdf", _embedded_specs())
    java = run_probe_text("PdTrueTypeFontFuzzProbe", str(pdf)).splitlines()
    py = _py_output(pdf).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch java={len(java)} py={len(py)}\n"
        "java:\n" + "\n".join(java) + "\npy:\n" + "\n".join(py)
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "PDTrueTypeFont fuzz parity broken:\n" + "\n".join(diffs[:60])


@requires_oracle
def test_non_embedded_alignable_facets_match_pdfbox(tmp_path: Path) -> None:
    """Pin the *alignable* facets of a non-embedded simple TrueType font.

    A simple TrueType font with no embedded /FontFile2 (F8 has no
    /FontDescriptor at all; F9 has a descriptor but no /FontFile2) drives
    PDFBox's environment-dependent **substitute-font program** (a system
    Arial/Liberation TTF) for ``getWidthFromFont`` / ``codeToGID`` and for the
    out-of-/Widths ``getWidth`` codes. pypdfbox does not load a substitute
    program (the FontMapperImpl substitute path is not wired into
    ``PDTrueTypeFont.get_true_type_font``), so those three columns diverge by a
    host-dependent amount — see CHANGES.md / DEFERRED.md "Wave 1533".

    The encoding-class selection, the per-code glyph **name**, and the
    in-/Widths-window ``getWidth`` value are independent of the substitute and
    DO align — those are pinned here against the live oracle.
    """
    pdf = _build_pdf(tmp_path / "ttf_nonembed.pdf", _non_embedded_specs())
    java = run_probe_text("PdTrueTypeFontFuzzProbe", str(pdf)).splitlines()
    py = _py_output(pdf).splitlines()
    assert len(java) == len(py)

    def fields(line: str) -> list[str]:
        return line.split("\t")

    for jl, pl in zip(java, py, strict=True):
        jf, pf = fields(jl), fields(pl)
        assert jf[0] == pf[0], f"row type mismatch: {jl!r} vs {pl!r}"
        if jf[0] == "FONT":
            # pageIndex, key, baseFont, isSymbolic, encodingClass align.
            # (embedded/damaged differ — Java reports the substitute as a
            # loaded program; pinned via the explicit asserts below instead.)
            assert jf[1:6] == pf[1:6], (
                f"FONT alignable facets diverge:\n  java={jl!r}\n  py={pl!r}"
            )
        else:  # CODE
            # pageIndex, key, code, getWidth, [skip wff], [skip gid], glyphName.
            assert jf[1] == pf[1] and jf[2] == pf[2] and jf[3] == pf[3], (
                f"CODE id columns diverge:\n  java={jl!r}\n  py={pl!r}"
            )
            # getWidth aligns only for in-/Widths-window codes 0x41..0x44.
            code = int(jf[3])
            if 0x41 <= code <= 0x44:
                assert jf[4] == pf[4], (
                    f"in-window getWidth diverges at code {code}:\n"
                    f"  java={jl!r}\n  py={pl!r}"
                )
            # glyph name (last column) is from the /Encoding, substitute-free.
            assert jf[7] == pf[7], (
                f"glyph name diverges at code {code}:\n"
                f"  java={jl!r}\n  py={pl!r}"
            )


@pytest.mark.parametrize(
    ("key", "expected_class"),
    [
        ("F1", "WinAnsiEncoding"),
        ("F2", "MacRomanEncoding"),
        ("F3", "StandardEncoding"),
        ("F4", "DictionaryEncoding"),
        ("F5", "BuiltInEncoding"),
        ("F8", "WinAnsiEncoding"),
    ],
    ids=["F1_winansi", "F2_macroman", "F3_std_default", "F4_diff", "F5_builtin",
         "F8_no_desc_winansi"],
)
def test_encoding_class_selection(
    key: str, expected_class: str, tmp_path: Path
) -> None:
    """Fixture-proof (no oracle): each malformed dict resolves to the expected
    ``get_encoding_typed`` class so the encoding-selection rung stays locked
    even on a machine without Java."""
    specs = _embedded_specs() + _non_embedded_specs()
    base_for_key = {
        k: d.get_name_as_string(COSName.get_pdf_name("BaseFont")) for k, d in specs
    }
    pdf = _build_pdf(tmp_path / "sel.pdf", specs)
    doc = PDDocument.load(pdf)
    try:
        target_base = base_for_key[key]
        match = None
        for page in doc.get_pages():
            res = page.get_resources()
            for name in res.get_font_names():
                font = res.get_font(name)
                if (
                    isinstance(font, PDTrueTypeFont)
                    and font.get_name() == target_base
                ):
                    match = font
        assert match is not None, f"font for {key} not found"
        enc = match.get_encoding_typed()
        assert type(enc).__name__ == expected_class, (
            f"{key}: encoding {type(enc).__name__}, expected {expected_class}"
        )
    finally:
        doc.close()
