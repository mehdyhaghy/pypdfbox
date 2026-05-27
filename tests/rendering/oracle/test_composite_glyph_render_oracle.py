"""Live PDFBox differential parity for TrueType **composite (compound)
glyph** rendering.

Wave 1438. An accented glyph such as ``é`` (``eacute``), ``à`` (``agrave``)
or ``ñ`` (``ntilde``) is a *composite* glyph in the TrueType ``glyf`` table:
its ``numberOfContours`` is negative and it carries no outline of its own —
instead it references one or more **component** base glyphs by GID, each with
an offset (``ARGS_ARE_XY_VALUES``) and an optional 2x2 transform, terminated by
the ``MORE_COMPONENTS`` loop. The composite outline is assembled by replaying
each component's (transformed) outline. ``eacute`` = ``e`` + ``acute``.

This file exercises the *render* path for composite glyphs end to end: it
embeds the bundled ``DejaVuSans.ttf`` (subsetting OFF so the composite glyph
and its component base glyphs are retained verbatim) as a Type0/CIDFontType2
font, shows the accented string ``éàñ`` at two font sizes, and compares the
rendered raster against Apache PDFBox.

The bug this guards against (fixed in wave 1438): pypdfbox's render pen bridge
(``rendering/_pen_bridge.make_base_pen_bridge``) overrode fontTools' BasePen
``addComponent`` and routed it to the delegate pen's ``add_component``. The
aggdraw render pen's ``add_component`` was a no-op, so every composite glyph's
components were silently dropped and accented characters rendered **blank**.
The fontbox ``glyf`` composite-assembly code (``GlyfCompositeDescript`` /
``GlyfCompositeComp``) is itself correct; the divergence was in the renderer's
pen bridge, which now falls back to BasePen's default component decomposition
(which transforms each base glyph and replays its outline) when the delegate
defines no meaningful ``add_component``.

Fingerprint (identical to the page/Type1/Type3 render oracles):

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs aggdraw) but catches a blank
  glyph, a wrong-scale glyph, a mis-assembled composite, or a dropped
  component.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 both sizes land at MAD ~0.5 / MAXDIFF ~12 (the composite glyphs
paint where PDFBox paints them). A *blank* render of either fixture measures
MAD well outside the gate (asserted below), proving the composite glyphs really
paint and the gate discriminates a correct render from a dropped composite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FONT = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# The accented string is the composite payload; ``e a n`` (the base glyphs)
# are the simple components ``éàñ`` decompose into.
_TEXT = "éàñ"

#   label -> (page width, page height, font size)
_CASES = {
    "size24": (140.0, 30.0, 24),
    "size40": (220.0, 48.0, 40),
}


def _build(out: Path, page_w: float, page_h: float, font_size: int) -> Path:
    """Embed ``DejaVuSans.ttf`` (subset OFF) and show ``éàñ`` at ``font_size``
    on a tight page."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, page_w, page_h))
        doc.add_page(page)

        # embed_subset=False keeps the composite glyph (and its component
        # base glyphs) in the embedded program verbatim, so the render path
        # must assemble the composite rather than a flattened/subset outline.
        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        encoded = font.encode(_TEXT)
        cs = COSStream()
        cs.set_data(
            b"BT\n/F1 %d Tf\n4 6 Td\n<%s> Tj\nET\n"
            % (font_size, encoded.hex().encode("ascii"))
        )
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
# fixture proof: the rendered glyphs really are composite
# ---------------------------------------------------------------------------


def test_accented_glyphs_are_composite() -> None:
    """Prove the test exercises the *composite* assembly path: each accented
    glyph has ``numberOfContours < 0`` and references component base glyphs;
    the base glyphs themselves are simple. If this font ever changed so the
    accented glyphs were simple, the render test below would no longer cover
    composite assembly."""
    font = TTFont(str(_FONT))
    glyf = font["glyf"]
    cmap = font.getBestCmap()
    for ch in _TEXT:
        name = cmap[ord(ch)]
        glyph = glyf[name]
        assert glyph.numberOfContours < 0, (
            f"{ch!r} ({name}) is not composite (numberOfContours="
            f"{glyph.numberOfContours}); the composite render path is not "
            f"exercised"
        )
        assert glyph.isComposite()
        assert len(glyph.components) >= 1
        # Every component is a real base glyph referenced by name/GID.
        for comp in glyph.components:
            base = glyf[comp.glyphName]
            assert base.numberOfContours >= 0, (
                f"component {comp.glyphName} of {name} is itself composite; "
                f"the simple-component assumption no longer holds"
            )


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_composite_glyph_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
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
    #     a mis-assembled composite (wrong component offset/scale), a dropped
    #     component, or a wrong-scale glyph.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — composite glyph render grossly divergent, "
        f"not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_blank_page_far_from_composite_reference(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (composite-glyph-bearing) render. Proves the composite
    glyphs really paint — if the components were dropped (the wave-1438 bug),
    pypdfbox's own render would be blank and would (wrongly) pass the gate
    above; this asserts a blank page does NOT pass, so the gate genuinely
    discriminates an assembled composite from a dropped one."""
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank page passes the MAD gate, "
        f"so a dropped composite glyph would not be caught (blank MAD "
        f"{mad:.2f})"
    )
