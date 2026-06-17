"""Live PDFBox differential parity for an image XObject carrying **both** a
color-key ``/Mask`` array (PDF 32000-1 §8.9.6.4) AND an ``/SMask`` stream
(§11.6.5.1).

The dual-mask oracle (``test_dual_mask_smask_oracle.py``) covers the
*stencil-stream* ``/Mask`` + ``/SMask`` case. This file covers the **color-key
array** form combined with ``/SMask``.

Wave 1491 finding (verified against the live 3.0.7 oracle): although
``PDImageXObject.getImage`` *does* pass ``getColorKeyMask()`` into
``SampledImageReader.getRGBImage`` (so the base ARGB raster carries the
color-key alpha), the subsequent ``applyMask`` step for a ``/SMask``
**overwrites the alpha band wholesale** —
``raster.setSamples(0, y, width, 1, 3, samples)`` (Java
``PDImageXObject.applyMask`` line 679) — replacing, not multiplying, the
color-key alpha. So when a color-key ``/Mask`` array and an ``/SMask`` coexist,
the color-key has **no net effect**: the SMask alpha wins outright. (This
*corrects* the wave-1449 DEFERRED hypothesis, which read the source as
"color-key always applies" without accounting for the wholesale alpha
overwrite in ``applyMask``.)

We drive ``PDImageXObject.getImage()`` directly via
``oracle/probes/ColorKeyMaskProbe.java`` (the same probe the non-RGB color-key
oracle uses) and compare an 8x8 average-RGBA fingerprint: the colour channels
loosely (Pillow vs Java2D sample rounding), the alpha plane tightly — the
combined-mask alpha must equal the pure ``/SMask`` alpha, exactly as Java's.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 8
_CHANNELS = 4  # R,G,B,A per cell
_RGB_MAD_TOLERANCE = 8.0
_RGB_MAXDIFF_TOLERANCE = 70
_ALPHA_TOLERANCE = 28  # per-cell avg alpha diff (AA-soft cell edges + ramp)

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt


def _grid_from_rgba(img: Image.Image) -> list[int]:
    """8x8 average-RGBA fingerprint — identical cell mapping to
    ``ColorKeyMaskProbe.java`` (four channels per cell, row-major)."""
    rgba = img.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    sums = [[0, 0, 0, 0] for _ in range(_GRID * _GRID)]
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            r, g, b, a = pixels[x, y]
            sums[idx][0] += r
            sums[idx][1] += g
            sums[idx][2] += b
            sums[idx][3] += a
            count[idx] += 1
    out: list[int] = []
    for i in range(_GRID * _GRID):
        c = count[i] if count[i] else 1
        out.extend(round(sums[i][ch] / c) for ch in range(_CHANNELS))
    return out


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run ColorKeyMaskProbe and parse its (dims, 8x8 RGBA grid)."""
    lines = run_probe_text("ColorKeyMaskProbe", str(fixture)).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID * _CHANNELS
    return (width, height), grid


def _split_channels(grid: list[int]) -> tuple[list[int], list[int]]:
    rgb: list[int] = []
    alpha: list[int] = []
    for i in range(0, len(grid), _CHANNELS):
        rgb.extend(grid[i : i + 3])
        alpha.append(grid[i + 3])
    return rgb, alpha


def _smask_ramp(_img: int = _IMG) -> Image.Image:
    """Top→bottom 255..0 luminance ramp used as the 8-bit /SMask alpha."""
    smask_img = Image.new("L", (_img, _img))
    spx = smask_img.load()
    for y in range(_img):
        val = round((_img - 1 - y) * 255 / (_img - 1))
        for x in range(_img):
            spx[x, y] = val
    return smask_img


