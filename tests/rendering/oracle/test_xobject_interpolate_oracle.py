"""Live PDFBox differential parity for the image-XObject ``/Interpolate``
flag on the ``Do`` paint path (PDF 32000-1 §8.9.5.3).

When a small, sharp-edged raster image XObject is scaled into a much larger
device box via ``cm`` / ``draw_image``, the ``/Interpolate`` flag controls the
resampling filter:

* **/Interpolate false** (the default, PDF 32000-1 Table 89) — upstream PDFBox
  upsamples with **nearest-neighbour** sampling, so the enlarged image shows
  *hard pixel edges* (a blocky checkerboard, each source sample a crisp
  rectangle), not a smooth gradient across sample boundaries.
* **/Interpolate true** — PDFBox may smooth across sample boundaries.

The bug this guards (wave 1446 follow-up): ``_paste_image`` grew an
``interpolate`` parameter wired for *inline* images, but the image-XObject
``Do`` site still pasted positionally → always BILINEAR. So a default
(``/Interpolate false``) checkerboard upscaled into a large box smoothed where
PDFBox renders nearest-neighbour. Threading ``xobject.get_interpolate()`` into
that call site fixes it.

Each fixture is a tiny one-page PDF synthesised in-memory via pypdfbox's
``LosslessFactory`` + content-stream API: a white backdrop, then a 4x4 black/
white checkerboard image XObject drawn into a large box. The ``/Interpolate``
flag is toggled per fixture.

Pixel-EXACT parity is impossible (Pillow vs Java2D resampling — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a 16x16
average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). A bilinear-
smoothed upscale of a checkerboard lands far outside this gate against PDFBox's
nearest-neighbour render — the guard test below measures that divergence
directly by forcing a bilinear render of the nearest-reference fixture.
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
# AA ceiling (a matched nearest-neighbour upscale measures MAD<=2 here) yet
# well below the gross-failure floor (a bilinear-smoothed checkerboard vs the
# nearest reference lands well past the gate — proved by the guard test).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)
_CHECK = 4  # checkerboard source dimension (4x4 samples)
# Draw the tiny raster into nearly the full media box so each 4x4 source sample
# spans ~24x24 device px — a scale at which nearest vs bilinear is obvious.
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
    large box with ``/Interpolate`` set to ``interpolate`` (default is
    false → nearest-neighbour hard edges)."""
    base = _checkerboard()

    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    image = LosslessFactory.create_from_image(doc, base)
    image.set_interpolate(interpolate)
    assert image.get_interpolate() is interpolate

    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(1.0, 1.0, 1.0)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.draw_image(image, _BOX_X, _BOX_Y, _BOX_W, _BOX_H)
    cs.close()
    doc.save(str(path))
    doc.close()


@requires_oracle
def test_interpolate_false_render_matches_pdfbox(tmp_path: Path) -> None:
    """The default (``/Interpolate false``) upscaled checkerboard must match
    Java PDFBox's **nearest-neighbour** render within the fingerprint gate.

    This is the load-bearing parity assertion for the wave-1447 fix: before
    threading ``xobject.get_interpolate()`` into the image-XObject ``Do`` paste
    site, pypdfbox bilinear-smoothed the checkerboard (MAD ~14 vs the oracle)
    while PDFBox painted hard pixel edges; after the fix it matches (MAD <2)."""
    fixture = tmp_path / "interpolate_false.pdf"
    _build_checker_fixture(fixture, interpolate=False)

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

    # (b) Perceptual grid parity within tolerance. A bilinear smooth of the
    # /Interpolate-false checkerboard lands far outside this gate (see guard).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} (maxdiff={maxdiff}) "
        "— /Interpolate false not painted nearest-neighbour, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} (mad={mad:.2f}) "
        "— a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_interpolate_true_smooths_vs_nearest(tmp_path: Path) -> None:
    """Directional control for ``/Interpolate true``: PDFBox *smooths* an
    upscaled checkerboard (PDF 32000-1 §8.9.5.3 — the flag permits, and PDFBox
    applies, interpolation), so its render must differ materially from its own
    **nearest-neighbour** render of the ``/Interpolate false`` fixture.

    We assert the *direction* (smoothed != nearest) rather than pixel-matching
    PDFBox's exact smoothing kernel: PDFBox interpolates with **bicubic**
    sampling while ``_paste_image`` uses Pillow BILINEAR for ``interpolate=True``
    (matched at ~1:1 / downscale, divergent only on extreme upscale). That
    kernel gap is tracked in ``DEFERRED.md`` and is out of scope for the
    nearest-neighbour fix this test anchors."""
    false_fixture = tmp_path / "interpolate_false.pdf"
    true_fixture = tmp_path / "interpolate_true.pdf"
    _build_checker_fixture(false_fixture, interpolate=False)
    _build_checker_fixture(true_fixture, interpolate=True)

    _dims, nearest_grid = _oracle_signature(false_fixture)
    (java_w, java_h), smoothed_grid = _oracle_signature(true_fixture)
    assert (java_w, java_h) == _dims  # same box, same dims

    # PDFBox's smoothed (true) render must diverge materially from its own
    # nearest (false) render — proof /Interpolate true actually smooths.
    diffs = [abs(a - b) for a, b in zip(nearest_grid, smoothed_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"PDFBox /Interpolate true did not smooth vs its nearest render "
        f"(MAD {mad:.2f} < {_MAD_TOLERANCE}) — fixture not exercising the path"
    )


@requires_oracle
def test_forced_bilinear_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: a BILINEAR-smoothed upscale of the checkerboard (the
    exact pre-fix bug — smoothing across sample boundaries where ``/Interpolate
    false`` mandates nearest-neighbour) must land outside tolerance against the
    Java oracle's true nearest-neighbour render of the ``/Interpolate false``
    fixture, proving the gate detects a bilinear-smoothed checkerboard rather
    than passing everything.

    The pre-fix renderer forced BILINEAR regardless of the flag. We reproduce
    that smoothed pixel output independently of the renderer by resizing the
    source checkerboard with BILINEAR to the device box and fingerprinting it,
    then comparing to the FALSE oracle (nearest).
    """
    fixture = tmp_path / "interpolate_false.pdf"
    _build_checker_fixture(fixture, interpolate=False)
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    # Reproduce the pre-fix bilinear paint: the source raster smoothed up to the
    # device box size (the bug discarded interpolate=False and used BILINEAR).
    box_w = round(_BOX_W * java_w / _MB)
    box_h = round(_BOX_H * java_h / _MB)
    smoothed_box = _checkerboard().resize((box_w, box_h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (java_w, java_h), (255, 255, 255))
    # /Interpolate false fixture draws at lower-left (_BOX_X,_BOX_Y); paste the
    # smoothed raster at the same device origin (top-left in image coords).
    px0 = round(_BOX_X * java_w / _MB)
    py0 = java_h - round((_BOX_Y + _BOX_H) * java_h / _MB)
    canvas.paste(smoothed_box, (px0, py0))
    py_grid = _grid_from_image(canvas)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a bilinear-smoothed checkerboard passes the MAD "
        "gate against the oracle's nearest-neighbour render"
    )
