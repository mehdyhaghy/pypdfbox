"""Live PDFBox differential parity for the ``PDFRenderer`` DPI-scaling +
``ImageType`` surface — the raster *dimensions* a given DPI/scale produces and
the *pixel format* (channel layout) each ``ImageType`` selects.

This is the orthogonal companion to ``test_render_oracle.py`` (which pins the
72-DPI luminance fingerprint of real fixtures) and ``test_color_image_rgb_-
oracle.py`` (raster colour conversion). Neither sweeps DPI nor exercises the
three-arg ``renderImageWithDPI(page, dpi, ImageType)`` overload. The facets
pinned here:

* **DPI -> dimensions.** width = ``(int)(mediaBoxWidthPt / 72 * dpi)``,
  height likewise (Java ``(int)`` cast == floor for the positive sizes here).
  We render the same page at 36 / 72 / 96 / 150 DPI and assert the rendered
  ``(width, height)`` matches PDFBox *exactly* at every DPI. A mismatch is a
  real bug (wrong rounding, scale off-by-one), not anti-aliasing.
* **ImageType -> pixel format.** ``ImageType.{RGB,ARGB,GRAY,BINARY}`` selects
  the Pillow mode (``RGB`` / ``RGBA`` / ``L`` / ``1``) mirroring the upstream
  ``BufferedImage.TYPE_*`` flavour. We assert the returned image's Pillow mode
  matches the expected channel layout for each type.

Pixel-EXACT parity across Java2D vs Pillow is impossible (see
``test_render_oracle.py`` / ``CHANGES.md``), so the perceptual check reuses the
proven coarse 16x16 average-luminance fingerprint, gated at ``MAD < 6`` /
``MAXDIFF < 60`` against ``oracle/probes/RenderImageTypeProbe.java``.

**Scope of the grid gate.** The luminance fingerprint is compared only for the
``RGB`` and ``ARGB`` types, where both renderers rasterise into an RGB(A)
buffer and the grid math (Rec.601 luma) means the same thing on each side.
``GRAY`` and ``BINARY`` are pinned on the *pixel-format* facet only
(dimensions + channel layout / Pillow mode), NOT the luminance values: Apache
PDFBox renders those types directly into a Java AWT ``TYPE_BYTE_GRAY`` /
``TYPE_BYTE_BINARY`` ``BufferedImage`` whose ICC gray ColorModel applies a
gamma-2.2 TRC at paint time (a flat ``rgb(217,217,217)`` fill lands at gray
238, ``rgb(128,128,128)`` at 188 — measured, not Rec.601). pypdfbox converts
the finished RGB raster with Pillow ``convert("L")`` / ``convert("1")`` (plain
Rec.601, no ICC), so the gray *values* diverge by construction. That is a
documented colorspace-management divergence in the same family as the
Java2D-vs-Pillow anti-aliasing divergence (see ``CHANGES.md``); reproducing it
byte-for-byte would require shipping Java's ICC gray transform / CMM, which is
out of scope. The channel-layout parity (1-band ``L`` / 1-bit ``1``) IS the
load-bearing assertion for those two types.

The fixture is a tiny one-page PDF synthesised in-memory: a *fully opaque*
backdrop plus large flat colour blocks (no thin AA edges). The full-page
opaque fill matters for the ARGB case — with no transparent pixels the ARGB
luminance grid lines up with the RGB grid on both sides (PDFBox's ``getRGB``
returns 0 for transparent pixels whereas Pillow's RGBA->L ignores alpha, so a
partly-transparent page would diverge in the background by construction, not
by a real bug).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.image_type import ImageType
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Media box deliberately fractional so the (int) truncation of the scaled
# dimensions is genuinely exercised at every DPI (not a clean multiple).
_MB_W = 153.5
_MB_H = 211.25

# DPI sweep + ImageType list — MUST match RenderImageTypeProbe.java exactly
# (same order, same values) so the line-by-line zip lines up.
_DPIS = [36.0, 72.0, 96.0, 150.0]
_TYPES = [ImageType.RGB, ImageType.ARGB, ImageType.GRAY, ImageType.BINARY]

# Expected Pillow mode per ImageType (the channel layout the surface selects).
_EXPECTED_MODE = {
    ImageType.RGB: "RGB",
    ImageType.ARGB: "RGBA",
    ImageType.GRAY: "L",
    ImageType.BINARY: "1",
}

# Number of channels (bands) the returned image must carry per type — the
# load-bearing pixel-format assertion (matches PDFBox's BufferedImage band
# count: RGB=3, ARGB=4, GRAY=1, BINARY=1).
_EXPECTED_BANDS = {
    ImageType.RGB: 3,
    ImageType.ARGB: 4,
    ImageType.GRAY: 1,
    ImageType.BINARY: 1,
}

# The grid (luminance) gate is meaningful only where both renderers rasterise
# in RGB(A) space — see the module docstring "Scope of the grid gate".
_GRID_GATED_TYPES = frozenset({ImageType.RGB, ImageType.ARGB})


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderImageTypeProbe.java`` (integer-division of pixel coord over image
    size, clamped to the last cell). Matches PIL's "L" Rec.601 weights."""
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


