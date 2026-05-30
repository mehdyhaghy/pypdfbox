"""Live PDFBox differential parity for the **zero-width (hairline) stroke**:
a path stroked with ``0 w`` (PDF 32000-1 §8.4.3.2).

The spec says a 0-width line is rendered as the thinnest line the output device
can render — one device pixel — NOT invisible, and NOT scaled away when the CTM
shrinks (or grows) it below a pixel. Apache PDFBox honours this in
``PageDrawer.getStroke``: it floors the device-space pen width to 1 px when
``lineWidth * transformWidth(CTM)`` is sub-pixel. pypdfbox mirrors this in
``PdfRenderer._stroke_path_device_space`` (``if width_px < 1.0: width_px = 1.0``).

Distinct from the sibling stroke surfaces:

* ``test_stroke_geometry_oracle.py`` (wave 1461) — cap / join / miter / dash at
  identity CTM, all with a *non-zero* width.
* ``test_stroke_ctm_width_oracle.py`` (wave 1472) — how a non-zero ``w`` scales
  under a non-identity CTM.

This surface pins the boundary case those two do not touch: ``w == 0``, where
the spec mandates the 1-device-pixel floor rather than a width proportional to
the operand.

Fixtures (one-page PDFs synthesised in-memory, black hairline strokes on white):

* **identity** — ``0 w`` at identity CTM; the cross-shaped path renders as a
  visible 1-px hairline.
* **scaled** — the same ``0 w`` path under ``cm 4 0 0 4`` (a CTM that would
  shrink an honest sub-pixel width even further); ``0 w`` is still floored to
  1 device pixel, so the hairline stays exactly as visible as the identity
  case. A renderer that computed ``0 * scale`` and let the pen vanish would
  render a blank page here.

Pixel-EXACT parity is impossible (Java2D vs skia AA — see ``CHANGES.md`` /
``test_render_oracle.py``); we compare the proven coarse fingerprint: exact
rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against ``oracle/probes/ZeroWidthStrokeProbe.java``
(72 DPI, RenderProbe luminance math). Guard tests prove the ``0 w`` render is
NOT blank (the hairline is genuinely painted) in both the identity and scaled
cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same whole-page render gate as test_stroke_ctm_width_oracle.py /
# test_render_oracle.py — comfortably above the Java2D-vs-skia AA ceiling yet
# well below the gross-failure floor (a vanished 0-width stroke renders a blank
# page, diverging far past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 80.0  # square page (== px at 72 DPI)


def _content_for(label: str) -> bytes:
    """Content stream for one zero-width-stroke fixture. A cross-shaped black
    path stroked with ``0 w``; the geometry lands well inside the 80x80 page in
    both the identity and scaled cases."""
    if label == "identity":
        # 0 w at identity: a horizontal + vertical hairline through the page.
        return b"0 w 0 0 0 RG\n15 40 m 65 40 l S\n40 15 m 40 65 l S\n"
    if label == "scaled":
        # Same cross under cm 4x (coords divided by 4 to land in the same
        # device region). 0 w is floored to 1 device px regardless of the CTM.
        return (
            b"4 0 0 4 0 0 cm\n0 w 0 0 0 RG\n"
            b"3.75 10 m 16.25 10 l S\n10 3.75 m 10 16.25 l S\n"
        )
    raise ValueError(label)  # pragma: no cover


def _build(label: str, out: Path) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(_content_for(label))
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


_LABELS = ["identity", "scaled"]


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror ZeroWidthStrokeProbe.java's cell mapping
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
    """Run ZeroWidthStrokeProbe on page 0 and parse its (dims, 16x16 grid).
    The probe emits the grid comma-separated (see the probe header)."""
    lines = run_probe_text("ZeroWidthStrokeProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _dark_pixel_count(fixture: Path) -> int:
    """Count rendered pixels darker than mid-grey — the painted hairline."""
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
    px = img.load()
    width, height = img.size
    return sum(
        1 for y in range(height) for x in range(width) if px[x, y] < 128
    )


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_zero_width_stroke_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each zero-width-stroke variant must match Java PDFBox's render of the
    same fixture within the 16x16 fingerprint gate — the ``0 w`` hairline is a
    visible 1-device-pixel line in both the identity and scaled cases."""
    fixture = _build(label, tmp_path / f"{label}.pdf")

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

    # (b) Perceptual grid parity within tolerance.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — zero-width stroke mis-rendered, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_zero_width_stroke_is_not_blank(label: str, tmp_path: Path) -> None:
    """Guard the gate: a ``0 w`` stroke must paint a visible hairline, NOT
    vanish. A renderer that computed ``0 * scale`` and let the pen disappear
    would render a blank (all-white) page — caught here for both the identity
    and the scaled CTM, where the naive scaling would shrink the pen even
    further below a pixel."""
    fixture = _build(label, tmp_path / f"{label}.pdf")
    dark = _dark_pixel_count(fixture)
    # The cross has two ~50-pt-long device segments; a 1-px hairline paints on
    # the order of a hundred dark pixels. Anything near zero means it vanished.
    assert dark > 50, (
        f"{label}: only {dark} dark pixels — the 0-width stroke appears to "
        "have vanished instead of rendering as a 1-device-pixel hairline"
    )
