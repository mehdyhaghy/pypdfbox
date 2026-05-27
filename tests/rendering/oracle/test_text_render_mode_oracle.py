"""Live PDFBox differential parity for the text rendering-mode matrix
(``Tr`` 0-7, PDF 32000-1 §9.3.6 / Table 106).

The eight text rendering modes control whether a shown glyph is filled,
stroked, both, made invisible, and/or added to the clipping path:

============  ====================================
``Tr`` value  effect
============  ====================================
0             fill
1             stroke
2             fill then stroke
3             invisible (paints nothing)
4             fill + add to clip
5             stroke + add to clip
6             fill + stroke + add to clip
7             clip only (paints nothing; clip applied at ET)
============  ====================================

Each case below builds a tiny PDF that shows the same string under one
mode with *distinct* fill (red) and stroke (blue) colours so a fill-vs-
stroke confusion is visible in the fingerprint. The clip-only case (7)
shows the glyphs under mode 7 then fills the whole page red — only the
glyph interiors should survive the text clip.

Comparison reuses ``oracle/probes/RenderProbe.java`` (exact rendered
dimensions + a 16x16 average-luminance grid). Pixel-exact parity is
impossible across Java2D vs skia/Pillow (anti-aliasing, sub-pixel
coverage), so the same MAD<6 / MAXDIFF<60 tolerance the other render
oracles calibrated against PDFBox 3.0.7 at 72 DPI applies here.

The glyph source is the embedded ``DemoType1.pfb`` fixture (deliberately
tiny box outlines in a 1000-unit em) shown large so the painted glyphs
fill a sizeable fraction of the page — this makes a blank / wrong-mode
render clearly separable from a correct one in the coarse grid, and it
exercises the real Type 1 outline draw path (not the placeholder box).

Two extra guards beyond the per-mode MAD gate:

* **Tr 3 is blank** — the invisible mode must leave the page identical to
  an empty page (no paint at all). A renderer that fills/strokes glyphs
  under mode 3 fails here.
* **Tr 0 vs Tr 1 differ** — fill and stroke must be genuinely distinct
  outputs. A renderer that fills under a stroke mode (or vice-versa)
  collapses the two and fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate the other render oracles calibrated for whole-page parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"

# Page sized so the row of large box-outline glyphs fills a good fraction
# of the canvas (keeps the coarse 16x16 grid discriminating).
_PW, _PH, _FS = 160.0, 50.0, 60
_TEXT = b"ABCAB"

# Per-mode content streams. Fill = red (``1 0 0 rg``), stroke = blue
# (``0 0 1 RG``) at 1-unit width so fill and stroke are distinguishable.
_CONTENT: dict[str, bytes] = {
    # 0 — fill (red).
    "tr0_fill": b"BT\n/F1 %d Tf\n1 0 0 rg\n4 6 Td\n0 Tr\n(%s) Tj\nET\n"
    % (_FS, _TEXT),
    # 1 — stroke (blue, width 1).
    "tr1_stroke": b"BT\n/F1 %d Tf\n0 0 1 RG\n1 w\n4 6 Td\n1 Tr\n(%s) Tj\nET\n"
    % (_FS, _TEXT),
    # 2 — fill (red) then stroke (blue).
    "tr2_fill_stroke": b"BT\n/F1 %d Tf\n1 0 0 rg\n0 0 1 RG\n1 w\n"
    b"4 6 Td\n2 Tr\n(%s) Tj\nET\n" % (_FS, _TEXT),
    # 3 — invisible (page stays blank where the text is).
    "tr3_invisible": b"BT\n/F1 %d Tf\n1 0 0 rg\n4 6 Td\n3 Tr\n(%s) Tj\nET\n"
    % (_FS, _TEXT),
    # 7 — clip only, then fill the whole page red: only the glyph
    #     interiors should paint (everything else is clipped out at ET).
    "tr7_clip_fill": b"q\nBT\n/F1 %d Tf\n4 6 Td\n7 Tr\n(%s) Tj\nET\n"
    b"1 0 0 rg\n0 0 %d %d re\nf\nQ\n"
    % (_FS, _TEXT, int(_PW), int(_PH)),
    # Reference empty page (no text op) — the Tr 3 blank guard compares
    # against this.
    "blank": b"",
}


def _build(out: Path, content: bytes) -> Path:
    """Embed ``DemoType1.pfb`` via pypdfbox, write an explicit
    ``StandardEncoding`` (so the renderer resolves code -> glyph name for
    the embedded Type 1), and lay down ``content`` as the page stream."""
    pfb = (_FIXTURES / "DemoType1.pfb").read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PW, _PH))
        doc.add_page(page)

        font = PDType1Font.load(doc, pfb)
        font._dict.set_item(  # noqa: SLF001
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("StandardEncoding"),
        )

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = COSStream()
        cs.set_data(content)
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


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _py_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------

_MODE_LABELS = [
    "tr0_fill",
    "tr1_stroke",
    "tr2_fill_stroke",
    "tr3_invisible",
    "tr7_clip_fill",
]


@requires_oracle
@pytest.mark.parametrize("label", _MODE_LABELS, ids=_MODE_LABELS)
def test_text_render_mode_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each ``Tr`` mode renders identically (within the AA tolerance) to
    Apache PDFBox 3.0.7 at 72 DPI."""
    fixture = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _py_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance — catches a wrong mode
    #     (e.g. mode 3 painting, a stroke mode filling, a missing fill or
    #     stroke under mode 2, or the clip-only glyph painting itself).
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — text render mode grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_invisible_mode_is_blank(tmp_path: Path) -> None:
    """Tr 3 (invisible) must leave the page identical to an empty page —
    no fill, no stroke. Guards against a renderer that paints under the
    invisible mode."""
    blank = _build(tmp_path / "blank.pdf", _CONTENT["blank"])
    invisible = _build(tmp_path / "tr3.pdf", _CONTENT["tr3_invisible"])

    _bdims, blank_grid = _py_grid(blank)
    _idims, invisible_grid = _py_grid(invisible)
    mad, maxdiff = _mad_maxdiff(blank_grid, invisible_grid)
    assert maxdiff == 0, (
        f"Tr 3 painted something: invisible-vs-blank maxdiff={maxdiff} "
        f"(mad={mad:.2f}) — mode 3 must paint nothing"
    )

    # And cross-check against the oracle: PDFBox also renders Tr 3 blank.
    _jdims, java_invisible = _oracle_signature(invisible)
    jmad, jmaxdiff = _mad_maxdiff(java_invisible, invisible_grid)
    assert jmad < _MAD_TOLERANCE and jmaxdiff < _MAXDIFF_TOLERANCE, (
        f"Tr 3 diverges from PDFBox: mad={jmad:.2f} maxdiff={jmaxdiff}"
    )


