"""Live PDFBox differential parity for image-XObject ``/Mask`` and ``/SMask``
compositing — the orthogonal cases not covered by ``test_soft_mask_oracle.py``
or ``test_image_decode_mask_oracle.py`` (PDF 32000-1 §8.9.6 / §11.6.5.3).

Wave 1455 surface decision: ``test_soft_mask_oracle.py`` already pins one
representative each of (a) /SMask alpha gradient, (b) explicit /Mask stencil
default polarity, and (c) color-key /Mask exact-white. ``test_image_decode_-
mask_oracle.py`` pins /ImageMask stencil polarity (the *image itself* a
stencil) and /Decode inversion. The orthogonal cases for the /Mask + /SMask
surface that are NOT covered there:

* **Color-key /Mask RANGE** (§8.9.6.4) — ``[200 255 200 255 200 255]`` keys
  out a *range* of near-white pixels (not just exact ``[255 255 …]``). The
  existing color_key oracle pins only the degenerate single-value case.
* **/Mask color-key + /SMask both present** — the spec (§8.9.6.3 note) says
  ``/SMask`` takes precedence and ``/Mask`` is ignored. A renderer that runs
  both (e.g. composes the color-key alpha on top of the SMask alpha) lands
  far outside the gate against the SMask-only oracle.
* **Explicit /Mask stream with /Decode [1 0]** (§8.9.6.3) — the stencil
  mask's *own* /Decode array reverses which mask sample masks the pixel out.
  ``test_image_decode_mask_oracle.py`` pins the /Decode-on-/ImageMask path
  (the base image being a stencil); this pins /Decode-on-the-mask-image
  (the base image carries an explicit /Mask whose own /Decode is inverted).
* **Explicit /Mask circle stencil** — exercises the resize-nearest-neighbour
  path on a non-axis-aligned mask shape so a renderer that applies bilinear
  filtering to the mask plane (which would blur the circle edge) lands
  outside the gate.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA — see ``CHANGES.md`` /
``test_render_oracle.py``), so we compare the proven coarse fingerprint:
exact rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against ``oracle/probes/ImageMaskProbe.java``
(72 DPI render — identical luminance math to ``RenderProbe``, dedicated
named probe per the wave brief).

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
# Same gate as test_soft_mask_oracle.py / test_image_decode_mask_oracle.py —
# comfortably above the AA ceiling yet well below the gross-failure floor
# (an ignored mask, inverted stencil polarity, or SMask-yielding-to-color-key
# bug all diverge far past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``ImageMaskProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell). Matches PIL's "L" Rec.601 weights."""
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
    """Run ImageMaskProbe on page 0 and parse its (dims, 16x16 grid).

    The probe emits the grid as a comma-separated single line (see
    ``oracle/probes/ImageMaskProbe.java`` header); ``RenderProbe`` emits
    space-separated. Using a dedicated probe keeps the parsing format
    obvious from the probe-name in the test."""
    lines = run_probe_text("ImageMaskProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
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


def _build_color_key_range_fixture(path: Path) -> None:
    """RGB image with a near-white block (left half) + a brightly-coloured
    block (right half), keyed out via ``/Mask [200 255 200 255 200 255]``.
    The keyed range catches every near-white sample (>=200 in all channels);
    the right-half mid-saturation magenta falls outside the range and stays
    opaque. Renders over a blue backdrop.

    An ignored color-key /Mask paints the near-white block too (no
    transparency); applying the range INCLUSIVELY but with the wrong
    direction (e.g. >= max only) paints the wrong pixels — both score
    far outside the gate against the oracle's correct render.
    """
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    bpx = base.load()
    for x in range(_IMG // 2):
        for y in range(_IMG):
            # Pixels in [200..255] — caught by the color-key range.
            bpx[x, y] = (230, 240, 220)
    for x in range(_IMG // 2, _IMG):
        for y in range(_IMG):
            # Mid magenta; channels all outside [200..255].
            bpx[x, y] = (180, 40, 160)

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    image.set_color_key_mask([200, 255, 200, 255, 200, 255])
    assert image.has_color_key_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.3, 0.9))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_smask_wins_over_color_key_fixture(path: Path) -> None:
    """RGB image (solid red) carrying BOTH a color-key /Mask
    ``[255 255 255 255 255 255]`` (which would key nothing, since the image
    has no white pixels) AND a soft /SMask gradient. Per spec, /SMask
    takes precedence; a renderer that also applies the color-key (or one
    that lets /Mask win) lands outside the gate.

    The color-key here is intentionally chosen to mask NO pixels in the
    actual raster — what we're guarding against is *evaluating the
    color-key at all* (e.g. applying it as an extra alpha layer on top
    of the SMask, or letting it preempt the SMask). With /SMask in
    charge, the render is the same left-transparent→right-opaque
    gradient as the /SMask-only case.
    """
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
    # LosslessFactory splits RGBA into RGB + /SMask gradient.
    image = LosslessFactory.create_from_image(doc, rgba)
    assert image.has_soft_mask()
    # Attach an additional color-key /Mask — the spec says /SMask wins.
    image.set_color_key_mask([255, 255, 255, 255, 255, 255])
    assert image.has_color_key_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.3, 0.9))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_explicit_mask_inverted_decode_fixture(path: Path) -> None:
    """RGB image (solid red) + explicit 1-bit /Mask stencil whose stencil
    image carries ``/Decode [1 0]``, which reverses the per-sample mask
    polarity. Stencil left half = 1, right half = 0. With default
    /Decode [0 1] the LEFT half would be masked out; with /Decode [1 0]
    the polarity is inverted so the RIGHT half is masked out and the
    LEFT half paints image-red over a green backdrop.
    """
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    # 1-bit stencil: left half = 1, right half = 0.
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
    # Invert the mask's own /Decode so sample 1 paints / sample 0 masks.
    mask.set_decode([1.0, 0.0])
    image.set_mask(mask)
    assert image.has_explicit_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.7, 0.2))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_explicit_mask_circle_fixture(path: Path) -> None:
    """RGB image (solid blue) + explicit 1-bit /Mask stencil shaped as a
    centred circle. A circle is non-axis-aligned: a renderer that applies
    bilinear filtering to the mask plane (rather than the spec-mandated
    nearest-neighbour sample selection) blurs the edge, perturbing the
    coarse luminance grid past the gate. Renders over a yellow backdrop
    so the masked-out background contributes a distinct luminance from
    both the image (blue, low luma) and a pure-white renderer artefact."""
    base = Image.new("RGB", (_IMG, _IMG), (30, 60, 220))
    stencil = Image.new("1", (_IMG, _IMG), 1)  # default to masked-out
    spx = stencil.load()
    cx = _IMG / 2 - 0.5
    cy = _IMG / 2 - 0.5
    radius = _IMG * 0.4
    r2 = radius * radius
    for x in range(_IMG):
        for y in range(_IMG):
            dx = x - cx
            dy = y - cy
            spx[x, y] = 0 if (dx * dx + dy * dy) <= r2 else 1

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    mask = LosslessFactory.create_from_image(doc, stencil)
    mask.set_image_mask(True)
    image.set_mask(mask)
    assert image.has_explicit_mask()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.95, 0.85, 0.15))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "color_key_range": _build_color_key_range_fixture,
    "smask_wins_over_color_key": _build_smask_wins_over_color_key_fixture,
    "explicit_mask_inverted_decode": _build_explicit_mask_inverted_decode_fixture,
    "explicit_mask_circle": _build_explicit_mask_circle_fixture,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_image_mask_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each orthogonal /Mask + /SMask variant must match Java PDFBox's
    render of the same fixture within the 16x16 fingerprint gate."""
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

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — mask path mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_smask_wins_over_color_key_proof(tmp_path: Path) -> None:
    """Direct proof that the SMask-precedence case is actually exercising
    /SMask (not silently dropping both masks): the rendered alpha gradient
    must visibly fade left→right over the blue backdrop. A renderer that
    let /Mask color-key preempt and ignored /SMask would paint the image
    fully opaque (no fade, no blue showing at the left)."""
    fixture = tmp_path / "smask_wins_over_color_key.pdf"
    _build_smask_wins_over_color_key_fixture(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # Sample columns near the painted region (40..160 pt at 72 DPI).
    # mid-height inside the painted area.
    y = 120
    left = img.getpixel((50, y))
    right = img.getpixel((150, y))
    # Left edge should be close to the blue backdrop (b dominates).
    assert left[2] > left[0] + 40, (
        f"SMask-wins fixture left edge {left} not blue-dominant — /SMask appears ignored"
    )
    # Right edge should be close to image-red (r dominates).
    assert right[0] > right[2] + 40, (
        f"SMask-wins fixture right edge {right} not red-dominant — /SMask appears ignored"
    )


@requires_oracle
def test_inverted_stencil_decode_polarity_proof(tmp_path: Path) -> None:
    """Direct proof the mask's /Decode [1 0] is applied: with the default
    polarity the LEFT half (stencil sample 1) is masked out (green shows);
    with /Decode [1 0] the polarity flips so the RIGHT half is masked out
    (green shows) and the LEFT half paints image-red. A renderer that
    ignores the mask's /Decode renders identical to the default-polarity
    case."""
    fixture = tmp_path / "explicit_mask_inverted_decode.pdf"
    _build_explicit_mask_inverted_decode_fixture(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    y = 120
    left = img.getpixel((50, y))
    right = img.getpixel((150, y))
    # With /Decode [1 0]: left = image-red (r dominant), right = green backdrop.
    assert left[0] > left[1] + 40 and left[0] > left[2] + 40, (
        f"inverted-decode left edge {left} not red-dominant — mask /Decode ignored"
    )
    assert right[1] > right[0] + 40 and right[1] > right[2] + 40, (
        f"inverted-decode right edge {right} not green-dominant — mask /Decode ignored"
    )


@requires_oracle
def test_ignored_color_key_range_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the color-key-range fixture *without* the
    /Mask entry (the near-white block paints opaquely instead of letting
    the blue backdrop show through) must land outside tolerance against
    the correct oracle render, proving the gate detects an ignored
    color-key range rather than passing both."""
    fixture = tmp_path / "color_key_range.pdf"
    _build_color_key_range_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    mask_key = COSName.get_pdf_name("Mask")
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        for name in resources.get_x_object_names():
            xobj = resources.get_x_object(name)
            cos = xobj.get_cos_object()
            if cos.get_dictionary_object(mask_key) is not None:
                cos.remove_item(mask_key)
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored color-key range passes the MAD gate "
        f"(observed mad={mad:.2f})"
    )
