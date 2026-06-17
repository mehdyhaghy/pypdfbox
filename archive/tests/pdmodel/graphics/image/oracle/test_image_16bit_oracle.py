"""Live PDFBox differential parity for **16-bit-per-component** image XObjects.

Complements the 8-bit / sub-byte coverage elsewhere in this package. PDF
§8.9.5.2 permits ``/BitsPerComponent 16``; samples are stored big-endian
(two bytes, high byte first). PDFBox reads the 16-bit raster and down-shifts
to 8-bit for rendering (``raw / 65535 * 255``). pypdfbox must reproduce that
exact mapping — a degenerate misread (wrong byte order, treating the bytes as
8-bit samples, or dropping the image entirely) shifts luminance materially.

Cases (each a tiny one-page PDF authored with raw big-endian 16-bit samples):

* **rgb16_gradient** — a 16-bit DeviceRGB left→right grayscale-ish gradient
  spanning the *full* 16-bit range (0 → 65535), so 8-bit truncation is
  exercised across the whole tonal range. A treat-as-8-bit misread would read
  every *other* byte as a pixel and halve the effective width / scramble the
  ramp.
* **gray16_gradient** — a 16-bit DeviceGray left→right 0 → 65535 ramp.
* **rgb16_decode** — the same RGB gradient but with ``/Decode
  [1 0 1 0 1 0]`` (invert every channel); the ramp must render reversed.
* **gray16_smask** — an 8-bit RGB base painted through a **16-bit DeviceGray
  /SMask** carrying a left→right 0 → 65535 alpha ramp.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA + down-shift rounding),
so we compare the same coarse fingerprint the page-render oracle uses: exact
rendered dimensions plus a 16x16 average-luminance grid, gated at ``MAD < 6`` /
``MAXDIFF < 60`` against ``oracle/probes/RenderProbe.java`` (72 DPI).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 32  # source image side, px
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


def _pack16(samples: list[int]) -> bytes:
    """Big-endian (high byte first) 16-bit sample stream."""
    return b"".join(struct.pack(">H", s & 0xFFFF) for s in samples)


def _ramp16(width: int) -> list[int]:
    """Per-column 0 → 65535 ramp value (full 16-bit range)."""
    return [round(x * 65535 / (width - 1)) for x in range(width)]


def _build_raw_image_xobject(
    raw: bytes, cs_name: str, decode: list[float] | None = None
) -> PDImageXObject:
    """Assemble a raw-sample 16-bit image XObject COS dict."""
    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(_IMG)
    image.set_height(_IMG)
    image.set_bits_per_component(16)
    stream.set_item("ColorSpace", COSName.get_pdf_name(cs_name))
    if decode is not None:
        arr = COSArray()
        for v in decode:
            arr.add(COSFloat(v))
        stream.set_item("Decode", arr)
    return image


def _build_rgb16(path: Path, decode: list[float] | None = None) -> None:
    """16-bit DeviceRGB left→right gradient (full 16-bit range on every
    channel) over a black backdrop."""
    ramp = _ramp16(_IMG)
    samples: list[int] = []
    for _y in range(_IMG):
        for x in range(_IMG):
            v = ramp[x]
            samples.extend((v, v, v))
    image = _build_raw_image_xobject(_pack16(samples), "DeviceRGB", decode)

    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(0.0, 0.0, 0.0)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_gray16(path: Path) -> None:
    """16-bit DeviceGray left→right 0 → 65535 ramp over a black backdrop."""
    ramp = _ramp16(_IMG)
    samples: list[int] = []
    for _y in range(_IMG):
        samples.extend(ramp)
    image = _build_raw_image_xobject(_pack16(samples), "DeviceGray")

    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(0.0, 0.0, 0.0)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_rgb16_decode(path: Path) -> None:
    """16-bit DeviceRGB gradient with /Decode [1 0 1 0 1 0] (invert every
    channel) — the ramp must render reversed."""
    _build_rgb16(path, decode=[1.0, 0.0, 1.0, 0.0, 1.0, 0.0])


def _build_gray16_smask(path: Path) -> None:
    """8-bit solid-red RGB base painted through a 16-bit DeviceGray /SMask
    carrying a left→right 0 → 65535 alpha ramp, over a black backdrop. The
    soft mask's 16-bit samples must down-shift to 8-bit alpha; a misread
    would invert or scramble the fade."""
    base = Image.new("RGB", (_IMG, _IMG), (255, 255, 255))

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)

    ramp = _ramp16(_IMG)
    samples: list[int] = []
    for _y in range(_IMG):
        samples.extend(ramp)
    smask = _build_raw_image_xobject(_pack16(samples), "DeviceGray")
    image.get_cos_object().set_item(
        COSName.get_pdf_name("SMask"), smask.get_cos_object()
    )

    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(0.0, 0.0, 0.0)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "rgb16_gradient": _build_rgb16,
    "gray16_gradient": _build_gray16,
    "rgb16_decode": _build_rgb16_decode,
    "gray16_smask": _build_gray16_smask,
}


def _render_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_16bit_image_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
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
        f"(maxdiff={maxdiff}) — 16-bit samples mis-unpacked, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond down-shift rounding"
    )


@requires_oracle
def test_16bit_rgb_gradient_is_smooth_and_nondegenerate(tmp_path: Path) -> None:
    """Guard against a degenerate (treat-as-8-bit) misread. The full-range
    16-bit RGB gradient must render as a *smooth* left→right ramp: the mean
    luminance of the image's left third must be materially darker than its
    right third (a treat-as-8-bit misread reads every other byte as a pixel,
    which scrambles the ordering and collapses this monotonic difference)."""
    fixture = tmp_path / "rgb16_gradient.pdf"
    _build_rgb16(fixture)
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
        "16-bit RGB gradient is not a smooth left→right ramp "
        f"(left_avg={left_avg:.1f} right_avg={right_avg:.1f}) — "
        "samples likely mis-unpacked (treated as 8-bit / wrong byte order)"
    )
