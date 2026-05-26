"""Live PDFBox differential parity for clipping paths + line styling.

Renders five small PDFs that exercise the clip / dash / cap / join surface
of :class:`PDFRenderer` against Apache PDFBox 3.0.7, comparing the coarse
16x16 luminance fingerprint emitted by ``oracle/probes/RenderProbe.java``.

Why a fingerprint and not a pixel diff: pypdfbox rasterises with
skia-python while PDFBox uses Java2D/AWT, so anti-aliasing differs at the
sub-pixel level. The 16x16 average-luminance grid survives AA but still
catches the gross failures this surface is prone to:

* a *clip* that is ignored bleeds paint into cells PDFBox leaves white;
* the *wrong fill rule* (non-zero where PDFBox used even-odd) fills a
  donut hole that should stay transparent;
* a *nested clip* that isn't restored after ``Q`` paints the wrong region;
* an ignored *dash / cap / join* renders a solid line where PDFBox dashes.

Cases (all built in-process, 200x200pt page, rendered at 72 DPI):

(a) ``clip_fill``  — ``W n`` rectangle clip; a full-page fill must only
    appear inside the rectangle (outside stays white).
(b) ``even_odd``   — ``W*`` self-overlapping (outer + inner rect) donut
    clip; the centre hole must stay unpainted (even-odd rule).
(c) ``nested``     — ``q W n ... Q`` inner clip restored to the outer clip
    after ``Q``, then a paint in the outer-only region reappears.
(d) ``dash``       — a thick stroke with ``[20 20] 0 d`` dash, round cap
    (``1 J``) and round join (``1 j``) — solid-stroke output diverges.
(e) ``text_clip``  — ``7 Tr`` text-clip with an *embedded* square-glyph
    TTF (so both renderers draw the identical outline — this isolates the
    clip from font-substitution shape differences), then a full-page fill
    that only survives inside the glyph outlines.

Tolerance mirrors ``test_render_oracle.py``: gate at ``MAD < 6.0`` and
``MAXDIFF < 60`` — above the AA ceiling, well below any clip/dash failure
floor. Two guard tests confirm the gate actually discriminates: an
*un-clipped* full-page fill, and a *solid* (un-dashed) stroke, both score
far over the gate against PDFBox's clipped / dashed reference.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 200.0


# --------------------------------------------------------------------------
# fingerprint helpers (must match RenderProbe.java's cell mapping exactly)
# --------------------------------------------------------------------------


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
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _oracle_signature(pdf: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(pdf), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# --------------------------------------------------------------------------
# PDF builders
# --------------------------------------------------------------------------


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _set_contents(page: PDPage, ops: bytes) -> None:
    cs = COSStream()
    cs.set_raw_data(ops)
    page.get_cos_object().set_item(COSName.CONTENTS, cs)


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(str(path))
    doc.close()


def _build_clip_fill(path: Path) -> None:
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n50 50 100 100 re\nW n\n0 0 0 rg\n0 0 200 200 re\nf\nQ\n",
    )
    _save(doc, path)


def _build_unclipped(path: Path) -> None:
    doc, page = _make_doc()
    _set_contents(page, b"0 0 0 rg\n0 0 200 200 re\nf\n")
    _save(doc, path)


def _build_even_odd(path: Path) -> None:
    # Outer rect (40..160) with inner rect (80..120) as a single even-odd
    # clip path -> annular clip; the centre hole stays unpainted.
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n40 40 120 120 re\n80 80 40 40 re\nW* n\n"
        b"0 0 0 rg\n0 0 200 200 re\nf\nQ\n",
    )
    _save(doc, path)


def _build_nested(path: Path) -> None:
    # Outer clip (20..180); a q-scoped inner clip (50..150) restricts the
    # first fill; after Q the outer clip is active again so a right-edge
    # strip (160..190) reappears.
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n20 20 160 160 re\nW n\n"
        b"q\n50 50 100 100 re\nW n\n"
        b"0 0 0 rg\n0 0 200 200 re\nf\n"
        b"Q\n"
        b"0 0 0 rg\n160 20 30 160 re\nf\n"
        b"Q\n",
    )
    _save(doc, path)


def _build_dash(path: Path) -> None:
    # Thick dashed strokes with round cap + round join.
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n10 w\n[20 20] 0 d\n1 J\n1 j\n0 0 0 RG\n"
        b"30 100 m\n170 100 l\nS\n"
        b"30 50 m\n100 150 l\n170 50 l\nS\n"
        b"Q\n",
    )
    _save(doc, path)


def _build_dash_solid(path: Path) -> None:
    # Identical geometry, but solid (no dash, butt cap, miter join) — used
    # by the guard test to prove the dash is genuinely exercised.
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n10 w\n0 0 0 RG\n"
        b"30 100 m\n170 100 l\nS\n"
        b"30 50 m\n100 150 l\n170 50 l\nS\n"
        b"Q\n",
    )
    _save(doc, path)


def _square_ttf_bytes() -> bytes:
    """A TrueType font whose ``A`` / ``B`` glyphs are solid 800x800-em
    squares, so the text-clip outline is identical in both renderers."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({0x41: "A", 0x42: "B"})

    def sq() -> object:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 100))
        pen.lineTo((900, 100))
        pen.lineTo((900, 900))
        pen.lineTo((100, 900))
        pen.closePath()
        return pen.glyph()

    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": sq(), "B": sq()})
    fb.setupHorizontalMetrics({".notdef": (0, 0), "A": (1024, 0), "B": (1024, 0)})
    fb.setupHorizontalHeader(ascent=900, descent=-100)
    fb.setupNameTable({"familyName": "DejaVuSquare", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, usWinAscent=900, usWinDescent=100)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _build_text_clip(path: Path) -> None:
    doc, page = _make_doc()
    font_file2 = COSStream()
    font_file2.set_raw_data(_square_ttf_bytes())
    descriptor = PDFontDescriptor(COSDictionary())
    descriptor.set_font_file2(font_file2)
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("DejaVuSquare")
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font_dict.set_item(COSName.get_pdf_name("FirstChar"), COSInteger.get(65))
    font_dict.set_item(COSName.get_pdf_name("LastChar"), COSInteger.get(66))
    widths = COSArray()
    widths.add(COSInteger.get(1000))
    widths.add(COSInteger.get(1000))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
    font = PDTrueTypeFont(font_dict)

    resources = page.get_resources()
    fname = resources.add(font)
    page.set_resources(resources)
    ops = (
        b"q\nBT\n/" + fname.get_name().encode("ascii") + b" 90 Tf\n"
        b"7 Tr\n30 60 Td\n(AB) Tj\nET\n"
        b"0 0 0 rg\n0 0 200 200 re\nf\nQ\n"
    )
    _set_contents(page, ops)
    _save(doc, path)


_BUILDERS = {
    "clip_fill": _build_clip_fill,
    "even_odd": _build_even_odd,
    "nested": _build_nested,
    "dash": _build_dash,
    "text_clip": _build_text_clip,
}


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


# --------------------------------------------------------------------------
# differential tests
# --------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_clip_and_line_style_match_pdfbox(label: str, tmp_path: Path) -> None:
    pdf = tmp_path / f"{label}.pdf"
    _BUILDERS[label](pdf)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _diff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — clip/line-style diverges, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_unclipped_fill_blows_past_clip_gate(tmp_path: Path) -> None:
    """Guard: an *un-clipped* full-page fill scores far over the gate
    against PDFBox's clipped reference. Proves the clip in ``clip_fill``
    is genuinely exercised (a no-op clip would let this pass)."""
    clipped = tmp_path / "clip_fill.pdf"
    unclipped = tmp_path / "unclipped.pdf"
    _build_clip_fill(clipped)
    _build_unclipped(unclipped)

    _dims, java_clipped_grid = _oracle_signature(clipped)
    py_unclipped_grid = _grid_from_image(_render_py(unclipped))
    mad, maxdiff = _diff(java_clipped_grid, py_unclipped_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"clip gate too loose: an un-clipped fill passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
def test_solid_stroke_blows_past_dash_gate(tmp_path: Path) -> None:
    """Guard: a *solid* (un-dashed, butt-cap, miter-join) stroke scores far
    over the gate against PDFBox's dashed/round reference. Proves the
    dash + cap + join in ``dash`` are genuinely exercised."""
    dashed = tmp_path / "dash.pdf"
    solid = tmp_path / "dash_solid.pdf"
    _build_dash(dashed)
    _build_dash_solid(solid)

    _dims, java_dashed_grid = _oracle_signature(dashed)
    py_solid_grid = _grid_from_image(_render_py(solid))
    mad, maxdiff = _diff(java_dashed_grid, py_solid_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"dash gate too loose: a solid stroke passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )
