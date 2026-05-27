"""Live PDFBox differential parity for **symbolic** simple-TrueType glyph
mapping without a (3,1) Unicode cmap (PDF 32000-1 §9.6.6.4).

Wave 1445. A symbolic TrueType simple font — descriptor ``/Flags`` bit 3
(symbolic) set, and (per the spec) typically *no* ``/Encoding`` entry — commonly
embeds only a ``(3,0)`` Windows-Symbol cmap or a ``(1,0)`` Mac-Roman cmap (or no
usable cmap at all). PDFBox's ``PDTrueTypeFont.codeToGID`` symbolic fallback
chain is, in strict order:

  1. ``(3,1)`` Win-Unicode — via the WinAnsi/MacRoman encoding glyph name when
     the active encoding is one of those, else the raw code — *when a (3,1)
     subtable is present*;
  2. ``(3,0)`` Win-Symbol — raw ``code``, then ``0xF000+code``, then
     ``0xF100+code``, then ``0xF200+code`` (only the F0xx family for the
     0..255 code range);
  3. ``(1,0)`` Mac-Roman — raw ``code``.

When none of those resolve, ``codeToGID`` returns ``0`` (``.notdef``). There is
**no** "the code *is* the glyph id" fallback inside ``codeToGID`` for an embedded
symbolic font: a symbolic font with no usable cmap maps every code to GID 0 and
renders ``.notdef`` (verified against the live oracle below — the ``no_cmap``
fixture returns GID 0 for every code in both engines).

This file synthesizes four controlled symbolic fonts via fontTools — each with
the symbolic flag set, **no** ``(3,1)`` Unicode cmap, and **no** ``/Encoding``
on the font dict — exercising every rung of the fallback chain:

  * ``win_symbol``      — only a ``(3,0)`` cmap keyed on ``0xF000+code``;
  * ``win_symbol_direct`` — only a ``(3,0)`` cmap keyed on the *raw* code;
  * ``mac_roman``       — only a ``(1,0)`` Mac-Roman cmap keyed on the raw code;
  * ``no_cmap``         — no cmap subtables at all (every code -> ``.notdef``);
  * ``both``            — both a ``(3,0)`` (``0xF0xx``) and a ``(1,0)`` cmap, so
                          the precedence ``(3,0) before (1,0)`` is pinned: a code
                          present in *both* must resolve through the symbol
                          subtable, and a code present only in the Mac subtable
                          must fall through to it.

Two layers of parity, both against Apache PDFBox 3.0.7:

  * **code -> GID** — ``PDTrueTypeFont.codeToGID(code)`` for codes 0..255 must
    match the ``SymbolicTtfProbe`` ``gid`` mode line for line. Pure integer
    arithmetic over the cmap subtables — zero tolerance.
  * **render** — the 16x16 luminance fingerprint of the page (``SymbolicTtfProbe``
    ``render`` mode, same cell mapping as ``RenderProbe``) must agree within the
    project's calibrated ``MAD < 6`` / ``MAXDIFF < 60`` gate, proving the
    resolved glyphs paint where PDFBox paints them.

Result: pypdfbox already matches PDFBox on the full chain (code->GID exact on all
five fonts incl. the precedence case; render MAD ~0.06). No production fix was
needed; this test pins the parity so a future regression in the symbolic
fallback order, the missing ``0xF000`` step, or a spurious code-as-GID fallback
fails loudly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FtCmapSubtable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_descriptor import FLAG_SYMBOLIC, PDFontDescriptor
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Codes shown on the page / asserted in the GID parity. 0x41..0x44 exercise the
# mapped + unmapped glyphs; 0x01/0x02 exercise low codes that never resolve.
_CODES = (0x01, 0x02, 0x41, 0x42, 0x43, 0x44)

_GLYPH_ORDER = [".notdef", "g1", "g2", "g3", "g4"]


# ---------------------------------------------------------------------------
# font synthesis — five symbolic TTFs with controlled cmaps
# ---------------------------------------------------------------------------


def _glyphs() -> dict:
    """Five distinct filled-box glyphs, one per GID, so a wrong GID renders a
    visibly different shape (and a wrong-GID render diverges in the grid)."""
    pens: dict = {}

    def box(name: str, pts: list[tuple[int, int]]) -> None:
        pen = TTGlyphPen(None)
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
        pens[name] = pen.glyph()

    box(".notdef", [(100, 0), (100, 700), (500, 700), (500, 0)])
    box("g1", [(50, 0), (50, 750), (750, 750), (750, 0)])
    box("g2", [(300, 0), (300, 800), (450, 800), (450, 0)])
    box("g3", [(0, 300), (0, 500), (800, 500), (800, 300)])
    box("g4", [(50, 0), (400, 750), (750, 0)])
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
    """Build the ``cmap`` table for one synthesis ``kind``. Never includes a
    ``(3,1)`` Win-Unicode subtable — that is the whole point of the fixture."""
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = []
    if kind == "win_symbol":
        cmap.tables.append(_subtable(4, 3, 0, {0xF041: "g1", 0xF042: "g2", 0xF043: "g3"}))
    elif kind == "win_symbol_direct":
        cmap.tables.append(_subtable(4, 3, 0, {0x41: "g1", 0x42: "g2", 0x43: "g3"}))
    elif kind == "mac_roman":
        cmap.tables.append(_subtable(0, 1, 0, {0x41: "g1", 0x42: "g2", 0x43: "g3"}))
    elif kind == "no_cmap":
        pass  # empty cmap table — no usable subtable
    elif kind == "both":
        # (3,0) keyed on 0xF0xx maps 0x41->g1, 0x42->g2; (1,0) maps the raw
        # 0x41->g3, 0x42->g4, 0x43->g4. Precedence: (3,0) wins for 0x41/0x42,
        # 0x43 (absent from symbol) falls through to mac (g4 / GID 4).
        cmap.tables.append(_subtable(4, 3, 0, {0xF041: "g1", 0xF042: "g2"}))
        cmap.tables.append(_subtable(0, 1, 0, {0x41: "g3", 0x42: "g4", 0x43: "g4"}))
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown kind: {kind}")
    return cmap


def _synth_ttf(kind: str) -> bytes:
    """Return the bytes of a TTF with five glyphs and the ``kind`` cmap."""
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(_GLYPH_ORDER)
    fb.setupCharacterMap({})
    fb.setupGlyf(_glyphs())
    fb.setupHorizontalMetrics({n: (900, 50) for n in _GLYPH_ORDER})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {"familyName": "SymTest", "styleName": "Regular", "psName": "SymTest-" + kind}
    )
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    fb.font["cmap"] = _cmap_for(kind)
    import io

    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


def _build_pdf(out: Path, ttf_bytes: bytes) -> Path:
    """Embed ``ttf_bytes`` as a *symbolic* simple TrueType font (descriptor
    /Flags symbolic, **no** /Encoding on the font dict) and show ``_CODES``."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 200.0, 80.0))
        doc.add_page(page)

        font_dict = COSDictionary()
        font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
        font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
        font_dict.set_name(COSName.get_pdf_name("BaseFont"), "SymTest")
        font_dict.set_int(COSName.get_pdf_name("FirstChar"), 0)
        font_dict.set_int(COSName.get_pdf_name("LastChar"), 255)
        widths = COSArray()
        for _ in range(256):
            widths.add(COSFloat(900.0))
        font_dict.set_item(COSName.get_pdf_name("Widths"), widths)

        descriptor = PDFontDescriptor()
        descriptor.set_font_name("SymTest")
        descriptor.set_flags(FLAG_SYMBOLIC)
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

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), PDTrueTypeFont(font_dict))
        page.set_resources(res)

        hexcodes = "".join(f"{c:02X}" for c in _CODES)
        cs = COSStream()
        cs.set_data(b"BT\n/F1 24 Tf\n4 20 Td\n<%s> Tj\nET\n" % hexcodes.encode("ascii"))
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------------------
# pypdfbox reproductions of the probe output
# ---------------------------------------------------------------------------


