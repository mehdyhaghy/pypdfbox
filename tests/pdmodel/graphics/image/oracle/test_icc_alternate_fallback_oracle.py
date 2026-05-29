"""Live PDFBox differential parity for **ICCBased image XObjects whose
embedded profile is unparseable**, forcing the ``/Alternate`` fallback.

PDF §8.6.5.5: an image XObject's ``/ColorSpace`` may be ``[/ICCBased
<stream N>]`` where the stream body carries an embedded ICC profile.
When a renderer's CMM cannot build a transform from the embedded
profile, it must fall back to the ``/Alternate`` colour space (or, when
``/Alternate`` is absent, a Device space inferred from ``/N`` ∈ {1, 3,
4} → DeviceGray / DeviceRGB / DeviceCMYK).

``test_icc_image_render_oracle.py`` already pins the *successful* CMM
path (N=3 over a real sRGB profile, N=1 over a minimal valid GRAY
profile) and one fallback case (N=4 over a *valid-header but LUT-less*
CMYK profile that resolves through ``/Alternate /DeviceCMYK`` — a
documented CMM-model divergence). The orthogonal cases this file pins
are NOT covered there:

* **N=3, totally unparseable profile, explicit ``/Alternate
  /DeviceRGB``** — the embedded bytes are not a valid ICC profile at
  all (no ``acsp`` signature, wrong size field), so *both* CMMs (Java
  AWT and Pillow/LittleCMS2) reject it outright and fall back to the
  alternate. Because the alternate is DeviceRGB (a 1:1 sample→sRGB
  identity, no profile maths), parity here is near-exact — unlike the
  CMYK-fallback case which inherits the subtractive-vs-CGATS001 model
  gap. A renderer that swallowed the unparseable profile and rendered
  garbage, or that ignored ``/Alternate`` and dropped to a per-pixel
  re-attempt, lands far outside the gate.
* **N=1, totally unparseable profile, explicit ``/Alternate
  /DeviceGray``** — same fallback for the single-component case; the
  raster decodes straight through DeviceGray (gray→sRGB identity).

Both cases assert exact rendered dimensions plus the proven 16x16
average-luminance fingerprint, gated against ``oracle/probes/Render-
Probe.java`` at 72 DPI. Because the resolved alternates are Device
spaces (no CMM rounding), these use the tight (near-exact) tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Both fallback alternates here are Device spaces (DeviceRGB / DeviceGray),
# whose sample→sRGB conversion is a 1:1 identity with no CMM maths — so
# parity is near-exact, well inside the page-render AA band.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 32  # source image side, px
_MB = 200  # media-box side, pt

# Bytes that are categorically NOT a valid ICC profile: no 'acsp' file
# signature at offset 36, a bogus size field, arbitrary content. Both
# Java AWT's ICC_Profile.getInstance and Pillow's LittleCMS2 reject this
# and the renderer must fall back to /Alternate.
_GARBAGE_PROFILE = b"this-is-not-an-icc-profile-at-all\x00\x01\x02\x03" * 8


def _make_icc_image(
    profile: bytes, n: int, raster: bytes, alternate: str
) -> PDImageXObject:
    """Assemble an ``[/ICCBased <stream N>]`` image XObject over ``raster``
    with an explicit ``/Alternate`` device colour space."""
    icc = COSStream()
    icc.set_int(COSName.get_pdf_name("N"), n)
    icc.set_raw_data(profile)
    icc.set_item("Alternate", COSName.get_pdf_name(alternate))
    cs = COSArray()
    cs.add(COSName.get_pdf_name("ICCBased"))
    cs.add(icc)

    stream = COSStream()
    stream.set_raw_data(bytes(raster))
    image = PDImageXObject(stream)
    image.set_width(_IMG)
    image.set_height(_IMG)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", cs)
    return image


def _save_with_image(path: Path, image: PDImageXObject) -> None:
    """Paint ``image`` into a 120x120 box over a black backdrop and save."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    content = PDPageContentStream(doc, page)
    content.set_non_stroking_color(0.0, 0.0, 0.0)
    content.add_rect(0, 0, _MB, _MB)
    content.fill()
    content.draw_image(image, 40, 60, 120, 120)
    content.close()
    doc.save(str(path))
    doc.close()


def _build_rgb_fallback(path: Path) -> None:
    """``/N 3`` over an unparseable profile + ``/Alternate /DeviceRGB``;
    left→right grayscale ramp, decoded straight through DeviceRGB."""
    samples = bytearray()
    for _y in range(_IMG):
        for x in range(_IMG):
            v = round(x * 255 / (_IMG - 1))
            samples += bytes((v, v, v))
    image = _make_icc_image(_GARBAGE_PROFILE, 3, bytes(samples), "DeviceRGB")
    _save_with_image(path, image)


def _build_gray_fallback(path: Path) -> None:
    """``/N 1`` over an unparseable profile + ``/Alternate /DeviceGray``;
    left→right 0→255 ramp, decoded straight through DeviceGray."""
    samples = bytearray()
    for _y in range(_IMG):
        for x in range(_IMG):
            samples.append(round(x * 255 / (_IMG - 1)))
    image = _make_icc_image(_GARBAGE_PROFILE, 1, bytes(samples), "DeviceGray")
    _save_with_image(path, image)


_BUILDERS = {
    "rgb_alt_fallback": _build_rgb_fallback,
    "gray_alt_fallback": _build_gray_fallback,
}


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


def _render_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_icc_alternate_fallback_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """An ICCBased image whose embedded profile is unparseable must render
    identically to Java PDFBox, which falls back to ``/Alternate`` (a
    Device space) exactly as pypdfbox does."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _render_grid(fixture)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — unparseable ICC profile was not handled "
        f"via the /Alternate fallback the way PDFBox does"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond AA"
    )


@requires_oracle
def test_icc_rgb_fallback_is_smooth_left_to_right_ramp(tmp_path: Path) -> None:
    """Guard against a degenerate handling of the unparseable profile
    (garbage rendered, raster mis-strided, or the fallback dropping to a
    per-pixel re-attempt that scrambles the raster). The N=3 fallback
    image must render as a smooth left→right ramp through DeviceRGB: the
    left third materially darker than the right third."""
    fixture = tmp_path / "rgb_alt_fallback.pdf"
    _build_rgb_fallback(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
    width, height = img.size
    px = img.load()
    left = right = 0
    n = 0
    for y in range(height):
        for x in range(width // 3):
            left += px[x, y]
            right += px[width - 1 - x, y]
            n += 1
    left_avg = left / n
    right_avg = right / n
    assert right_avg - left_avg > 40, (
        "ICCBased unparseable-profile RGB fallback is not a smooth "
        f"left→right ramp (left_avg={left_avg:.1f} right_avg={right_avg:.1f}) "
        "— the /Alternate /DeviceRGB fallback was not applied"
    )
