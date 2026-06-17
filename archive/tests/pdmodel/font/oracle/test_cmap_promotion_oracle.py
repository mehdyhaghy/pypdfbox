"""Live PDFBox differential parity for **dual-cmap** Unicode-platform promotion
in a non-symbolic simple TrueType font (PDFBOX-4755 / PDFBOX-5484).

Wave 1446. Upstream ``PDTrueTypeFont.extractCmapTable`` collects the cmap
subtables and assigns the ``cmapWinUnicode`` slot for *both* the canonical
``(3,1)`` Windows-Unicode-BMP subtable **and** the Unicode-platform
``(0,0)`` / ``(0,3)`` subtables — and it does so *unconditionally*. When a
single font carries **both** a ``(3,1)`` and a ``(0,x)`` subtable that map the
same code to *different* glyph ids, the assignment that survives is the **last**
one in cmap-directory iteration order (last-wins).

pypdfbox previously guarded the ``(0,x)`` → win-Unicode promotion with
``and self._cmap_win_unicode is None`` (first-wins / ``putIfAbsent``), so a real
``(3,1)`` subtable was never clobbered by a later Unicode-platform subtable.
That diverges from upstream only for the narrow dual-cmap case this file
synthesizes; the symbolic-no-``(3,1)`` surface (``test_symbolic_ttf_oracle``)
is unaffected and stays at parity.

The fixture is a non-symbolic TrueType simple font (``/Flags`` non-symbolic,
``/Encoding WinAnsiEncoding``) that embeds a font program whose cmap holds:

  * a ``(3,1)`` Win-Unicode subtable mapping ``U+0041`` ('A') → glyph ``g1``
    (GID 1) and ``U+0042`` ('B') → ``g2`` (GID 2);
  * a ``(0,3)`` Unicode-2.0-BMP subtable mapping ``U+0041`` → ``g2`` (GID 2)
    and ``U+0042`` → ``g1`` (GID 1) — i.e. the **swapped** assignment.

fontTools always sorts the cmap encoding-record directory by
``(platformID, platEncID)`` on compile, which would place ``(0,3)`` *before*
``(3,1)`` — making last-wins land back on ``(3,1)`` and hiding the bug. So the
fixture post-processes the saved bytes to reorder the directory records to
``(3,1)`` then ``(0,3)`` (the subtable data stays put; only the directory order
changes). Both engines iterate the directory in that order, so last-wins lands
on ``(0,3)``.

Disputed result for code ``0x41`` (→ 'A' → ``U+0041`` via WinAnsi):
  * first-wins (pre-fix pypdfbox) → ``(3,1)`` → GID 1;
  * last-wins  (upstream + post-fix pypdfbox) → ``(0,3)`` → GID 2.

Parity: ``PDTrueTypeFont.codeToGID(code)`` for codes 0..255 must match Apache
PDFBox 3.0.7 (``CmapLookupProbe`` ``pdf`` mode) line for line — pure integer
arithmetic, zero tolerance.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FtCmapSubtable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

# Non-symbolic /Flags: bit 6 (Nonsymbolic) set, bit 3 (Symbolic) clear.
_FLAG_NONSYMBOLIC = 0x20

_GLYPH_ORDER = [".notdef", "g1", "g2"]

# Codes shown on the page. 0x41 ('A') and 0x42 ('B') are the disputed codes
# (present in both cmaps with swapped glyph ids); 0x43 ('C') is in neither.
_CODES = (0x41, 0x42, 0x43)


# ---------------------------------------------------------------------------
# font synthesis — one TTF carrying BOTH a (3,1) and a (0,3) cmap that disagree
# ---------------------------------------------------------------------------


def _glyphs() -> dict:
    """Three distinct filled-box glyphs so a wrong GID is observable."""
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
    return pens


def _subtable(fmt: int, plat: int, enc: int, mapping: dict[int, str]):
    sub = FtCmapSubtable.getSubtableClass(fmt)(fmt)
    sub.format = fmt
    sub.platformID = plat
    sub.platEncID = enc
    sub.language = 0
    sub.cmap = mapping
    return sub


def _reorder_cmap_directory(data: bytes) -> bytes:
    """Rewrite the cmap encoding-record directory so ``(3,1)`` is iterated
    *before* ``(0,3)``.

    fontTools sorts the directory by ``(platformID, platEncID)`` on compile,
    which would place ``(0,3)`` first and make upstream last-wins land back on
    ``(3,1)`` — hiding the divergence. We swap only the directory records (the
    subtable byte blobs stay where they are, still referenced by their original
    offsets), so a reader iterating the directory visits ``(3,1)`` then
    ``(0,3)``.
    """
    buf = bytearray(data)
    num_tables = struct.unpack(">H", buf[4:6])[0]
    rec = 12
    cmap_off = None
    for _ in range(num_tables):
        tag = bytes(buf[rec : rec + 4])
        off = struct.unpack(">I", buf[rec + 8 : rec + 12])[0]
        if tag == b"cmap":
            cmap_off = off
        rec += 16
    assert cmap_off is not None, "no cmap table in synthesized font"
    _ver, nsub = struct.unpack(">HH", buf[cmap_off : cmap_off + 4])
    recs = []
    p = cmap_off + 4
    for _ in range(nsub):
        plat, enc, o = struct.unpack(">HHl", buf[p : p + 8])
        recs.append((plat, enc, o))
        p += 8
    # (3,1) first, everything else after (stable for the rest).
    order = sorted(range(nsub), key=lambda i: 0 if recs[i][:2] == (3, 1) else 1)
    p = cmap_off + 4
    for i in order:
        buf[p : p + 8] = struct.pack(">HHl", *recs[i])
        p += 8
    return bytes(buf)


def _synth_ttf() -> bytes:
    """A TTF whose cmap holds a ``(3,1)`` and a ``(0,3)`` subtable that map
    ``U+0041`` / ``U+0042`` to *swapped* glyph ids, with the directory ordered
    ``(3,1)`` then ``(0,3)``."""
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(_GLYPH_ORDER)
    fb.setupCharacterMap({})
    fb.setupGlyf(_glyphs())
    fb.setupHorizontalMetrics({n: (900, 50) for n in _GLYPH_ORDER})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {"familyName": "DispTest", "styleName": "Regular", "psName": "DispTest"}
    )
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = [
        _subtable(4, 3, 1, {0x41: "g1", 0x42: "g2"}),
        _subtable(4, 0, 3, {0x41: "g2", 0x42: "g1"}),
    ]
    fb.font["cmap"] = cmap
    buf = io.BytesIO()
    fb.font.save(buf)
    return _reorder_cmap_directory(buf.getvalue())


def _build_pdf(out: Path, ttf_bytes: bytes) -> Path:
    """Embed ``ttf_bytes`` as a *non-symbolic* simple TrueType font with an
    explicit ``/Encoding WinAnsiEncoding`` and show ``_CODES``."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 200.0, 80.0))
        doc.add_page(page)

        font_dict = COSDictionary()
        font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
        font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
        font_dict.set_name(COSName.get_pdf_name("BaseFont"), "DispTest")
        font_dict.set_int(COSName.get_pdf_name("FirstChar"), 0)
        font_dict.set_int(COSName.get_pdf_name("LastChar"), 255)
        widths = COSArray()
        for _ in range(256):
            widths.add(COSFloat(900.0))
        font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
        # WinAnsiEncoding so 0x41 -> 'A' -> U+0041, 0x42 -> 'B' -> U+0042.
        font_dict.set_name(COSName.get_pdf_name("Encoding"), "WinAnsiEncoding")

        descriptor = PDFontDescriptor()
        descriptor.set_font_name("DispTest")
        descriptor.set_flags(_FLAG_NONSYMBOLIC)
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
# pypdfbox reproduction of the probe's pdf-mode output
# ---------------------------------------------------------------------------