def _py_gid(pdf_path: Path) -> str:
    """Reconstruct SymbolicTtfProbe ``gid`` mode output, line for line."""
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
                descriptor = font.get_font_descriptor()
                symbolic = bool(descriptor.is_symbolic()) if descriptor else False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{'true' if symbolic else 'false'}"
                )
                for code in range(256):
                    try:
                        gid = font.code_to_gid(code)
                    except Exception:
                        gid = -1
                    lines.append(f"CGID\t{code}\t{gid}")
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


def _grid_from_image(img) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _py_render(pdf_path: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(pdf_path) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


def _oracle_render(pdf_path: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("SymbolicTtfProbe", "render", str(pdf_path), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


_KINDS = ["win_symbol", "win_symbol_direct", "mac_roman", "no_cmap", "both"]

# Expected GID for each probed code, per synthesis kind. Pinned from the live
# oracle (PDFBox 3.0.7) and matched by pypdfbox; kept here so the fixture-proof
# test can assert the fallback chain hit the rung we intended even when the
# oracle is unavailable.
_EXPECTED_GID = {
    "win_symbol": {0x41: 1, 0x42: 2, 0x43: 3, 0x44: 0, 0x01: 0, 0x02: 0},
    "win_symbol_direct": {0x41: 1, 0x42: 2, 0x43: 3, 0x44: 0, 0x01: 0, 0x02: 0},
    "mac_roman": {0x41: 1, 0x42: 2, 0x43: 3, 0x44: 0, 0x01: 0, 0x02: 0},
    "no_cmap": {0x41: 0, 0x42: 0, 0x43: 0, 0x44: 0, 0x01: 0, 0x02: 0},
    # (3,0) wins 0x41/0x42; 0x43 absent from symbol falls to (1,0) -> g4 (GID 4).
    "both": {0x41: 1, 0x42: 2, 0x43: 4, 0x44: 0, 0x01: 0, 0x02: 0},
}


# ---------------------------------------------------------------------------
# fixture proof (no oracle needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
def test_fixture_is_symbolic_without_31_cmap(kind: str, tmp_path: Path) -> None:
    """Prove each fixture really is symbolic and carries no (3,1) Unicode cmap
    — if a future fontTools changed cmap synthesis so a (3,1) leaked in, the
    fallback chain under test would no longer be exercised."""
    from fontTools.ttLib import TTFont

    ttf_bytes = _synth_ttf(kind)
    font = TTFont(__import__("io").BytesIO(ttf_bytes))
    pairs = {(t.platformID, t.platEncID) for t in font["cmap"].tables}
    assert (3, 1) not in pairs, f"{kind}: unexpected (3,1) Unicode cmap present"
    assert (0, 3) not in pairs and (0, 4) not in pairs, (
        f"{kind}: a Unicode-platform cmap leaked in"
    )

    pdf = _build_pdf(tmp_path / f"{kind}.pdf", ttf_bytes)
    doc = PDDocument.load(pdf)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        name = next(iter(res.get_font_names()))
        pdfont = res.get_font(name)
        assert isinstance(pdfont, PDTrueTypeFont)
        assert pdfont.get_font_descriptor().is_symbolic()
        # No /Encoding on the font dict.
        assert pdfont.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Encoding")
        ) is None
    finally:
        doc.close()


@pytest.mark.parametrize("kind", _KINDS)
def test_code_to_gid_hits_expected_fallback_rung(kind: str, tmp_path: Path) -> None:
    """Pin the fallback-chain result for each kind without the oracle so the
    rung (raw (3,0), 0xF000+code (3,0), (1,0) Mac, or GID-0 no-cmap) is locked
    even on a machine without Java."""
    pdf = _build_pdf(tmp_path / f"{kind}.pdf", _synth_ttf(kind))
    doc = PDDocument.load(pdf)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        font = res.get_font(next(iter(res.get_font_names())))
        assert isinstance(font, PDTrueTypeFont)
        for code, expected in _EXPECTED_GID[kind].items():
            assert font.code_to_gid(code) == expected, (
                f"{kind}: code 0x{code:02X} -> {font.code_to_gid(code)}, "
                f"expected {expected}"
            )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential tests against the live oracle
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("kind", _KINDS)
def test_code_to_gid_matches_pdfbox(kind: str, tmp_path: Path) -> None:
    """Every ``code -> GID`` (codes 0..255) must match Apache PDFBox exactly.

    This pins the symbolic fallback chain — raw (3,0), then 0xF000/F100/F200,
    then (1,0) Mac — and the absence of any code-as-GID fallback (the no_cmap
    fixture resolves every code to GID 0 in both engines). Pure integer
    arithmetic: zero tolerance.
    """
    pdf = _build_pdf(tmp_path / f"{kind}.pdf", _synth_ttf(kind))
    java = run_probe_text("SymbolicTtfProbe", "gid", str(pdf)).splitlines()
    py = _py_gid(pdf).splitlines()
    assert len(java) == len(py), (
        f"{kind}: line-count mismatch java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"symbolic code->gid parity broken for {kind}:\n" + "\n".join(diffs[:40])
    )


@requires_oracle
@pytest.mark.parametrize("kind", _KINDS)
def test_render_matches_pdfbox(kind: str, tmp_path: Path) -> None:
    """The rendered symbolic glyphs must paint where PDFBox paints them.

    Catches a wrong GID resolving to the wrong glyph (visibly different box),
    a blanked .notdef where PDFBox draws a glyph, or a wrong-scale render.
    """
    pdf = _build_pdf(tmp_path / f"{kind}.pdf", _synth_ttf(kind))
    (jw, jh), jgrid = _oracle_render(pdf)
    (pw, ph), pgrid = _py_render(pdf)

    assert (pw, ph) == (jw, jh), (
        f"{kind}: rendered dims diverge pypdfbox={pw}x{ph} java={jw}x{jh}"
    )
    diffs = [abs(a - b) for a, b in zip(jgrid, pgrid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{kind}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — symbolic glyph render grossly divergent"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{kind}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_no_cmap_resolves_every_code_to_gid_zero(tmp_path: Path) -> None:
    """Explicit pin for the high-value claim: a symbolic embedded TrueType font
    with **no usable cmap** maps every code to GID 0 (.notdef) — PDFBox's
    ``codeToGID`` has no "code is the glyph id" fallback. Asserted against the
    oracle so a future spurious code-as-GID fallback in pypdfbox fails here.
    """
    pdf = _build_pdf(tmp_path / "no_cmap.pdf", _synth_ttf("no_cmap"))
    java = run_probe_text("SymbolicTtfProbe", "gid", str(pdf)).splitlines()
    cgid = [ln for ln in java if ln.startswith("CGID\t")]
    assert cgid, "no CGID lines emitted"
    assert all(ln.endswith("\t0") for ln in cgid), (
        "PDFBox resolved some code to a non-zero GID for a no-cmap symbolic font"
    )
    # And pypdfbox agrees.
    assert _py_gid(pdf).splitlines() == java
