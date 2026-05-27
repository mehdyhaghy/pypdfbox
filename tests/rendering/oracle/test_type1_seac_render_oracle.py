"""Live PDFBox differential parity for Type 1 ``seac`` (Standard-Encoding
Accented Character) composite-glyph *rendering*.

Wave 1440. Companion to ``tests/rendering/oracle/test_type1_glyph_render_oracle.py``
(simple Type 1 glyph paint) and ``test_composite_glyph_render_oracle.py`` (the
TrueType ``glyf`` composite path). This file exercises the Type 1 analogue of
the wave-1438 TrueType composite-component drop.

A Type 1 ``seac`` charstring builds an **accented composite** glyph from a base
character plus an accent character, each referenced by its *StandardEncoding
code*, positioned by ``(adx, ady)`` (with the spec's ``adx += sbx - asb`` side-
bearing adjustment). ``eacute`` (``é``) = base ``e`` (code 101) + accent
``acute`` (code 194). The Type 1 spec §8.5 ``seac`` operator never carries the
component outlines itself — the interpreter must look the two component glyphs
up *by name* and replay their (translated) outlines.

In pypdfbox the Type 1 charstring interpreter is delegated to fontTools'
``T1OutlineExtractor`` (MIT, library-first per CLAUDE.md). Its ``op_seac``
resolves the base/accent names through StandardEncoding and emits two
``pen.addComponent(glyphName, transform)`` calls, relying on the pen's *glyph
set* to fetch and replay each component outline. The bug this guards against
(fixed in wave 1440): the embedded-``/FontFile`` render path
(``Type1Font.get_path`` → ``cs.draw(pen)``) built its recording pen with
``glyphSet=None``, so ``BasePen.addComponent``'s ``None[glyphName]`` lookup
raised ``TypeError``; the swallowed error dropped the **entire** composite and
every accented Type 1 glyph rendered **blank** — exactly the wave-1438 lesson
(the outline-assembly is correct, but a render-path pen handler silently drops
the composite). The fix supplies a glyph set
(``pypdfbox.fontbox.type1.type1_font._T1GlyphSet``) so fontTools' built-in
component decomposition resolves the base + accent outlines, plus a matching
``add_component`` on the in-memory (``create_with_pfb``) pen in
``pypdfbox.fontbox.cff.type1_char_string``.

No bundled Type 1 program has accented (``seac``) glyphs — ``DemoType1.pfb`` is
A/B/C boxes — so the fixture ``SeacType1.pfb`` is built (derived from
``DemoType1.pfb`` via fontTools' ``t1Lib`` writer so *both* load paths,
``create_with_pfb`` and the strict ``from_bytes`` PostScript interpreter, parse
it): a filled box ``e`` near the baseline, a small box ``acute`` up high, and an
``eacute`` whose charstring is ``[0 700 hsbw  0 0 0 101 194 seac  endchar]`` —
a genuine ``seac`` referencing ``e`` (101) + ``acute`` (194). A
``/Differences`` encoding maps code 65 → ``eacute`` so the renderer resolves the
composite. ``test_fixture_glyph_is_seac`` proves the test glyph really is a
``seac`` composite (not a standalone outline), so the render test below truly
covers the composite-assembly path.

Fingerprint (identical to the page / Type 1 / composite render oracles):

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw) but catches a
  blank composite, a base-only render (dropped accent), a mis-positioned accent
  (wrong adx/ady), or a wrong-scale glyph.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 the seac composite lands at MAD ~0.0 / MAXDIFF ~0 (the composed
outline paints pixel-for-pixel where PDFBox paints it). A *blank* render
measures MAD well outside the gate (asserted below): if the accent (or the
whole composite) were dropped, pypdfbox's render would diverge far from
PDFBox's, so the gate genuinely discriminates an assembled seac from a dropped
one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.t1Lib import T1Font
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page / glyph render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"
_SEAC_PFB = _FIXTURES / "SeacType1.pfb"

# The fixture's ``eacute`` glyph is a seac composite (base ``e`` 101 + accent
# ``acute`` 194). A /Differences encoding maps code 65 -> eacute so the
# renderer resolves the composite. Two scales exercise the glyph-space ->
# user-space divisor, and a row of glyphs fills enough of the page that the
# coarse 16x16 grid clearly separates a real composite from a blank one.
#   (page width, page height, font size, text)
_CASES = {
    "size48": (130.0, 24.0, 48, b"AAA"),
    "size64": (170.0, 30.0, 64, b"AA"),
}


def _build(
    out: Path, page_w: float, page_h: float, font_size: int, text: bytes
) -> Path:
    """Embed ``SeacType1.pfb`` via pypdfbox, map code 65 -> ``eacute`` via a
    ``/Differences`` encoding, and show ``text`` (the seac composite) at
    ``font_size`` on a tight page."""
    pfb = _SEAC_PFB.read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, page_w, page_h))
        doc.add_page(page)

        font = PDType1Font.load(doc, pfb)
        # A /Differences encoding mapping 65 -> eacute lets the renderer's
        # code -> glyph-name lookup resolve the seac composite irrespective
        # of the program's built-in encoding.
        enc_dict = COSDictionary()
        enc_dict.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding")
        )
        enc_dict.set_item(
            COSName.get_pdf_name("BaseEncoding"),
            COSName.get_pdf_name("StandardEncoding"),
        )
        diffs = COSArray()
        diffs.add(COSInteger.get(65))
        diffs.add(COSName.get_pdf_name("eacute"))
        enc_dict.set_item(COSName.get_pdf_name("Differences"), diffs)
        font._dict.set_item(  # noqa: SLF001
            COSName.get_pdf_name("Encoding"), enc_dict
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
# fixture proof: the test glyph really is a seac composite
# ---------------------------------------------------------------------------


def test_fixture_glyph_is_seac() -> None:
    """Prove the test exercises the *seac* composite path: the fixture's
    ``eacute`` charstring uses the ``seac`` operator and references the
    base ``e`` (StandardEncoding 101) + accent ``acute`` (194). If the
    fixture ever changed so ``eacute`` were a standalone outline, the
    render test below would no longer cover the seac composite path."""
    font = T1Font(str(_SEAC_PFB))
    font.parse()
    charstrings = font.font["CharStrings"]
    cs = charstrings["eacute"]
    cs.decompile()
    program = cs.program
    assert "seac" in program, (
        f"eacute is not a seac composite (program={program}); the seac "
        f"render path is not exercised"
    )
    idx = program.index("seac")
    # asb adx ady bchar achar seac
    _asb, _adx, _ady, bchar, achar = program[idx - 5 : idx]
    assert int(bchar) == 101, f"seac base char is {bchar}, expected 101 (e)"
    assert int(achar) == 194, f"seac accent char is {achar}, expected 194 (acute)"
    # The components must themselves be real (non-seac) outlines.
    for comp_name in ("e", "acute"):
        comp = charstrings[comp_name]
        comp.decompile()
        assert "seac" not in comp.program, (
            f"component {comp_name} is itself a seac; the simple-component "
            f"assumption no longer holds"
        )


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_type1_seac_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
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

    # (b) Perceptual grid parity within tolerance — catches a blank composite,
    #     a base-only render (dropped accent), a mis-positioned accent (wrong
    #     adx/ady), or a wrong-scale glyph.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — seac composite render grossly divergent, "
        f"not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_blank_page_far_from_seac_reference(label: str, tmp_path: Path) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (seac-composite-bearing) render. Proves the seac glyph
    really paints — if the composite (or just the accent component) were
    dropped, pypdfbox's own render would be blank/base-only and would
    (wrongly) pass the gate above; this asserts a blank page does NOT pass,
    so the gate genuinely discriminates an assembled seac from a dropped
    one."""
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank page passes the MAD gate, "
        f"so a dropped seac composite would not be caught (blank MAD "
        f"{mad:.2f})"
    )
