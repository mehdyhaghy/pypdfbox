"""Live PDFBox differential parity for **16-bit-per-component** image decode
through ``PDImageXObject.getImage()`` — the *decode* surface, distinct from the
page-render pipeline pinned by ``test_image_16bit_oracle.py``.

``test_image_16bit_oracle.py`` drives ``PDFRenderer.renderImageWithDPI`` (the
full page-render path: DPI scaling, backdrop fill, Java2D anti-aliasing) and so
can only assert a loose luminance fingerprint. This module drives
``PDImageXObject.getImage()`` directly — the raw 16-bit → 8-bit down-sample with
no AA, no backdrop, no scaling — which lets us pin the down-sample *formula*
EXACTLY (the page-render test cannot, because AA blurs the per-pixel value).

The decisive question this surface settles: PDFBox 3.0.7 down-samples a 16-bit
sample to 8-bit by **linear scaling with rounding** (``round(raw / 65535 *
255)``), NOT by taking the high byte (``raw >> 8``). The two formulas disagree
on values like ``0x00FF`` — high-byte yields ``0`` while linear-rounding yields
``1`` — so the ``uniform_*`` fixtures below pin per-channel EXACT equality on
exactly such discriminating samples. pypdfbox's
``_apply_decode_to_8bit_samples(..., bpc=16)`` already uses the linear-rounding
form; this test is its regression pin against the live oracle.

Cases (each a tiny one-page PDF with raw big-endian 16-bit samples):

* **uniform_00ff_rgb** — solid ``0x00FF`` DeviceRGB fill; the high-byte vs
  linear-rounding discriminator (oracle = 1, high-byte would be 0).
* **uniform_80ff_gray** — solid ``0x80FF`` DeviceGray fill (decodes to 128 on
  every channel).
* **rgb16_gradient** — full-range 0 → 65535 DeviceRGB left→right ramp.
* **gray16_gradient** — full-range 0 → 65535 DeviceGray left→right ramp.
* **rgb16_decode** — the RGB gradient with ``/Decode [1 0 1 0 1 0]`` (every
  channel inverted at the 16-bit range); the ramp must decode reversed.

The ``uniform_*`` fixtures are asserted EXACT per channel (no AA to blur a
single-value fill via ``getImage()``). The gradient fixtures are compared with
a tight per-cell tolerance (the only slack is the 16x16 averaging of the ramp,
not decode error).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Gradient slack: only the 16x16 cell averaging of a smooth ramp, not decode
# error. A treated-as-8-bit / wrong-byte-order misread diverges far past this.
_MAD_TOLERANCE = 2.0
_MAXDIFF_TOLERANCE = 8

_IMG = 32  # source image side, px
_MB = 200  # media-box side, pt


def _channel_grids_from_image(img: Image.Image) -> tuple[list[int], list[int], list[int]]:
    """Per-channel 16x16 average grids (R, G, B) — identical cell mapping to
    ``Image16BitProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell)."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    sums = [[0] * (_GRID * _GRID) for _ in range(3)]
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            r, g, b = pixels[x, y]
            sums[0][idx] += r
            sums[1][idx] += g
            sums[2][idx] += b
            count[idx] += 1
    out = []
    for channel in sums:
        out.append(
            [round(channel[i] / count[i]) if count[i] else 0 for i in range(_GRID * _GRID)]
        )
    return out[0], out[1], out[2]


def _oracle_signature(
    fixture: Path,
) -> tuple[tuple[int, int], list[int], list[int], list[int]]:
    """Run Image16BitProbe on ``fixture`` and parse the first image XObject's
    ``(dims, r_grid, g_grid, b_grid)`` from ``getImage()``."""
    line = run_probe_text("Image16BitProbe", str(fixture)).splitlines()[0]
    # "img page <p> name <name> w <w> h <h> r <...> g <...> b <...>"
    head, _, tail = line.partition(" r ")
    r_part, _, gb = tail.partition(" g ")
    g_part, _, b_part = gb.partition(" b ")
    tokens = head.split()
    width = int(tokens[tokens.index("w") + 1])
    height = int(tokens[tokens.index("h") + 1])
    r_grid = [int(v) for v in r_part.split(",")]
    g_grid = [int(v) for v in g_part.split(",")]
    b_grid = [int(v) for v in b_part.split(",")]
    for grid in (r_grid, g_grid, b_grid):
        assert len(grid) == _GRID * _GRID
    return (width, height), r_grid, g_grid, b_grid


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


def _save_with_image(path: Path, image: PDImageXObject) -> None:
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_uniform_00ff_rgb(path: Path) -> None:
    """Solid ``0x00FF`` DeviceRGB fill — the high-byte vs linear-rounding
    discriminator. ``raw >> 8`` = 0 (wrong); ``round(255/65535*255)`` = 1."""
    samples = [0x00FF] * (_IMG * _IMG * 3)
    _save_with_image(path, _build_raw_image_xobject(_pack16(samples), "DeviceRGB"))


def _build_uniform_80ff_gray(path: Path) -> None:
    """Solid ``0x80FF`` DeviceGray fill — decodes to 128 on every channel
    (both formulas agree at 128 here; pins the DeviceGray decode path)."""
    samples = [0x80FF] * (_IMG * _IMG)
    _save_with_image(path, _build_raw_image_xobject(_pack16(samples), "DeviceGray"))


