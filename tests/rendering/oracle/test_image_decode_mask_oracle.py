"""Live PDFBox differential parity for image ``/Decode`` inversion and the
stencil ``/ImageMask true`` paint path (PDF 32000-1 §8.9.5.2 / §8.9.5.4).

This complements ``test_soft_mask_oracle.py`` (which covers /SMask, the
explicit /Mask stencil-on-another-image, and the color-key /Mask array). The
two cases here exercise the remaining image-paint behaviours:

* **/Decode inversion on a normal image** (§8.9.5.2) — a DeviceRGB raster
  carrying ``/Decode [1 0 1 0 1 0]`` maps every sample ``s`` to ``1 - s``, so
  a solid mid-blue source is rendered as its complement. Proves the renderer
  applies the per-component /Decode transform rather than painting the raw
  samples.
* **/ImageMask true stencil painted in the fill colour** (§8.9.5.4) — a 1-bpc
  stencil XObject is not a colour image: its samples are an alpha matte and the
  *current non-stroking colour* fills the opaque positions while the backdrop
  shows through the transparent ones. With the default ``/Decode [0 1]`` a
  sample of 0 paints; ``/Decode [1 0]`` reverses the polarity. We render both
  polarities of the same stencil (left half / right half painted in fill red
  over a green backdrop) and confirm each matches PDFBox — an ignored or
  inverted stencil lands far outside the gate.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA — see ``CHANGES.md`` /
``test_render_oracle.py``), so we compare the proven coarse fingerprint: exact
rendered dimensions plus a 16x16 average-luminance grid, gated at ``MAD < 6`` /
``MAXDIFF < 60`` against ``oracle/probes/RenderProbe.java`` (72 DPI render). A
guard test renders each fixture with the masking/decode behaviour stripped and
asserts it scores materially worse, proving the gate detects a regression.

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
``LosslessFactory`` + content-stream API (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_render_oracle.py / test_soft_mask_oracle.py — comfortably
# above the AA ceiling yet well below the gross-failure floor (an ignored
# /Decode or a stencil painted with the wrong polarity diverges far past it;
# see the dedicated guard tests below).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell)."""
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


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run RenderProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _fill_backdrop(cs: PDPageContentStream, rgb: tuple[float, float, float]) -> None:
    cs.set_non_stroking_color(*rgb)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()


def _build_decode_invert_fixture(path: Path) -> None:
    """Solid mid-blue DeviceRGB image carrying /Decode [1 0 1 0 1 0] over a
    white backdrop. The /Decode array maps sample s -> 1 - s, so the painted
    region renders as the colour complement (mid-orange-yellow), not blue."""
    base = Image.new("RGB", (_IMG, _IMG), (40, 60, 200))

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    # Per-component inverting /Decode for a 3-component DeviceRGB raster.
    image.set_decode([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_stencil_paint_fixture(path: Path, *, invert: bool) -> None:
    """A 1-bpc /ImageMask true stencil painted in fill-red over a green
    backdrop. With the default /Decode [0 1] a sample of 0 paints (opaque) and
    1 is transparent; /Decode [1 0] reverses that. The source stencil has its
    left half = 0 and right half = 1, so:

    * invert=False (/Decode [0 1]): left half paints red, right half = backdrop.
    * invert=True  (/Decode [1 0]): right half paints red, left half = backdrop.
    """
    stencil = Image.new("1", (_IMG, _IMG), 0)
    spx = stencil.load()
    for x in range(_IMG):
        val = 0 if x < _IMG // 2 else 1
        for y in range(_IMG):
            spx[x, y] = val

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, stencil)
    image.set_image_mask(True)
    if invert:
        image.set_decode([1.0, 0.0])
    assert image.is_stencil()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.7, 0.2))
    # Current non-stroking colour fills the opaque stencil positions.
    cs.set_non_stroking_color(0.85, 0.12, 0.12)
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "decode_invert_rgb": _build_decode_invert_fixture,
    "stencil_paint_default": lambda p: _build_stencil_paint_fixture(p, invert=False),
    "stencil_paint_inverted": lambda p: _build_stencil_paint_fixture(p, invert=True),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_image_decode_mask_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

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

    # (b) Perceptual grid parity within tolerance. An ignored /Decode, a
    # stencil painted opaque, or a stencil painted with reversed polarity all
    # land far outside this gate (see the guard tests below).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — /Decode or stencil mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_ignored_decode_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the /Decode-inverting fixture *without* the
    /Decode entry (raw blue samples painted) must land outside tolerance,
    proving the gate detects an ignored /Decode rather than passing both."""
    fixture = tmp_path / "decode_invert_rgb.pdf"
    _build_decode_invert_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        for name in resources.get_x_object_names():
            xobj = resources.get_x_object(name)
            cos = xobj.get_cos_object()
            if cos.get_dictionary_object(COSName.get_pdf_name("Decode")) is not None:
                cos.remove_item(COSName.get_pdf_name("Decode"))
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored /Decode passes the MAD gate"
    )


@requires_oracle
def test_inverted_stencil_polarity_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: comparing the default-polarity stencil render against
    the *inverted*-polarity oracle signature (red on the opposite half) must
    land outside tolerance, proving the gate detects a flipped stencil
    polarity rather than passing either orientation."""
    default_fixture = tmp_path / "stencil_paint_default.pdf"
    inverted_fixture = tmp_path / "stencil_paint_inverted.pdf"
    _build_stencil_paint_fixture(default_fixture, invert=False)
    _build_stencil_paint_fixture(inverted_fixture, invert=True)

    # Oracle signature for the INVERTED fixture (red on the right half).
    _dims, java_inverted_grid = _oracle_signature(inverted_fixture)

    # pypdfbox render of the DEFAULT fixture (red on the left half).
    with PDDocument.load(default_fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_default_grid = _grid_from_image(img)

    diffs = [
        abs(a - b)
        for a, b in zip(java_inverted_grid, py_default_grid, strict=True)
    ]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a stencil rendered with the wrong /Decode "
        "polarity passes the MAD gate"
    )
