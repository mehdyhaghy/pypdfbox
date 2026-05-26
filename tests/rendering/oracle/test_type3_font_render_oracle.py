"""Live PDFBox differential parity for Type 3 font glyph *rendering*.

Wave 1430. Companion to ``tests/pdmodel/font/oracle/test_type3_font_oracle.py``
(which checks the Type 3 *model* surface — FontMatrix, encoding, widths). This
file exercises the distinct *render* path: ``pypdfbox.rendering`` executing each
glyph's ``/CharProcs`` content stream under the font's ``/FontMatrix``, honouring
the ``d0`` / ``d1`` width-and-colour operators and the surrounding text-state
colour.

A Type 3 glyph is a mini content stream (drawing ops, not an outline), so this
path is wholly separate from TrueType / CFF glyph painting — it runs the
charproc bytes through the same dispatch loop a Form XObject uses, with the CTM
folded as ``FontMatrix * text_local * text_matrix``. The classic Type 3 render
bugs are:

* **glyph not drawn** — the charproc fills/strokes are dropped, so the page is
  blank where it should paint;
* **FontMatrix scale wrong** — a glyph defined in a 1000-unit em cell renders at
  the wrong size (off by the FontMatrix factor);
* **d0 / d1 colour handling wrong** — a ``d1`` ("coloured" form) glyph must take
  the *text-state* non-stroking colour, while a ``d0`` glyph paints its own
  colour ops; mixing these up gives the wrong colour;
* **char-proc /Resources not resolved** — a charproc that references the font's
  own resources finds nothing.

No Type 3 fixture ships in the corpus, so the test BUILDS Type 3 font PDFs with
pypdfbox: a ``d1`` glyph (filled box, colour inherited from the text state) and
a ``d0`` glyph (a bar that sets its own black fill). Each fixture is shown at a
different font size so FontMatrix scaling is exercised, then rendered through
Apache PDFBox (``oracle/probes/RenderProbe.java``) and through pypdfbox at 72
DPI and compared with the same tolerance fingerprint the page-render oracle
uses:

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw) but catches a
  blank glyph, a wrong-scale glyph, or the wrong d0/d1 colour.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 both cases land at MAD ~0.0 / MAXDIFF ~0 (the Type 3 glyph path
paints pixel-for-pixel where PDFBox does). A *blank* render of either fixture
measures MAD 26+ — comfortably outside the gate (asserted below), proving the
glyphs actually paint and the gate discriminates a correct render from a dropped
one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page / pattern render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE_W = 200.0
_PAGE_H = 120.0

# Standard 1000-unit-em Type 3 FontMatrix. The two render cases below show the
# glyphs at different font sizes, so the FontMatrix * font_size composition (and
# thus the glyph-space -> user-space scale) is exercised at two scales.
_FONT_MATRIX = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------------------------------------------------------------------------
# /CharProcs glyph streams
# ---------------------------------------------------------------------------


def _char_proc_box() -> COSStream:
    """Code 65 ('box'): a ``d1`` (coloured form) glyph — a filled 750x750
    glyph-space box. Per PDF 32000-1 §9.6.5.3 a ``d1`` glyph paints in the
    *current text-state* non-stroking colour; the charproc sets NO colour of
    its own, so the box must inherit the page's ``rg`` colour. This is the
    primary d1-colour-from-text-state probe."""
    body = b"750 0 0 0 750 750 d1\n0 0 750 750 re f\n"
    stream = COSStream()
    stream.set_data(body)
    return stream


def _char_proc_bar() -> COSStream:
    """Code 66 ('bar'): a ``d0`` (uncoloured-advance form) glyph that sets its
    OWN colour (black) and fills a vertical bar. A ``d0`` glyph is free to
    paint with its own colour ops; this verifies the renderer does NOT force
    the text-state colour onto a d0 glyph (it would tint the bar otherwise)."""
    body = b"750 0 d0\n0 0 0 rg\n100 0 400 750 re f\n"
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_type3_font_dict() -> COSDictionary:
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("box"), _char_proc_box())
    char_procs.set_item(COSName.get_pdf_name("bar"), _char_proc_bar())

    # /Differences: code 65 -> box, 66 -> bar (Type 3 has no built-in encoding).
    differences = COSArray()
    differences.add(COSInteger.get(65))
    differences.add(COSName.get_pdf_name("box"))
    differences.add(COSName.get_pdf_name("bar"))
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3")
    )
    font_dict.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("T3"))
    font_dict.set_item(
        COSName.get_pdf_name("FontMatrix"),
        COSArray([COSFloat(v) for v in _FONT_MATRIX]),
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontBBox"),
        COSArray([COSInteger.get(v) for v in (0, 0, 750, 750)]),
    )
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, 65)
    font_dict.set_int(COSName.LAST_CHAR, 66)
    font_dict.set_item(
        COSName.get_pdf_name("Widths"), COSArray([COSFloat(750.0), COSFloat(750.0)])
    )
    return font_dict


def _build(out: Path, content: bytes) -> Path:
    """Save a one-page PDF whose only font is the Type 3 font above, with the
    given page content stream (which shows the glyphs)."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    doc.add_page(page)

    font = PDType3Font(_build_type3_font_dict())
    res = PDResources()
    res.put(COSName.get_pdf_name("F1"), font)
    font.set_resources(PDResources())
    page.set_resources(res)

    cs = COSStream()
    cs.set_data(content)
    page.set_contents(cs)
    doc.save(str(out))
    doc.close()
    return out


# Two render cases. Each shows glyphs filling a large fraction of the page so a
# dropped glyph is obvious in the coarse grid.
#   size40_d1 — four 'box' (d1) glyphs in a red text state: tests d1 inheriting
#               the text-state colour, and FontMatrix scaling at 40pt.
#   size80_mix — one 'box' (d1, blue text state) + one 'bar' (d0, own black):
#               tests d0 vs d1 colour handling side-by-side, FontMatrix at 80pt.
_BUILDERS = {
    "size40_d1": b"BT\n1 0 0 rg\n/F1 40 Tf\n4 4 Td\n<41414141> Tj\nET\n",
    "size80_mix": b"BT\n0 0 1 rg\n/F1 80 Tf\n2 8 Td\n<4142> Tj\nET\n",
}


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
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_type3_glyph_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _build(tmp_path / f"{label}.pdf", _BUILDERS[label])
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
    #     wrong-scale glyph (FontMatrix bug), or the wrong d0/d1 colour.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — Type 3 glyph render grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_blank_page_far_from_type3_reference(label: str, tmp_path: Path) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (glyph-bearing) render. Proves the Type 3 glyphs really
    paint — if the charproc fills were dropped, pypdfbox's own render would be
    blank and would (wrongly) pass the gate above; this asserts a blank page
    does NOT pass, so the gate genuinely discriminates a painted glyph."""
    fixture = _build(tmp_path / f"{label}.pdf", _BUILDERS[label])
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank page passes the MAD gate, so "
        f"a dropped Type 3 glyph would not be caught (blank MAD {mad:.2f})"
    )