def _build_color_key_smask_fixture(path: Path) -> None:
    """Author one DeviceGray image XObject carrying BOTH:

    * a color-key ``/Mask`` ``[0 60]`` that on its OWN would key out the left
      (dark sample-20) half, and
    * an 8-bit luminosity ``/SMask`` top→bottom alpha ramp.

    Per the wave-1491 finding, ``applyMask`` overwrites the alpha band with the
    SMask ramp, so the color-key has no net effect and the final alpha is the
    pure ramp across the whole image (left and right halves identical). The
    fixture deliberately keys the LEFT half so that any port that *honoured*
    the color-key under /SMask (e.g. by multiplying alphas) would zero the left
    half and diverge sharply from Java's pure-ramp reference."""
    base = Image.new("L", (_IMG, _IMG), 220)
    bpx = base.load()
    for x in range(_IMG // 2):
        for y in range(_IMG):
            bpx[x, y] = 20  # left half: dark sample, inside the [0 60] key

    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    image = LosslessFactory.create_from_image(doc, base)
    assert image.get_color_space().get_name() == "DeviceGray"
    image.set_color_key_mask([0, 60])
    assert image.has_color_key_mask()

    smask = LosslessFactory.create_from_image(doc, _smask_ramp())
    image.set_soft_mask(smask)
    assert image.has_soft_mask()

    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _first_image(doc: PDDocument) -> PDImageXObject:
    resources = doc.get_page(0).get_resources()
    return next(
        xobj
        for name in resources.get_x_object_names()
        if isinstance(xobj := resources.get_x_object(name), PDImageXObject)
    )


@requires_oracle
def test_color_key_mask_with_smask_matches_pdfbox(tmp_path: Path) -> None:
    """``getImage()`` on an image with color-key ``/Mask`` + ``/SMask`` must
    match Java PDFBox's ARGB within the 8x8 fingerprint gate. Per Java's
    ``applyMask`` (alpha-band overwrite), the result is the pure SMask ramp —
    the color-key is discarded — and pypdfbox must reproduce that."""
    fixture = tmp_path / "color_key_smask.pdf"
    _build_color_key_smask_fixture(fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        py_img = _first_image(doc).get_image()
    assert py_img is not None
    py_w, py_h = py_img.size
    py_grid = _grid_from_rgba(py_img)

    assert (py_w, py_h) == (java_w, java_h), (
        "color-key+/SMask: getImage() dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    java_rgb, java_alpha = _split_channels(java_grid)
    py_rgb, py_alpha = _split_channels(py_grid)

    # Alpha plane — the real result. Tight gate: the combined mask must read the
    # pure SMask ramp (color-key discarded), so the left half (color-keyed in
    # isolation) reads the SAME alpha as the right half. A port that honoured
    # the color-key under /SMask would zero the left half and blow this gate.
    adiffs = [abs(a - b) for a, b in zip(java_alpha, py_alpha, strict=True)]
    amax = max(adiffs)
    assert amax < _ALPHA_TOLERANCE, (
        f"color-key+/SMask: worst per-cell alpha diff {amax} >= {_ALPHA_TOLERANCE} "
        f"— color-key not discarded under /SMask (java alpha={java_alpha}, "
        f"py alpha={py_alpha})"
    )

    rdiffs = [abs(a - b) for a, b in zip(java_rgb, py_rgb, strict=True)]
    rmad = sum(rdiffs) / len(rdiffs)
    rmax = max(rdiffs)
    assert rmad < _RGB_MAD_TOLERANCE, (
        f"color-key+/SMask: mean abs RGB cell diff {rmad:.2f} >= {_RGB_MAD_TOLERANCE}"
    )
    assert rmax < _RGB_MAXDIFF_TOLERANCE, (
        f"color-key+/SMask: worst RGB cell diff {rmax} >= {_RGB_MAXDIFF_TOLERANCE}"
    )


@requires_oracle
def test_color_key_discarded_left_half_follows_ramp(tmp_path: Path) -> None:
    """Guard the gate: the color-keyed LEFT half must follow the SMask ramp
    (NOT be keyed transparent), proving pypdfbox discards the color-key under
    /SMask exactly as Java does. Top cells (ramp opaque) read ~255 on both the
    keyed-left and un-keyed-right columns; bottom cells (ramp transparent) read
    ~0 on both."""
    fixture = tmp_path / "color_key_smask.pdf"
    _build_color_key_smask_fixture(fixture)
    with PDDocument.load(fixture) as doc:
        py_img = _first_image(doc).get_image()
    _rgb, alpha = _split_channels(_grid_from_rgba(py_img))

    # 8x8 grid, row-major. Row 0 = top (ramp opaque). The color-keyed top-left
    # cell (index 0) must follow the ramp (~255), NOT be keyed to 0.
    assert alpha[0] > 200, (
        f"top-left cell keyed transparent (alpha={alpha[0]}) — color-key NOT "
        "discarded under /SMask"
    )
    assert alpha[7] > 200, f"top-right cell not opaque (alpha={alpha[7]})"
    # Bottom row (index 56..63) = ramp transparent on BOTH halves.
    assert alpha[56] < 40, f"bottom-left cell not transparent (alpha={alpha[56]})"
    assert alpha[63] < 40, f"bottom-right cell not transparent (alpha={alpha[63]})"
