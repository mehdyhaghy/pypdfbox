"""Live PDFBox differential parity for the RASTER colour-conversion surface
``PDColorSpace.toRGBImage(WritableRaster)`` — distinct from the single-value
``toRGB(float[])`` path covered by ``test_color_space_to_rgb_oracle.py`` and the
``ColorSpaceProbe`` family.

The Java side is ``oracle/probes/ColorImageRgbProbe.java``: for each colour
space it builds a banded ``WritableRaster`` (one band per component), fills it
with a fixed list of 8-bit pixel sample tuples, calls ``toRGBImage``, then reads
each pixel back via ``BufferedImage.getRGB`` and emits canonical
``csname s0 s1 ... -> r g b`` lines (RGB 0-255 ints). The Python side
reconstructs the matching pypdfbox spaces, runs the same raster bytes through
``to_rgb_image``, reads each pixel with Pillow ``getpixel``, and compares.

Only colour spaces whose base/alternate stays out of the JVM colour-management
module are exercised so the comparison is byte-exact:

  * Indexed over DeviceRGB  — fast palette dereference + out-of-range clamp
  * Separation -> DeviceGray — Type-4 tint, ``(int)(result*255)`` truncation in
    the raster fan-out, then DeviceGray channel replication (no CMM)
  * DeviceN (2 colorants) -> DeviceGray — same, two bands

A mismatch here is a real raster-path bug (the single-value ``toRGB`` path is
covered separately, so a divergence isolated to ``toRGBImage`` would otherwise
slip through).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders mirroring the Java probe ----------


def _type4(domain: list[float], rng: list[float], ps: str) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", COSArray.of_cos_floats(domain))
    s.set_item("Range", COSArray.of_cos_floats(rng))
    with s.create_output_stream() as os:
        os.write(ps.encode("ascii"))
    return s


def _indexed_rgb() -> PDColorSpace:
    palette = bytes(
        [
            0, 0, 0,  # 0 black
            255, 0, 0,  # 1 red
            0, 255, 0,  # 2 green
            128, 128, 255,  # 3 light blue
        ]
    )
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(COSInteger.get(3))
    arr.add(COSString(palette))
    cs = PDColorSpace.create(arr)
    assert cs is not None
    return cs


def _separation_gray() -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("PsSpot"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    arr.add(_type4([0.0, 1.0], [0.0, 1.0], "{ 1 exch sub }"))
    return PDSeparation(arr)


def _device_n_gray() -> PDDeviceN:
    names = COSArray()
    names.add(COSName.get_pdf_name("G1"))
    names.add(COSName.get_pdf_name("G2"))
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    arr.add(COSName.get_pdf_name("DeviceGray"))
    arr.add(_type4([0, 1, 0, 1], [0, 1], "{ add 2 div 1 exch sub }"))
    return PDDeviceN(arr)


# Map probe name -> (builder, pixel sample tuples). Pixels MUST match
# ColorImageRgbProbe.java exactly, in the same order.
_BATTERY: dict[str, tuple[object, list[list[int]]]] = {
    "IdxRgbImg": (
        _indexed_rgb(),
        [[0], [1], [2], [3], [4], [7], [255]],
    ),
    "SepGrayImg": (
        _separation_gray(),
        [[0], [1], [64], [127], [128], [191], [254], [255]],
    ),
    "DevNGrayImg": (
        _device_n_gray(),
        [[0, 0], [255, 255], [0, 255], [128, 64], [200, 100]],
    ),
}


def _parse_probe(text: str) -> dict[str, list[tuple[int, int, int]]]:
    """Parse ``csname s0 s1 ... -> r g b`` lines into name -> [(r,g,b), ...]."""
    out: dict[str, list[tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        left, right = line.split("->")
        name = left.split()[0]
        r, g, b = (int(x) for x in right.split())
        out.setdefault(name, []).append((r, g, b))
    return out


def _raster_bytes(pixels: list[list[int]]) -> bytes:
    """Tightly-packed 8-bit sample buffer, pixels row-major (1 row here)."""
    flat: list[int] = []
    for px in pixels:
        flat.extend(px)
    return bytes(flat)


def _image_pixels(
    cs: object, pixels: list[list[int]]
) -> list[tuple[int, int, int]]:
    width = len(pixels)
    img = cs.to_rgb_image(_raster_bytes(pixels), width, 1)  # type: ignore[attr-defined]
    rgb = img.convert("RGB")
    return [rgb.getpixel((x, 0)) for x in range(width)]


@pytest.fixture(scope="module")
def _java_rgb() -> dict[str, list[tuple[int, int, int]]]:
    return _parse_probe(run_probe_text("ColorImageRgbProbe"))


@requires_oracle
@pytest.mark.parametrize("name", list(_BATTERY))
def test_to_rgb_image_matches_pdfbox(
    name: str, _java_rgb: dict[str, list[tuple[int, int, int]]]
) -> None:
    """pypdfbox ``to_rgb_image`` pixels == PDFBox ``toRGBImage`` pixels."""
    cs, pixels = _BATTERY[name]
    java = _java_rgb[name]
    assert len(java) == len(pixels), f"{name}: probe emitted {len(java)} rows"
    py = _image_pixels(cs, pixels)
    for sample, py_rgb, j_rgb in zip(pixels, py, java, strict=True):
        assert py_rgb == j_rgb, (
            f"{name} {sample}: pypdfbox {py_rgb} != PDFBox {j_rgb}"
        )