def _py_gid(pdf_path: Path) -> str:
    """Reconstruct CmapLookupProbe ``pdf`` mode output, line for line."""
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


# Disputed codes resolve last-wins → (0,3): 0x41 ('A') -> g2 (GID 2),
# 0x42 ('B') -> g1 (GID 1). 0x43 ('C') is in neither cmap and the font has no
# 'C' glyph name in its post table, so it resolves to GID 0 (.notdef) — pinned
# from the live oracle so the no-oracle test still locks the full result.
_EXPECTED_GID = {0x41: 2, 0x42: 1, 0x43: 0}


# ---------------------------------------------------------------------------
# fixture proof (no oracle needed)
# ---------------------------------------------------------------------------


def test_fixture_carries_both_cmaps_that_disagree(tmp_path: Path) -> None:
    """Prove the synthesized font really carries both a ``(3,1)`` and a
    ``(0,3)`` subtable, that they map the disputed codes to *different* glyph
    ids, and that the directory iterates ``(3,1)`` before ``(0,3)`` — without
    all three, first-wins vs last-wins would not be observable."""
    ttf_bytes = _synth_ttf()
    font = TTFont(io.BytesIO(ttf_bytes))
    try:
        tables = font["cmap"].tables
        order = [(t.platformID, t.platEncID) for t in tables]
        assert (3, 1) in order, "missing (3,1) Win-Unicode cmap"
        assert (0, 3) in order, "missing (0,3) Unicode-platform cmap"
        # Directory iteration must visit (3,1) before (0,3) for last-wins to
        # land on (0,3).
        assert order.index((3, 1)) < order.index((0, 3)), (
            f"cmap directory order {order} does not iterate (3,1) before (0,3)"
        )
        sub31 = next(t for t in tables if (t.platformID, t.platEncID) == (3, 1))
        sub03 = next(t for t in tables if (t.platformID, t.platEncID) == (0, 3))
        # The two subtables must DISAGREE on the disputed codepoints.
        assert sub31.cmap.get(0x41) != sub03.cmap.get(0x41)
        assert sub31.cmap.get(0x42) != sub03.cmap.get(0x42)
    finally:
        font.close()


