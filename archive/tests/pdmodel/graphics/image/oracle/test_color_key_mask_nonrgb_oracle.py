"""Live PDFBox differential parity for color-key ``/Mask`` (PDF 32000-1
§8.9.6.4) on a **non-RGB** image — the GRAY / CMYK / Indexed facet not covered
by the wave-1456 RGB color-key oracle.

Color-key masking keys out every pixel whose *raw colour-component samples*
(one per component, in the image's native colour space, **before** colour
conversion to sRGB) all fall inside the corresponding inclusive ``[min max]``
pair of the ``/Mask`` array. The range pairs are expressed in raw-sample units
``[0, 2**BitsPerComponent - 1]``:

* **DeviceGray** — one pair over the single gray sample (``[min max]``).
* **DeviceCMYK** — four pairs over the C,M,Y,K samples.
* **Indexed** — one pair over the *palette index* itself (not the looked-up
  colour), honouring the image's own ``/Decode`` index remap.

A renderer that (as the pre-wave-1470 port did) compares the *converted sRGB*
pixels against the first three range pairs keys the wrong pixels — or, for a
1- or 4-component image, never matches the range length at all and silently
keeps every pixel opaque. Both diverge far past the gate against Java PDFBox's
``PDImageXObject.getImage()`` (which composites the keyed samples as alpha 0).

We drive ``getImage()`` directly via ``oracle/probes/ColorKeyMaskProbe.java``
and compare an 8x8 average-RGBA fingerprint. Pixel-exact parity is impossible
(Pillow vs Java2D sample rounding), so we gate the colour channels loosely
(MAD/MAXDIFF) but pin the **alpha** plane tightly — the keyed cells must read
~0 alpha and the opaque cells ~255, which is the actual behaviour under test.

Fixtures are tiny one-page PDFs synthesised in-memory (no committed binaries):
DeviceGray + Indexed via pypdfbox's ``LosslessFactory``; DeviceCMYK via a raw
hand-built raster Image XObject.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 8
_CHANNELS = 4  # R,G,B,A per cell
# Colour channels: AA / sample-rounding tolerance, same scale as the other
# image-mask oracles. Alpha: tight — a keyed cell is fully transparent and an
# opaque cell fully opaque, so the per-cell alpha average is unambiguous.
_RGB_MAD_TOLERANCE = 8.0
_RGB_MAXDIFF_TOLERANCE = 70
_ALPHA_TOLERANCE = 24  # per-cell avg alpha diff (allows AA-soft cell edges)

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt


def _grid_from_rgba(img: Image.Image) -> list[int]:
    """8x8 average-RGBA fingerprint — identical cell mapping to
    ``ColorKeyMaskProbe.java``. Four channels per cell, row-major,
    consecutive (r,g,b,a)."""
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


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _emit(doc: PDDocument, page: PDPage, image: PDImageXObject, path: Path) -> None:
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_gray_fixture(path: Path) -> None:
    """8-bit DeviceGray image: left half dark (sample 20), right half bright
    (sample 220). Color-key ``[0 60]`` keys out every gray sample in 0..60 —
    i.e. the left (dark) half goes transparent, the right (bright) half stays
    opaque. The keyed range is over the SINGLE gray sample; a renderer that
    needed a 3-pair (RGB) range would never match the 1-pair array and keep
    the whole image opaque."""
    base = Image.new("L", (_IMG, _IMG), 220)
    bpx = base.load()
    for x in range(_IMG // 2):
        for y in range(_IMG):
            bpx[x, y] = 20
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    assert image.get_color_space().get_name() == "DeviceGray"
    image.set_color_key_mask([0, 60])
    assert image.has_color_key_mask()
    _emit(doc, page, image, path)


def _build_cmyk_fixture(path: Path) -> None:
    """Raw 8-bit DeviceCMYK image, hand-built. Left half is a near-pure-cyan
    sample ``(C=240, M=10, Y=10, K=5)``; right half is a magenta-ish sample
    ``(C=10, M=240, Y=10, K=5)``. Color-key
    ``[200 255  0 40  0 40  0 40]`` keys out the left (cyan) half — high C, low
    M/Y/K — and leaves the right half opaque (its M is 240, outside ``0..40``).
    The range is FOUR pairs over the CMYK samples; comparing converted sRGB
    against the first three pairs keys the wrong pixels."""
    width = height = _IMG
    raster = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            off = (y * width + x) * 4
            if x < width // 2:
                raster[off : off + 4] = bytes((240, 10, 10, 5))
            else:
                raster[off : off + 4] = bytes((10, 240, 10, 5))

    doc, page = _new_doc_page()
    stream = doc.get_document().create_cos_stream()
    with stream.create_output_stream(COSName.get_pdf_name("FlateDecode")) as out:
        out.write(bytes(raster))
    image = PDImageXObject(stream)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceCMYK")
    image.set_color_key_mask([200, 255, 0, 40, 0, 40, 0, 40])
    assert image.has_color_key_mask()
    _emit(doc, page, image, path)


def _build_indexed_fixture(path: Path) -> None:
    """Indexed (palette) image. Palette index 0 → red, 1 → green, 2 → blue.
    Left third index 0, middle third index 1, right third index 2. Color-key
    ``[1 1]`` keys out the MIDDLE third (the green palette entry) — keyed on
    the integer index, NOT on the looked-up green RGB. A renderer that keyed
    on the converted sRGB green pixels against a 3-pair range would have to be
    given green's RGB; the 1-pair index range proves the comparison is against
    the raw index sample."""
    palette = [255, 0, 0, 0, 200, 0, 0, 0, 255] + [0] * (256 * 3 - 9)
    base = Image.new("P", (_IMG, _IMG))
    base.putpalette(palette)
    bpx = base.load()
    third = _IMG // 3
    for x in range(_IMG):
        idx = 0 if x < third else (1 if x < 2 * third else 2)
        for y in range(_IMG):
            bpx[x, y] = idx

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    assert image.get_color_space().get_name() == "Indexed"
    image.set_color_key_mask([1, 1])
    assert image.has_color_key_mask()
    _emit(doc, page, image, path)


_BUILDERS = {
    "gray": _build_gray_fixture,
    "cmyk": _build_cmyk_fixture,
    "indexed": _build_indexed_fixture,
}


def _split_channels(grid: list[int]) -> tuple[list[int], list[int]]:
    """Split a flat (r,g,b,a per cell) grid into (rgb list, alpha list)."""
    rgb: list[int] = []
    alpha: list[int] = []
    for i in range(0, len(grid), _CHANNELS):
        rgb.extend(grid[i : i + 3])
        alpha.append(grid[i + 3])
    return rgb, alpha


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_color_key_mask_nonrgb_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each non-RGB color-key variant must match Java PDFBox's
    ``getImage()`` ARGB within the 8x8 fingerprint gate — colour channels
    loosely, the alpha plane tightly."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        image = None
        for name in resources.get_x_object_names():
            xobj = resources.get_x_object(name)
            if isinstance(xobj, PDImageXObject):
                image = xobj
                break
        assert image is not None
        py_img = image.get_image()
    assert py_img is not None
    py_w, py_h = py_img.size
    py_grid = _grid_from_rgba(py_img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: getImage() dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    java_rgb, java_alpha = _split_channels(java_grid)
    py_rgb, py_alpha = _split_channels(py_grid)

    # (a) Alpha plane — the actual color-key result. Tight gate.
    adiffs = [abs(a - b) for a, b in zip(java_alpha, py_alpha, strict=True)]
    amax = max(adiffs)
    assert amax < _ALPHA_TOLERANCE, (
        f"{label}: worst per-cell alpha diff {amax} >= {_ALPHA_TOLERANCE} — "
        f"color-key keyed the wrong pixels (java alpha={java_alpha}, "
        f"py alpha={py_alpha})"
    )

    # (b) Colour channels — loose AA / sample-rounding gate. DeviceCMYK is
    # exempt from the colour comparison: the residual gap is the documented
    # subtractive-vs-ICC CMYK->RGB transform divergence (see CHANGES.md /
    # _dct_jpeg_to_rgb docstring), a colour-cluster matter, not a mask bug —
    # the alpha plane above is what proves the color-key facet for CMYK.
    if label != "cmyk":
        rdiffs = [abs(a - b) for a, b in zip(java_rgb, py_rgb, strict=True)]
        rmad = sum(rdiffs) / len(rdiffs)
        rmax = max(rdiffs)
        assert rmad < _RGB_MAD_TOLERANCE, (
            f"{label}: mean abs RGB cell diff {rmad:.2f} >= {_RGB_MAD_TOLERANCE}"
        )
        assert rmax < _RGB_MAXDIFF_TOLERANCE, (
            f"{label}: worst RGB cell diff {rmax} >= {_RGB_MAXDIFF_TOLERANCE}"
        )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_color_key_actually_keys_some_cells_transparent(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: prove the color-key actually turns SOME cells
    transparent and leaves OTHERS opaque (a no-op renderer that left every
    pixel opaque — the pre-wave-1470 behaviour for 1/4-component images —
    would have a uniformly-255 alpha plane and fail this)."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        image = next(
            xobj
            for name in resources.get_x_object_names()
            if isinstance(xobj := resources.get_x_object(name), PDImageXObject)
        )
        py_img = image.get_image()
    _rgb, alpha = _split_channels(_grid_from_rgba(py_img))
    assert min(alpha) < 32, f"{label}: no cell keyed transparent (alpha min={min(alpha)})"
    assert max(alpha) > 224, f"{label}: no cell left opaque (alpha max={max(alpha)})"
