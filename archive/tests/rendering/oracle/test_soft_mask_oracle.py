"""Live PDFBox differential parity for image *mask* compositing.

Covers the three mutually-exclusive PDF image-masking mechanisms an image
XObject can carry (PDF 32000-1 §8.9.6) and how the renderer composites each
over a coloured page backdrop:

* **/SMask** (§8.9.6.5) — a separate 8-bit grayscale soft mask supplying a
  per-pixel alpha. Here a left→right alpha gradient over a blue backdrop, so
  the painted region fades from backdrop-blue (transparent) to image-red
  (opaque).
* **explicit /Mask stencil** (§8.9.6.3) — a 1-bit stencil Image XObject
  selecting which base-image samples are painted. With the default
  /Decode [0 1] a sample of 1 masks the pixel out; here the left half (sample
  1) is masked out (green backdrop shows) and the right half (sample 0) is
  painted (image-red).
* **color-key /Mask array** (§8.9.6.4) — a per-component ``[min max]`` sample
  range; pixels whose every component falls inside the range are masked out.
  Here pure-white pixels are keyed out so the blue backdrop shows through.

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a
16x16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). The gate is
the proven discriminator from ``test_render_oracle.py``: a render that ignores
the mask (image painted fully opaque), inverts it, or blanks the page lands
well outside it — measured here, an *ignored* explicit mask scores MAD~6.4
and an *ignored* color-key mask MAD~32, both of which would fail, while the
correct alpha-blended renders score MAD<=0.9.

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
``LosslessFactory`` + content-stream API (no bundled corpus carries all three
mask forms over a coloured backdrop), so the test is self-contained.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_render_oracle.py — comfortably above the AA ceiling
# (correct masked renders measure MAD<=0.9) yet well below the gross-failure
# floor (an ignored explicit mask = MAD~6.4, ignored color-key = MAD~32).
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


def _build_smask_fixture(path: Path) -> None:
    """RGB image (solid red) + grayscale /SMask gradient alpha over a blue
    backdrop. Left edge fully transparent (backdrop blue), right edge fully
    opaque (image red)."""
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    alpha = Image.new("L", (_IMG, _IMG))
    apx = alpha.load()
    for x in range(_IMG):
        col = round(x * 255 / (_IMG - 1))
        for y in range(_IMG):
            apx[x, y] = col
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)

    doc, page = _new_doc_page()
    # LosslessFactory splits an RGBA image into an RGB raster + 8-bit /SMask.
    image = LosslessFactory.create_from_image(doc, rgba)
    assert image.has_soft_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.3, 0.9))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_stencil_mask_fixture(path: Path) -> None:
    """RGB image (solid red) + explicit 1-bit /Mask stencil over a green
    backdrop. With the default /Decode [0 1], sample 1 = masked out and
    sample 0 = painted; here the left half (sample 1) is masked out so the
    green backdrop shows, and the right half (sample 0) paints image-red."""
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    # 1-bit stencil: left half = 1 (masked out), right half = 0 (painted).
    stencil = Image.new("1", (_IMG, _IMG), 0)
    spx = stencil.load()
    for x in range(_IMG):
        val = 1 if x < _IMG // 2 else 0
        for y in range(_IMG):
            spx[x, y] = val

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    mask = LosslessFactory.create_from_image(doc, stencil)
    mask.set_image_mask(True)
    image.set_mask(mask)
    assert image.has_explicit_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.7, 0.2))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_color_key_mask_fixture(path: Path) -> None:
    """RGB image (left half white, right half red) + color-key /Mask array
    that keys out pure white, over a blue backdrop. The keyed-out left half
    shows the backdrop blue; the right half paints image red."""
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    bpx = base.load()
    for x in range(_IMG // 2):
        for y in range(_IMG):
            bpx[x, y] = (255, 255, 255)

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    # Per-component inclusive [min max] ranges keying out pure white.
    image.set_color_key_mask([255, 255, 255, 255, 255, 255])
    assert image.has_color_key_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.3, 0.9))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "smask_gradient": _build_smask_fixture,
    "stencil_mask": _build_stencil_mask_fixture,
    "color_key_mask": _build_color_key_mask_fixture,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_image_mask_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
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

    # (b) Perceptual grid parity within tolerance. A mask that is ignored
    # (opaque), inverted, or blanked lands far outside this gate.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — mask ignored/inverted, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )
    # Tight parity to PDFBox proves the mask is actually composited: a
    # render that ignored/inverted/blanked the mask diverges from the
    # oracle far past this gate (see the dedicated guard test below, where
    # an ignored explicit mask scores MAD~6.4 >= the threshold).


@requires_oracle
def test_ignored_explicit_mask_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the explicit-/Mask fixture *without* the
    mask (image painted fully opaque) must land outside tolerance, proving
    the gate detects an ignored mask rather than passing everything."""
    fixture = tmp_path / "stencil_mask.pdf"
    _build_stencil_mask_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    # Render the *opaque* base image (no mask) by stripping the /Mask entry.
    from pypdfbox.cos import COSName  # noqa: PLC0415

    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        for name in resources.get_x_object_names():
            xobj = resources.get_x_object(name)
            cos = xobj.get_cos_object()
            if cos.get_dictionary_object(COSName.get_pdf_name("Mask")) is not None:
                cos.remove_item(COSName.get_pdf_name("Mask"))
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored explicit mask passes the MAD gate"
    )