def test_code_to_gid_uses_last_wins_promotion(tmp_path: Path) -> None:
    """Pin the disputed-code result (last-wins → ``(0,3)``) without the oracle
    so a machine without Java still locks the promotion semantics. Pre-fix this
    asserted GID 1 for 0x41 (first-wins → ``(3,1)``); post-fix it is GID 2."""
    pdf = _build_pdf(tmp_path / "disp.pdf", _synth_ttf())
    doc = PDDocument.load(pdf)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        font = res.get_font(next(iter(res.get_font_names())))
        assert isinstance(font, PDTrueTypeFont)
        assert font.is_symbolic() is False
        for code, expected in _EXPECTED_GID.items():
            assert font.code_to_gid(code) == expected, (
                f"code 0x{code:02X} -> {font.code_to_gid(code)}, expected {expected}"
            )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential test against the live oracle
# ---------------------------------------------------------------------------


@requires_oracle
def test_code_to_gid_matches_pdfbox(tmp_path: Path) -> None:
    """Every ``code -> GID`` (codes 0..255) must match Apache PDFBox 3.0.7.

    This pins the dual-cmap last-wins promotion: PDFBox's ``codeToGID`` resolves
    the disputed 0x41 to the ``(0,3)`` glyph (GID 2), proving pypdfbox's
    ``extract_cmap_table`` matches upstream's unconditional ``cmapWinUnicode``
    assignment. Pure integer arithmetic: zero tolerance.
    """
    pdf = _build_pdf(tmp_path / "disp.pdf", _synth_ttf())
    java = run_probe_text("CmapLookupProbe", "pdf", str(pdf)).splitlines()
    py = _py_gid(pdf).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        "dual-cmap code->gid parity broken:\n" + "\n".join(diffs[:40])
    )


@requires_oracle
def test_disputed_code_resolves_to_unicode_platform_glyph(tmp_path: Path) -> None:
    """Explicit pin for the high-value claim: with both a ``(3,1)`` and a later
    ``(0,3)`` subtable, PDFBox resolves the disputed code via the ``(0,3)``
    subtable (last-wins), not the ``(3,1)`` one. Asserted against the oracle so a
    future first-wins regression in pypdfbox fails here, not silently."""
    pdf = _build_pdf(tmp_path / "disp.pdf", _synth_ttf())
    java = run_probe_text("CmapLookupProbe", "pdf", str(pdf)).splitlines()
    java_map = {}
    for ln in java:
        parts = ln.split("\t")
        if parts[0] == "CGID":
            java_map[int(parts[1])] = int(parts[2])
    # PDFBox lands on the (0,3) glyph: 0x41 -> GID 2 (not the (3,1) GID 1).
    assert java_map[0x41] == 2, f"PDFBox 0x41 -> {java_map[0x41]}, expected 2"
    assert java_map[0x42] == 1, f"PDFBox 0x42 -> {java_map[0x42]}, expected 1"
    # And pypdfbox agrees code-for-code.
    py = _py_gid(pdf).splitlines()
    assert py == java
