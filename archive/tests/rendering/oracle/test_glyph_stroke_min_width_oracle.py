"""Live PDFBox differential parity for the glyph-outline stroke pen at the
**minimum-width regime** (wave 1595).

Apache PDFBox strokes glyph outlines (text rendering modes 1 / 2 / 5 / 6,
PDF 32000-1 §9.3.6) through the *same* ``PageDrawer.getStroke`` as vector
path strokes (``S`` / ``B``): the device pen width is
``lineWidth * transformWidth(CTM)`` floored to **0.25** device pixels
("minimum line width as used by Adobe Reader"). There is no separate
glyph-stroke minimum and ``/SA`` does not snap the width to a full pixel.

Before wave 1595 the per-glyph pen (``_build_stroke_pen``) floored the
device width to 0.5 (with a ``/SA``-snap-to-1.0 rule) — roughly 2x wider
than PDFBox at the floor. This oracle pins both regimes against PDFBox
3.0.7:

* **minimum-width** — a hairline stroke (``0.05 w``) at a large font:
  the device width (0.05 px) is below the floor for *both* engines, so
  both clamp to 0.25 and the rendered outlines must match within the AA
  tolerance. A 0.5-floor renderer paints a visibly heavier outline here.
* **large-font (wave 1442 regression guard)** — a ``1 w`` stroke at 60 pt:
  the wave-1442 fix that moved the floor into device space (so a 1-unit
  hairline no longer became a ~30 px slab) must stay intact.

Comparison reuses ``oracle/probes/RenderProbe.java`` (exact rendered
dimensions + a 16x16 average-luminance grid) at 72 DPI, the same
MAD<6 / MAXDIFF<60 tolerance the sibling render oracles calibrated
against PDFBox 3.0.7.
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
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"

# Large enough that the box-outline glyphs fill a good fraction of the
# canvas — keeps the coarse 16x16 grid discriminating between a 0.25 floor
# and a 0.5 floor at the hairline.
_PW, _PH, _FS = 160.0, 50.0, 60
_TEXT = b"ABCAB"

_CONTENT: dict[str, bytes] = {
    # Minimum-width regime: 0.05-user-unit stroke at 60 pt → 0.05 device px,
    # below the 0.25 floor for both engines. A 0.5-floor renderer paints a
    # heavier outline than PDFBox here.
    "tr1_hairline": b"BT\n/F1 %d Tf\n0 0 1 RG\n0.05 w\n4 6 Td\n1 Tr\n(%s) Tj\nET\n"
    % (_FS, _TEXT),
    # Same hairline under mode 2 (fill red + stroke blue).
    "tr2_hairline": b"BT\n/F1 %d Tf\n1 0 0 rg\n0 0 1 RG\n0.05 w\n"
    b"4 6 Td\n2 Tr\n(%s) Tj\nET\n" % (_FS, _TEXT),
    # Large-font wave-1442 regression guard: 1-unit stroke at 60 pt must
    # remain a thin outline (the floor is applied in device space, not
    # glyph-local space — otherwise it became a ~30 px slab).
    "tr1_large": b"BT\n/F1 %d Tf\n0 0 1 RG\n1 w\n4 6 Td\n1 Tr\n(%s) Tj\nET\n"
    % (_FS, _TEXT),
}


def _build(out: Path, content: bytes) -> Path:
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


_LABELS = ["tr1_hairline", "tr2_hairline", "tr1_large"]


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_glyph_stroke_min_width_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """The glyph-outline stroke pen renders identically (within the AA
    tolerance) to PDFBox 3.0.7 at both the sub-pixel floor (0.25) and the
    large-font (wave-1442) regime."""
    fixture = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _py_grid(fixture)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — glyph stroke width grossly divergent from "
        f"PDFBox, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_hairline_stroke_lighter_than_default_width(tmp_path: Path) -> None:
    """Sanity that the fixture actually exercises the floor: a 0.05-unit
    hairline outline (floored to 0.25 device px) covers less ink than a
    1-unit stroke at the same font size. Confirms the minimum-width regime
    is genuinely below the natural width, so the floor (not the nominal
    width) governs the rendered outline — the case where the old 0.5 floor
    would have over-painted relative to PDFBox."""
    hairline = _build(tmp_path / "hairline.pdf", _CONTENT["tr1_hairline"])
    large = _build(tmp_path / "large.pdf", _CONTENT["tr1_large"])

    _hd, hairline_grid = _py_grid(hairline)
    _ld, large_grid = _py_grid(large)
    # Lower luminance == more (blue) ink. The hairline page must be lighter
    # overall (more white) than the 1-unit-stroke page.
    assert sum(hairline_grid) > sum(large_grid), (
        "hairline stroke is not lighter than the 1-unit stroke — the "
        "minimum-width regime may not be exercised by this fixture"
    )
