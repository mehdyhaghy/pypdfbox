"""Live PDFBox differential parity for embedded Type 1 (PFB / ``/FontFile``)
glyph *rendering*.

Wave 1433. Companion to:

* ``tests/fontbox/type1/oracle/test_type1_font_oracle.py`` — the Type 1
  *model / program* surface (font matrix, encoding, per-glyph widths), and
* ``tests/pdmodel/font/oracle/test_type1_embed_oracle.py`` — the embed
  round-trip (pypdfbox writes a ``/FontFile`` program PDFBox can read back).

This file exercises the distinct *render* path: ``pypdfbox.rendering`` driving
the **Type 1 charstring interpreter** (``hsbw`` / ``rmoveto`` / ``rlineto`` /
``rrcurveto`` / ``closepath`` plus the ``seac`` / flex / hint-replacement
``OtherSubrs`` machinery) over an embedded ``/FontFile`` program to produce a
glyph *outline*, then rasterising that outline at the text-rendering matrix.
That pipeline is wholly separate from the TrueType (``/FontFile2``) and CFF
(``/FontFile3``) glyph-paint branches — it pulls outlines via
``PDType1Font.get_glyph_path(code)`` → ``Type1Font.get_path(name)`` →
``Type1CharString``.

The classic Type 1 glyph-render bugs this guards against:

* **glyph not drawn** — the charstring outline is dropped (a swallowed decode
  error, an empty path), so the page is blank where it should paint;
* **wrong outline** — a charstring op mishandled (``hsbw`` left-side-bearing,
  ``closepath`` wind, a flex curve), so the glyph shape diverges;
* **wrong scale** — the ``units_per_em`` divisor or FontMatrix is wrong, so the
  glyph renders at the wrong size;
* **wrong advance / position** — the per-glyph width is mis-read, so successive
  glyphs overlap or spread.

No content-bearing embedded-Type 1 PDF ships in the corpus (the
``*Embedded.pdf`` fixtures embed the program for model inspection but draw no
text), so the test BUILDS the PDFs with pypdfbox: it embeds the wave-1416
``DemoType1.pfb`` program (StandardEncoding Type 1, glyphs A/B/C/space, each a
filled box outline) via ``PDType1Font.load`` and shows ``ABC`` at two font
sizes so the glyph-space → user-space scale is exercised at two scales. An
explicit ``/Encoding`` (``StandardEncoding``) is written so the renderer's
code → glyph-name lookup resolves (see the module note below on the
no-``/Encoding`` gap).

Each fixture is rendered through Apache PDFBox (``oracle/probes/RenderProbe``)
and through pypdfbox at 72 DPI and compared with the same fingerprint the
page-render oracle uses:

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw) but catches a
  blank glyph, a wrong-scale glyph, or a wrong outline.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 both sizes land at MAD ~0.0 / MAXDIFF ~0 (the Type 1 glyph path
paints pixel-for-pixel where PDFBox does). A *blank* render of either fixture
measures MAD well outside the gate (asserted below), proving the glyphs really
paint and the gate discriminates a correct render from a dropped one.

Wave 1433 fixed a latent bug this path surfaced: ``Type1Font.get_path`` /
``get_width`` called ``.draw()`` directly on each ``/CharStrings`` value, which
is correct only when the value is a decompiled fontTools ``T1CharString`` (the
embedded-``/FontFile`` reload path). For an in-memory ``create_with_pfb``
program the values are raw charstring *bytes* with no ``.draw``, so every
glyph outline came back empty — now both paths route bytes through pypdfbox's
own Type 1 charstring interpreter.

Cross-module note (NOT fixed here — outside the rendering / fontbox.type1
surface): an embedded Type 1 font with **no** ``/Encoding`` entry in its PDF
dict still has a well-defined *built-in* encoding from the embedded program,
and PDFBox renders it via that built-in. pypdfbox's
``PDSimpleFont.get_encoding_typed`` only surfaces the built-in for non-embedded
Standard 14 fonts, so ``PDType1Font._code_to_glyph_name`` returns ``None`` for
every code and the glyph is dropped. This test therefore writes an explicit
``/Encoding`` (the well-formed case); the no-``/Encoding`` gap is reported as a
cross-module root cause in ``pdmodel/font/pd_simple_font.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page / pattern render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"

# Two render cases: the ``DemoType1`` glyphs are deliberately tiny box
# outlines (100x100 in a 1000-unit em), so each case uses a page sized tightly
# around a row of glyphs at a given font size. This (a) exercises the
# glyph-space -> user-space scale (units_per_em divisor) at two scales, and
# (b) makes the painted glyphs fill a large fraction of the page so the coarse
# 16x16 grid clearly distinguishes a real render from a blank one (the blank
# guard below relies on this).
#   (page width, page height, font size, string)
_CASES = {
    "size40": (120.0, 16.0, 40, b"ABCABC"),
    "size60": (160.0, 20.0, 60, b"ABCAB"),
}


def _build(
    out: Path, page_w: float, page_h: float, font_size: int, text: bytes
) -> Path:
    """Embed ``DemoType1.pfb`` via pypdfbox, write an explicit
    ``StandardEncoding``, and show ``text`` at ``font_size`` on a tight page."""
    pfb = (_FIXTURES / "DemoType1.pfb").read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, page_w, page_h))
        doc.add_page(page)

        font = PDType1Font.load(doc, pfb)
        # Without an explicit /Encoding the renderer cannot resolve code ->
        # glyph name for an embedded Type 1 (cross-module gap, see module
        # docstring); StandardEncoding maps 65/66/67 -> A/B/C, matching the
        # program's own built-in encoding.
        font._dict.set_item(  # noqa: SLF001
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("StandardEncoding"),
        )

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
def test_type1_glyph_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
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
        f"(maxdiff={maxdiff}) — Type 1 glyph render grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_blank_page_far_from_type1_reference(label: str, tmp_path: Path) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (glyph-bearing) render. Proves the Type 1 glyphs really
    paint — if the charstring outlines were dropped, pypdfbox's own render
    would be blank and would (wrongly) pass the gate above; this asserts a
    blank page does NOT pass, so the gate genuinely discriminates a painted
    glyph from a dropped one."""
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank page passes the MAD gate, so "
        f"a dropped Type 1 glyph would not be caught (blank MAD {mad:.2f})"
    )