def _build_rgb16(path: Path, decode: list[float] | None = None) -> None:
    """16-bit DeviceRGB left→right full-range ramp (every channel)."""
    ramp = _ramp16(_IMG)
    samples: list[int] = []
    for _y in range(_IMG):
        for x in range(_IMG):
            v = ramp[x]
            samples.extend((v, v, v))
    _save_with_image(path, _build_raw_image_xobject(_pack16(samples), "DeviceRGB", decode))


def _build_gray16(path: Path) -> None:
    """16-bit DeviceGray left→right full-range ramp."""
    ramp = _ramp16(_IMG)
    samples: list[int] = []
    for _y in range(_IMG):
        samples.extend(ramp)
    _save_with_image(path, _build_raw_image_xobject(_pack16(samples), "DeviceGray"))


def _build_rgb16_decode(path: Path) -> None:
    """16-bit DeviceRGB ramp with /Decode [1 0 1 0 1 0] — decodes reversed."""
    _build_rgb16(path, decode=[1.0, 0.0, 1.0, 0.0, 1.0, 0.0])


_EXACT_BUILDERS = {
    "uniform_00ff_rgb": _build_uniform_00ff_rgb,
    "uniform_80ff_gray": _build_uniform_80ff_gray,
}
_GRADIENT_BUILDERS = {
    "rgb16_gradient": _build_rgb16,
    "gray16_gradient": _build_gray16,
    "rgb16_decode": _build_rgb16_decode,
}


def _first_image_get_image(fixture: Path) -> Image.Image:
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        for name in resources.get_x_object_names():
            xobj = resources.get_x_object(name)
            if isinstance(xobj, PDImageXObject):
                img = xobj.get_image()
                assert img is not None
                return img.convert("RGB")
    raise AssertionError("no image XObject found in fixture")


@requires_oracle
@pytest.mark.parametrize("label", list(_EXACT_BUILDERS), ids=list(_EXACT_BUILDERS))
def test_16bit_get_image_uniform_exact(label: str, tmp_path: Path) -> None:
    """A uniform 16-bit fill decoded via ``getImage()`` has no AA slack, so
    every cell of every channel must match PDFBox EXACTLY — pinning the
    linear-rounding down-sample formula against the high-byte alternative."""
    fixture = tmp_path / f"{label}.pdf"
    _EXACT_BUILDERS[label](fixture)

    (java_w, java_h), jr, jg, jb = _oracle_signature(fixture)
    img = _first_image_get_image(fixture)
    py_w, py_h = img.size
    pr, pg, pb = _channel_grids_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: getImage() dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )
    assert pr == jr, f"{label}: R channel diverges from PDFBox getImage()"
    assert pg == jg, f"{label}: G channel diverges from PDFBox getImage()"
    assert pb == jb, f"{label}: B channel diverges from PDFBox getImage()"


@requires_oracle
@pytest.mark.parametrize("label", list(_GRADIENT_BUILDERS), ids=list(_GRADIENT_BUILDERS))
def test_16bit_get_image_gradient_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Full-range 16-bit gradients decoded via ``getImage()`` must match
    PDFBox within a tight per-cell tolerance (the only slack is the 16x16
    averaging of the ramp — there is no AA in the getImage() decode path)."""
    fixture = tmp_path / f"{label}.pdf"
    _GRADIENT_BUILDERS[label](fixture)

    (java_w, java_h), jr, jg, jb = _oracle_signature(fixture)
    img = _first_image_get_image(fixture)
    py_w, py_h = img.size
    pr, pg, pb = _channel_grids_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: getImage() dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )
    for name, py_grid, java_grid in (("r", pr, jr), ("g", pg, jg), ("b", pb, jb)):
        diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
        mad = sum(diffs) / len(diffs)
        maxdiff = max(diffs)
        assert mad < _MAD_TOLERANCE, (
            f"{label}: {name} channel mean abs cell diff {mad:.2f} >= "
            f"{_MAD_TOLERANCE} (maxdiff={maxdiff}) — 16-bit samples mis-decoded"
        )
        assert maxdiff < _MAXDIFF_TOLERANCE, (
            f"{label}: {name} channel worst cell diff {maxdiff} >= "
            f"{_MAXDIFF_TOLERANCE} (mad={mad:.2f}) — a region diverges far "
            "beyond ramp-averaging"
        )


@requires_oracle
def test_16bit_get_image_decode_reverses_ramp(tmp_path: Path) -> None:
    """Direct proof the 16-bit ``/Decode [1 0 ...]`` is applied at the
    16-bit range: with default decode the left edge is dark and the right
    edge bright; inverted, the left edge must be brighter than the right.
    A renderer that ignored /Decode (or applied it at 8-bit range) would not
    reverse the ramp."""
    fixture = tmp_path / "rgb16_decode.pdf"
    _build_rgb16_decode(fixture)
    img = _first_image_get_image(fixture)
    width, _height = img.size
    px = img.load()
    left = px[0, 0][0]
    right = px[width - 1, 0][0]
    assert left > right + 40, (
        f"inverted-decode ramp not reversed (left={left} right={right}) — "
        "16-bit /Decode appears ignored"
    )
