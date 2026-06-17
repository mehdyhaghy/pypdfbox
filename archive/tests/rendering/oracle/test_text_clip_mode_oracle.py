"""Live PDFBox differential parity for the text rendering-mode CLIP variants
(``Tr`` 4/5/6, PDF 32000-1 §9.3.6 / Table 106).

``test_text_render_mode_oracle.py`` already pins the paint-only modes
(``Tr`` 0 fill / 1 stroke / 2 fill+stroke / 3 invisible) and the clip-ONLY
mode 7 (clip + no paint). The orthogonal gap it does NOT cover is the three
modes that BOTH paint AND add the glyph outlines to the clipping path:

============  ============================================
``Tr`` value  effect
============  ============================================
4             fill   + add glyph outlines to clip (at ``ET``)
5             stroke + add glyph outlines to clip
6             fill + stroke + add glyph outlines to clip
============  ============================================

Each fixture shows the same string under one clip-mode with distinct fill
(red) and stroke (blue) colours, ends the text object (``ET`` commits the
accumulated glyph union into the GS clip), then fills the whole page green.
After ``ET`` only the glyph interiors survive the clip, so the green page-
fill paints solely inside the glyph outlines. The render therefore proves
two things at once for each mode:

* the glyphs were painted (fill / stroke per the mode) *during* the text
  object — distinguishing 4/5/6 from clip-only mode 7; and
* the glyph outlines were added to the clip and committed at ``ET`` —
  the subsequent whole-page green fill is confined to the glyph region.

Comparison reuses the proven coarse fingerprint (exact rendered dimensions
+ a 16x16 average-luminance grid) via ``oracle/probes/TextClipModeProbe.java``
(72 DPI; luminance math identical to ``RenderProbe`` / ``ImageMaskProbe``).
Pixel-exact parity is impossible across Java2D vs skia/Pillow (anti-aliasing,
sub-pixel coverage), so the same ``MAD<6`` / ``MAXDIFF<60`` gate the other
render oracles calibrated against PDFBox 3.0.7 applies.

The glyph source is the embedded ``DemoType1.pfb`` fixture shown large so
the painted/clipped glyphs fill a sizeable fraction of the page, keeping the
coarse grid discriminating and exercising the real Type 1 outline draw path.
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

# Page sized so the row of large box-outline glyphs fills a good fraction of
# the canvas (keeps the coarse 16x16 grid discriminating).
_PW, _PH, _FS = 160.0, 50.0, 60
_TEXT = b"ABCAB"


def _clip_mode_content(mode: int) -> bytes:
    """Show ``_TEXT`` under text rendering mode ``mode`` (4/5/6) with red
    fill + blue stroke, end the text object (``ET`` commits the glyph clip),
    then fill the whole page green — only the glyph interiors survive."""
    return (
        b"q\nBT\n/F1 %d Tf\n1 0 0 rg\n0 0 1 RG\n1 w\n"
        b"4 6 Td\n%d Tr\n(%s) Tj\nET\n"
        b"0 1 0 rg\n0 0 %d %d re\nf\nQ\n"
        % (_FS, mode, _TEXT, int(_PW), int(_PH))
    )


_CONTENT: dict[str, bytes] = {
    "tr4_fill_clip": _clip_mode_content(4),
    "tr5_stroke_clip": _clip_mode_content(5),
    "tr6_fill_stroke_clip": _clip_mode_content(6),
}

_MODE_LABELS = list(_CONTENT)


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
# fingerprint helpers — must mirror TextClipModeProbe.java's cell mapping
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
    lines = run_probe_text("TextClipModeProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
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


@requires_oracle
@pytest.mark.parametrize("label", _MODE_LABELS, ids=_MODE_LABELS)
def test_text_clip_mode_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each clip ``Tr`` mode (4/5/6) renders identically (within the AA
    tolerance) to Apache PDFBox 3.0.7 at 72 DPI: glyphs painted during the
    text object, then a whole-page green fill confined to the committed
    glyph clip."""
    fixture = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _py_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance — catches a missing clip
    #     (green floods the whole page), a missing paint (clip-only like
    #     mode 7), or a fill/stroke confusion under the clip mode.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — clip-mode render grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_clip_mode_confines_page_fill(tmp_path: Path) -> None:
    """Direct proof the glyph clip is committed at ``ET``: under mode 4 the
    whole-page green fill that follows ``ET`` must be confined to the glyph
    region. The page margins (top-left corner, well outside any glyph) must
    stay white; if the clip were ignored the green fill would flood the
    entire page and the corner would be green."""
    fixture = _build(tmp_path / "tr4.pdf", _CONTENT["tr4_fill_clip"])
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")

    # Top-left corner is page margin (the glyph row sits low-left after the
    # 4 6 Td baseline at a 60-pt font): outside the glyph clip => white.
    corner = img.getpixel((2, 2))
    assert min(corner) > 200, (
        f"clip-mode page-fill not confined: corner {corner} not white — "
        f"the glyph clip from Tr 4 appears not to be committed at ET"
    )

    # Somewhere inside the painted glyph band there must be green pixels
    # (the page-fill survived the clip there). Scan the lower-left region
    # where the large glyphs sit.
    found_green = False
    for x in range(4, img.width // 2):
        for y in range(img.height // 2, img.height):
            r, g, b = img.getpixel((x, y))
            if g > 120 and g > r + 40 and g > b + 40:
                found_green = True
                break
        if found_green:
            break
    assert found_green, (
        "no green pixels inside the glyph band — the whole-page green fill "
        "after ET should survive within the committed glyph clip"
    )


@requires_oracle
def test_clip_mode_differs_from_unclipped_fill(tmp_path: Path) -> None:
    """Guard the gate: rendering the same content with the page-fill clip
    IGNORED (green floods the whole page) must land far outside tolerance
    against the correct oracle render. Confirms the gate detects a dropped
    glyph clip rather than passing both."""
    fixture = _build(tmp_path / "tr4.pdf", _CONTENT["tr4_fill_clip"])
    _dims, java_grid = _oracle_signature(fixture)

    # A whole-page green flood (clip ignored): every cell is green's luma
    # (0.587*255 ~= 150). Compare against the correctly-clipped oracle.
    flood = [150] * (_GRID * _GRID)
    mad, _maxdiff = _mad_maxdiff(java_grid, flood)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a clip-ignored whole-page green flood passes "
        f"the MAD gate (observed mad={mad:.2f})"
    )