def _build_fixture(path: Path) -> None:
    """One-page PDF: full-page opaque backdrop + large flat colour blocks.

    No thin strokes or small text, so a 1-bit BINARY dither and a GRAY
    conversion of these flat regions still average back to within the
    luminance gate when downsampled to 16x16.
    """
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB_W, _MB_H))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    # Opaque light-gray backdrop covering the whole page (no transparency).
    cs.set_non_stroking_color_rgb(0.85, 0.85, 0.85)
    cs.add_rect(0, 0, _MB_W, _MB_H)
    cs.fill()
    # A dark-blue block, lower-left quadrant.
    cs.set_non_stroking_color_rgb(0.10, 0.15, 0.55)
    cs.add_rect(15, 15, _MB_W / 2 - 20, _MB_H / 2 - 20)
    cs.fill()
    # A mid-red block, upper-right quadrant.
    cs.set_non_stroking_color_rgb(0.75, 0.20, 0.20)
    cs.add_rect(_MB_W / 2 + 5, _MB_H / 2 + 5, _MB_W / 2 - 20, _MB_H / 2 - 20)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


def _oracle_lines(
    fixture: Path,
) -> list[tuple[float, str, int, int, int, int, list[int]]]:
    """Run RenderImageTypeProbe on page 0; parse one tuple per (dpi, type).

    Each line: ``<dpi> <typeName> <w> <h> <awtType> <numBands>: <comma grid>``.
    Returns ``(dpi, typeName, w, h, awtType, numBands, grid)`` per line.
    """
    out = run_probe_text("RenderImageTypeProbe", str(fixture), "0")
    parsed: list[tuple[float, str, int, int, int, int, list[int]]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        head, _, grid_str = line.partition(":")
        dpi_s, type_name, w_s, h_s, awt_s, bands_s = head.split()
        grid = [int(v) for v in grid_str.strip().split(",")]
        assert len(grid) == _GRID * _GRID
        parsed.append(
            (
                float(dpi_s),
                type_name,
                int(w_s),
                int(h_s),
                int(awt_s),
                int(bands_s),
                grid,
            )
        )
    return parsed


@requires_oracle
def test_dpi_and_image_type_match_pdfbox(tmp_path: Path) -> None:
    """Across the DPI sweep x every ImageType, pypdfbox must match PDFBox's
    raster dimensions exactly, return the expected channel layout per type,
    and land within the luminance fingerprint gate."""
    fixture = tmp_path / "dpi_image_type.pdf"
    _build_fixture(fixture)
    oracle = _oracle_lines(fixture)
    # 4 DPIs x 4 ImageTypes.
    assert len(oracle) == len(_DPIS) * len(_TYPES)

    with PDDocument.load(fixture) as doc:
        renderer = PDFRenderer(doc)
        cursor = 0
        for dpi in _DPIS:
            for itype in _TYPES:
                (
                    o_dpi,
                    o_type,
                    o_w,
                    o_h,
                    _o_awt,
                    o_bands,
                    o_grid,
                ) = oracle[cursor]
                cursor += 1
                # Probe order sanity: each python (dpi, type) lines up with
                # the matching oracle line.
                assert o_dpi == pytest.approx(dpi)
                assert o_type == itype.name

                img = renderer.render_image_with_dpi(0, dpi, itype)

                # (a) exact raster dimensions for this DPI.
                py_w, py_h = img.size
                assert (py_w, py_h) == (o_w, o_h), (
                    f"dpi={dpi} type={itype.name}: dims diverge "
                    f"pypdfbox={py_w}x{py_h} java={o_w}x{o_h}"
                )

                # (b) channel layout matches the requested ImageType — both
                # the Pillow mode and the PDFBox band count.
                assert img.mode == _EXPECTED_MODE[itype], (
                    f"dpi={dpi} type={itype.name}: pillow mode {img.mode!r} "
                    f"!= expected {_EXPECTED_MODE[itype]!r}"
                )
                assert o_bands == _EXPECTED_BANDS[itype], (
                    f"dpi={dpi} type={itype.name}: oracle band count {o_bands} "
                    f"!= expected {_EXPECTED_BANDS[itype]}"
                )
                assert len(img.getbands()) == _EXPECTED_BANDS[itype], (
                    f"dpi={dpi} type={itype.name}: pypdfbox bands "
                    f"{img.getbands()} != expected {_EXPECTED_BANDS[itype]}"
                )

                # (c) perceptual grid parity within tolerance — only for the
                # RGB(A) types (see module docstring "Scope of the grid gate";
                # GRAY/BINARY carry Java's ICC gray-TRC luminance which is a
                # documented colorspace divergence, not a parity bug).
                if itype not in _GRID_GATED_TYPES:
                    continue
                py_grid = _grid_from_image(img)
                diffs = [abs(a - b) for a, b in zip(o_grid, py_grid, strict=True)]
                mad = sum(diffs) / len(diffs)
                maxdiff = max(diffs)
                assert mad < _MAD_TOLERANCE, (
                    f"dpi={dpi} type={itype.name}: MAD {mad:.2f} >= "
                    f"{_MAD_TOLERANCE} (maxdiff={maxdiff})"
                )
                assert maxdiff < _MAXDIFF_TOLERANCE, (
                    f"dpi={dpi} type={itype.name}: maxdiff {maxdiff} >= "
                    f"{_MAXDIFF_TOLERANCE} (mad={mad:.2f})"
                )


@requires_oracle
def test_dpi_dimensions_scale_with_truncation(tmp_path: Path) -> None:
    """Direct proof of the (int)-truncation dimension formula: the RGB render
    width/height at each DPI equals ``int(mediaBoxPt / 72 * dpi)`` and matches
    the oracle. This isolates the scaling math from the pixel-format facet."""
    fixture = tmp_path / "dpi_image_type.pdf"
    _build_fixture(fixture)
    oracle = {
        (dpi, name): (w, h)
        for (dpi, name, w, h, _awt, _bands, _grid) in _oracle_lines(fixture)
    }

    with PDDocument.load(fixture) as doc:
        renderer = PDFRenderer(doc)
        for dpi in _DPIS:
            scale = dpi / 72.0
            expected_w = max(1, int(_MB_W * scale))
            expected_h = max(1, int(_MB_H * scale))
            o_w, o_h = oracle[(dpi, "RGB")]
            assert (o_w, o_h) == (expected_w, expected_h), (
                f"dpi={dpi}: oracle dims {o_w}x{o_h} != formula "
                f"{expected_w}x{expected_h}"
            )
            img = renderer.render_image_with_dpi(0, dpi, ImageType.RGB)
            assert img.size == (expected_w, expected_h)
