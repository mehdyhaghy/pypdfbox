"""Live PDFBox differential parity for the image-XObject ``/Interpolate true``
smoothing kernel — wave 1448 follow-up to the wave-1447 nearest-neighbour fix.

When ``/Interpolate true`` is set (PDF 32000-1 §8.9.5.3), upstream PDFBox
upsamples with ``RenderingHints.VALUE_INTERPOLATION_BICUBIC``; the previous
``_paste_image`` smoothing branch used ``Image.Resampling.BILINEAR`` instead.
A bilinear kernel matches bicubic at ~1:1 / downscale, but on an aggressive
upscale of a low-resolution raster the divergence is visible: a 4x4 hard-edged
checkerboard scaled into a ~92x92pt box measured MAD ~14.4 (BILINEAR pypdfbox
vs PDFBox bicubic) before the fix, dropping to MAD ~3.1 with BICUBIC (Pillow
filter sweep confirmed BICUBIC wins; LANCZOS close at ~3.4; BILINEAR ~14.4).

Each fixture is a tiny one-page PDF synthesised in-memory via pypdfbox's
``LosslessFactory`` + content-stream API: a white backdrop, then a 4x4 black/
white checkerboard image XObject drawn into a large box with
``/Interpolate true``.

Pixel-EXACT parity is impossible (Pillow vs Java2D resampling — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a
16x16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). A BILINEAR-
forced upscale of the same fixture lands outside the gate against PDFBox's
bicubic render — directly proving the kernel choice (not just "any smooth")
matters.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the sibling render oracles — comfortably above the resampler
# AA ceiling (bicubic pypdfbox vs PDFBox bicubic measures MAD ~3 here on this
# fixture) yet well below the gross-failure floor (a BILINEAR smooth diverges
# at MAD ~14 — proved by the guard test).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)
_CHECK = 4  # checkerboard source dimension (4x4 samples)
# Draw the tiny raster into nearly the full media box so each 4x4 source sample
# spans ~23x23 device px — the upscale ratio where bicubic vs bilinear
# diverges visibly while sharing the same overall smoothing direction.
_BOX_X, _BOX_Y, _BOX_W, _BOX_H = 4, 4, 92, 92


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


def _checkerboard() -> Image.Image:
    """A 4x4 hard-edged black/white checkerboard (sharp sample boundaries)."""
    img = Image.new("RGB", (_CHECK, _CHECK), (255, 255, 255))
    px = img.load()
    for y in range(_CHECK):
        for x in range(_CHECK):
            px[x, y] = (0, 0, 0) if (x + y) % 2 == 0 else (255, 255, 255)
    return img


def _build_checker_fixture(path: Path, *, interpolate: bool) -> None:
    """White backdrop, then a 4x4 checkerboard image XObject scaled into a
    large box with ``/Interpolate`` set to ``interpolate``."""
    base = _checkerboard()

    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, _MB, _MB))
        doc.add_page(page)

        image = LosslessFactory.create_from_image(doc, base)
        image.set_interpolate(interpolate)
        assert image.get_interpolate() is interpolate

        cs = PDPageContentStream(doc, page)
        try:
            cs.set_non_stroking_color(1.0, 1.0, 1.0)
            cs.add_rect(0, 0, _MB, _MB)
            cs.fill()
            cs.draw_image(image, _BOX_X, _BOX_Y, _BOX_W, _BOX_H)
        finally:
            cs.close()
        doc.save(str(path))
    finally:
        doc.close()


@requires_oracle
def test_interpolate_true_render_matches_pdfbox(tmp_path: Path) -> None:
    """``/Interpolate true`` upscaled checkerboard must match Java PDFBox's
    **bicubic** render within the fingerprint gate.

    Load-bearing parity assertion for the wave-1448 fix: before switching the
    ``interpolate=True`` branch of ``_paste_image`` from BILINEAR to BICUBIC,
    pypdfbox diverged from PDFBox's bicubic at MAD ~14 (well past the gate of
    6); after the switch it lands at MAD ~3, comfortably inside."""
    fixture = tmp_path / "interpolate_true.pdf"
    _build_checker_fixture(fixture, interpolate=True)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance. A BILINEAR smooth (the
    # pre-fix kernel) lands far outside this gate (see guard).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} (maxdiff={maxdiff}) "
        "— /Interpolate true not painted with a bicubic-equivalent kernel"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} (mad={mad:.2f}) "
        "— a region diverges far beyond resampling AA"
    )


@requires_oracle
def test_forced_bilinear_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: a BILINEAR-smoothed upscale of the checkerboard (the
    exact pre-fix kernel) must land outside tolerance against the Java oracle's
    bicubic render of the ``/Interpolate true`` fixture, proving the gate
    actually distinguishes the two kernels rather than passing any smooth.

    The pre-fix renderer used BILINEAR. We reproduce that smoothed pixel output
    independently of the renderer by resizing the source checkerboard with
    BILINEAR to the device box and fingerprinting it, then comparing to the
    TRUE oracle (bicubic).
    """
    fixture = tmp_path / "interpolate_true.pdf"
    _build_checker_fixture(fixture, interpolate=True)
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    # Reproduce the pre-fix bilinear paint: the source raster smoothed up to
    # the device box size with BILINEAR (the bug used the wrong kernel).
    box_w = round(_BOX_W * java_w / _MB)
    box_h = round(_BOX_H * java_h / _MB)
    smoothed_box = _checkerboard().resize((box_w, box_h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (java_w, java_h), (255, 255, 255))
    # /Interpolate true fixture draws at lower-left (_BOX_X,_BOX_Y); paste the
    # smoothed raster at the same device origin (top-left in image coords).
    px0 = round(_BOX_X * java_w / _MB)
    py0 = java_h - round((_BOX_Y + _BOX_H) * java_h / _MB)
    canvas.paste(smoothed_box, (px0, py0))
    py_grid = _grid_from_image(canvas)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a BILINEAR-smoothed checkerboard passes the MAD "
        "gate against the oracle's bicubic render"
    )