@requires_oracle
def test_fill_and_stroke_modes_differ(tmp_path: Path) -> None:
    """Tr 0 (fill) and Tr 1 (stroke) must produce genuinely distinct
    output — a solid glyph vs a thin outline in a different colour. A
    renderer that fills under the stroke mode (or strokes under fill)
    would collapse the two; guard that they meaningfully diverge."""
    fill = _build(tmp_path / "fill.pdf", _CONTENT["tr0_fill"])
    stroke = _build(tmp_path / "stroke.pdf", _CONTENT["tr1_stroke"])

    _fdims, fill_grid = _py_grid(fill)
    _sdims, stroke_grid = _py_grid(stroke)
    mad, maxdiff = _mad_maxdiff(fill_grid, stroke_grid)
    # PDFBox's own fill-vs-stroke fingerprints differ by MAD ~3.7 /
    # MAXDIFF ~62 on this fixture; require a clear, well-above-AA-noise
    # separation so a fill/stroke collapse is caught.
    assert mad > 1.0 and maxdiff > 20, (
        f"Tr 0 (fill) and Tr 1 (stroke) are nearly identical "
        f"(mad={mad:.2f} maxdiff={maxdiff}) — a stroke mode may be "
        f"filling, or a fill mode stroking"
    )


@requires_oracle
def test_blank_render_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate itself: a blank page is far outside tolerance for a
    fixture PDFBox renders with content (Tr 0 fill). The painted glyphs
    sit in a few cells against white margins, so whole-page MAD stays
    modest — but the cells holding the dark-red glyphs diverge from white
    far past the MAXDIFF gate. Confirms the MAXDIFF gate discriminates a
    correct render from a blank one on this fixture."""
    fill = _build(tmp_path / "fill.pdf", _CONTENT["tr0_fill"])
    _dims, java_grid = _oracle_signature(fill)
    blank = [255] * (_GRID * _GRID)
    _mad, maxdiff = _mad_maxdiff(java_grid, blank)
    assert maxdiff >= _MAXDIFF_TOLERANCE, (
        "tolerance too loose: a blank render passes the MAXDIFF gate"
    )
