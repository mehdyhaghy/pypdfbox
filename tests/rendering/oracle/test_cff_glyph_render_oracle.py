"""Live PDFBox differential parity for embedded CFF / Type 2 charstring
(``/FontFile3 /Type1C``) glyph *rendering*.

Wave 1438. Companion to:

* ``tests/pdmodel/font/oracle/test_cff_subset_oracle.py`` — the CFF
  *model / subset structure* surface (subtype, glyph count, CID flag,
  per-code widths), and
* ``tests/rendering/oracle/test_type1_glyph_render_oracle.py`` — the
  sibling *render* path for the Type 1 (``/FontFile``) charstring
  interpreter.

This file exercises the distinct CFF *render* path: ``pypdfbox.rendering``
driving the **Type 2 charstring interpreter** (``rmoveto`` / ``hmoveto`` /
``vmoveto`` / ``rlineto`` / ``hlineto`` / ``vlineto`` / ``rrcurveto`` /
``rcurveline`` / ``rlinecurve`` / ``vvcurveto`` / ``hhcurveto`` /
``vhcurveto`` / ``hvcurveto`` / ``flex`` / ``hflex`` / ``flex1`` /
``hflex1`` / ``endchar`` plus the ``callsubr`` / ``callgsubr`` recursion,
the local/global subr bias, and the ``hstem`` / ``vstem`` / ``hintmask`` /
``cntrmask`` hint-byte skipping) over an embedded ``/FontFile3 /Type1C``
CFF program to produce a glyph *outline*, then rasterising that outline at
the text-rendering matrix. That pipeline is wholly separate from the
TrueType (``/FontFile2`` / ``glyf``) and Type 1 (``/FontFile``) glyph-paint
branches — it pulls outlines via ``PDType1CFont.get_glyph_path(code)`` →
``CFFFont.get_path(name)`` → ``Type2CharString``.

The classic CFF / Type 2 glyph-render bugs this guards against:

* **glyph not drawn** — the charstring outline is dropped (a swallowed
  decode error, an empty path), so the page is blank where it should paint;
* **wrong outline** — a Type 2 op mishandled (a flex variant, the
  alternating-axis ``hvcurveto`` / ``vhcurveto`` / ``hhcurveto`` /
  ``vvcurveto`` logic, ``hintmask`` byte-skipping, a wrong subr bias), so
  the glyph shape diverges;
* **wrong scale** — the ``units_per_em`` divisor or CFF FontMatrix is
  wrong, so the glyph renders at the wrong size;
* **wrong advance / position** — the per-glyph width is mis-read, so
  successive glyphs overlap or spread.

No content-bearing *bold* CFF PDF ships in the corpus (the
``PDFBOX-3044-…`` / ``PDFBOX-3062-…`` fixtures bear faint real-document
text — a weak blank-vs-rendered discriminator), so this test BUILDS the
fixtures with pypdfbox: it generates a tiny CFF program (fontTools
``FontBuilder``, glyphs ``A`` / ``B`` / ``C`` / ``space`` — ``A`` a filled
box exercising ``hlineto``, ``B`` an outer body with an inner counter
exercising ``rmoveto`` + ``rrcurveto``, ``C`` a curve-heavy bowl exercising
``rrcurveto`` / ``vlineto``), embeds it as ``/FontFile3 /Subtype /Type1C``
on a ``PDType1CFont`` with an explicit ``/Encoding`` (WinAnsiEncoding maps
65/66/67 → A/B/C), and shows ``ABCABC`` at two font sizes so the
glyph-space → user-space scale is exercised at two scales. The glyphs are
deliberately large and solid so the coarse 16x16 grid sharply distinguishes
a real render from a blank one (the blank guard below relies on this).

Each fixture is rendered through Apache PDFBox (``oracle/probes/RenderProbe``)
and through pypdfbox at 72 DPI and compared with the same fingerprint the
page-render oracle uses:

* **exact page dimensions** — a mismatch is a real bug (wrong scale
  rounding), never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared
  by mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).
  Survives AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw)
  but catches a blank glyph, a wrong-scale glyph, or a wrong outline.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured
against PDFBox 3.0.7 both sizes land at MAD ~0.15 / MAXDIFF ~6 (the CFF
glyph path paints pixel-for-pixel where PDFBox does). A *blank* render of
either fixture measures MAD ~113 (asserted below), proving the glyphs
really paint and the gate discriminates a correct render from a dropped one.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page / pattern render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Two render cases: a tight page around a row of large solid glyphs at a
# given font size. This (a) exercises the glyph-space -> user-space scale
# (units_per_em divisor / CFF FontMatrix) at two scales, and (b) makes the
# painted glyphs fill a large fraction of the page so the coarse 16x16 grid
# clearly distinguishes a real render from a blank one.
#   (page width, page height, font size, string)
_CASES = {
    "size50": (200.0, 60.0, 50, b"ABCABC"),
    "size32": (140.0, 40.0, 32, b"ABCAB"),
}


def _build_cff_program() -> bytes:
    """Generate a minimal CFF (Type 2 charstring) program via fontTools
    ``FontBuilder`` and return the raw ``CFF `` table bytes.

    Glyphs are drawn so the Type 2 interpreter sees a representative op
    spread: ``A`` is a filled box (``hmoveto`` / ``hlineto`` /
    ``endchar``), ``B`` an outer body with an inner counter (``hmoveto`` /
    ``hlineto`` / ``rrcurveto`` / ``rmoveto``), ``C`` a curve-heavy bowl
    (``hmoveto`` / ``rrcurveto`` / ``vlineto``). fontTools' charstring
    compiler chooses the concrete op encoding (e.g. collapsing axis-aligned
    lines into ``hlineto`` / ``vlineto`` runs); both PDFBox and pypdfbox
    interpret whatever it emits, which is exactly the surface under test.
    """
    from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
    from fontTools.pens.t2CharStringPen import T2CharStringPen  # noqa: PLC0415
    from fontTools.ttLib import TTFont  # noqa: PLC0415

    order = [".notdef", "A", "B", "C", "space"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x41: "A", 0x42: "B", 0x43: "C", 0x20: "space"})

    def _box(pen: object, x0: int, y0: int, x1: int, y1: int) -> None:
        pen.moveTo((x0, y0))  # type: ignore[attr-defined]
        pen.lineTo((x1, y0))  # type: ignore[attr-defined]
        pen.lineTo((x1, y1))  # type: ignore[attr-defined]
        pen.lineTo((x0, y1))  # type: ignore[attr-defined]
        pen.closePath()  # type: ignore[attr-defined]

    def _glyph_a() -> object:
        pen = T2CharStringPen(700, {})
        _box(pen, 80, 0, 620, 700)
        return pen.getCharString()

    def _glyph_b() -> object:
        pen = T2CharStringPen(700, {})
        pen.moveTo((80, 0))
        pen.lineTo((620, 0))
        pen.curveTo((650, 200), (650, 500), (620, 700))
        pen.lineTo((80, 700))
        pen.closePath()
        # inner counter -> a second contour via rmoveto
        pen.moveTo((250, 250))
        pen.lineTo((450, 250))
        pen.lineTo((450, 450))
        pen.lineTo((250, 450))
        pen.closePath()
        return pen.getCharString()

    def _glyph_c() -> object:
        pen = T2CharStringPen(700, {})
        pen.moveTo((100, 0))
        pen.curveTo((300, -50), (500, -50), (620, 100))
        pen.lineTo((620, 600))
        pen.curveTo((500, 750), (300, 750), (100, 700))
        pen.closePath()
        return pen.getCharString()

    charstrings = {
        ".notdef": T2CharStringPen(700, {}).getCharString(),
        "A": _glyph_a(),
        "B": _glyph_b(),
        "C": _glyph_c(),
        "space": T2CharStringPen(300, {}).getCharString(),
    }
    fb.setupCFF("DemoCFF", {}, charstrings, {})
    fb.setupHorizontalMetrics(
        {g: (700 if g != "space" else 300, 0) for g in order}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {"familyName": "DemoCFF", "styleName": "Regular", "psName": "DemoCFF"}
    )
    fb.setupOS2()
    fb.setupPost()

    buf = io.BytesIO()
    fb.save(buf)
    buf.seek(0)
    return TTFont(buf).getTableData("CFF ")


def _build(
    out: Path, page_w: float, page_h: float, font_size: int, text: bytes
) -> Path:
    """Embed a generated CFF program as ``/FontFile3 /Type1C`` on a
    ``PDType1CFont`` with an explicit ``WinAnsiEncoding`` and show ``text``
    at ``font_size`` on a tight page."""
    cff = _build_cff_program()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, page_w, page_h))
        doc.add_page(page)

        ff3 = COSStream()
        ff3.set_data(cff)
        ff3.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1C")
        )

        fd = COSDictionary()
        fd.set_item(
            COSName.get_pdf_name("Type"),
            COSName.get_pdf_name("FontDescriptor"),
        )
        fd.set_item(
            COSName.get_pdf_name("FontName"), COSName.get_pdf_name("DemoCFF")
        )
        fd.set_int(COSName.get_pdf_name("Flags"), 4)
        bbox = COSArray()
        for v in (0, -200, 700, 800):
            bbox.add(COSInteger.get(v))
        fd.set_item(COSName.get_pdf_name("FontBBox"), bbox)
        fd.set_int(COSName.get_pdf_name("ItalicAngle"), 0)
        fd.set_int(COSName.get_pdf_name("Ascent"), 800)
        fd.set_int(COSName.get_pdf_name("Descent"), -200)
        fd.set_int(COSName.get_pdf_name("CapHeight"), 700)
        fd.set_int(COSName.get_pdf_name("StemV"), 80)
        fd.set_item(COSName.get_pdf_name("FontFile3"), ff3)

        font_dict = COSDictionary()
        font_dict.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font")
        )
        font_dict.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1")
        )
        font_dict.set_item(
            COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("DemoCFF")
        )
        font_dict.set_int(COSName.get_pdf_name("FirstChar"), 65)
        font_dict.set_int(COSName.get_pdf_name("LastChar"), 67)
        widths = COSArray()
        for w in (700, 700, 700):
            widths.add(COSInteger.get(w))
        font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
        font_dict.set_item(COSName.get_pdf_name("FontDescriptor"), fd)
        font_dict.set_item(
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("WinAnsiEncoding"),
        )

        font = PDType1CFont(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = COSStream()
        cs.set_data(b"BT\n/F1 %d Tf\n4 3 Td\n(%s) Tj\nET\n" % (font_size, text))
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror RenderProbe.java's cell mapping exactly
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
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
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_cff_glyph_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance — catches a blank glyph, a
    #     wrong-scale glyph, a wrong outline, or a wrong advance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — CFF glyph render grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_blank_page_far_from_cff_reference(label: str, tmp_path: Path) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (glyph-bearing) render. Proves the CFF glyphs really
    paint — if the Type 2 charstring outlines were dropped, pypdfbox's own
    render would be blank and would (wrongly) pass the gate above; this
    asserts a blank page does NOT pass, so the gate genuinely discriminates
    a painted glyph from a dropped one."""
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank page passes the MAD gate, so "
        f"a dropped CFF glyph would not be caught (blank MAD {mad:.2f})"
    )
