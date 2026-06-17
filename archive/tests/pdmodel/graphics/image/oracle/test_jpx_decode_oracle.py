"""Live PDFBox differential parity for JPXDecode (JPEG 2000) image decode.

Exercises the full image-XObject decode path — ``PDImageXObject.get_image()``
over a ``/Filter /JPXDecode`` stream — against what Apache PDFBox 3.0.7 would
produce on the *same* PDF, via ``oracle/probes/JpxImgProbe.java``.

PDFBox decodes JPEG 2000 through ``javax.imageio``, which needs a registered
JPEG2000 ``ImageReader`` plugin (JAI Image I/O Tools / openjpeg). The pinned
standalone ``pdfbox-app-3.0.7.jar`` bundles **no such reader** — the probe
first asks ``ImageIO`` whether one is registered and, finding none, prints the
canonical line ``NO_JPX_READER`` and exits 0. (This is verified, not assumed:
the probe runs and we branch on its output.) So on this surface the live
differential oracle physically cannot decode a JPX raster — there is nothing
to compare a pypdfbox raster against.

When the oracle reports ``NO_JPX_READER`` (the situation on the pinned jar),
this module skips the Java differential with a clear reason and instead asserts
pypdfbox decodes the JPX to the *expected* intrinsic geometry and a
*non-degenerate* raster whose 16x16 luminance fingerprint matches the
Pillow/imagecodecs ground truth the fixture was encoded from (MAD < 6,
MAXDIFF < 60 — JPEG 2000 is wavelet/lossy). When a reader *is* present (a dev
box with JAI installed), the same tolerance gates the Java-vs-Python grid.

There is no bundled JPX sample PDF (upstream ships none precisely because it
cannot decode them), so each test BUILDS one: a deterministic gradient raster
is JPEG-2000-encoded via Pillow's OpenJPEG bridge, wrapped in a one-page
image-XObject PDF, and saved once. The filter-level byte behaviour (component
count, bpc, endian, post-decode ``/Decode`` handling) is covered exhaustively
in ``tests/filter/test_jpx_decode.py``; this module covers the higher-level
``PDImageXObject.get_image()`` integration the CCITT/DCT oracle tests cover for
their surfaces.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

GRID = 16


def _raster(mode: str, width: int, height: int) -> Image.Image:
    """A deterministic gradient raster in the requested Pillow mode.

    Smooth gradients are wavelet-friendly: JPEG 2000 reproduces them with
    little loss, which keeps the luminance fingerprint stable across decoders
    while the spatial variation still pins down channel order and geometry.
    """
    img = Image.new(mode, (width, height))
    for y in range(height):
        for x in range(width):
            if mode == "L":
                img.putpixel((x, y), (x * 6 + y * 2) % 256)
            elif mode == "RGB":
                img.putpixel(
                    (x, y),
                    ((x * 7) % 256, (y * 9) % 256, ((x + y) * 5) % 256),
                )
            elif mode == "CMYK":
                img.putpixel(
                    (x, y),
                    ((x * 7) % 256, (y * 9) % 256, ((x + y) * 5) % 256, 0),
                )
    return img


def _luminance_grid(img: Image.Image) -> list[float]:
    """16x16 average Rec.601 luminance downsample of ``img``.

    Mirrors ``JpxImgProbe.grid`` exactly: same cell mapping
    (``cx = x * GRID // w``), same Rec.601 weights, row-major, so the Java and
    Python grids are directly comparable.
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    total = [0.0] * (GRID * GRID)
    count = [0] * (GRID * GRID)
    for y in range(h):
        cy = min(y * GRID // h, GRID - 1)
        for x in range(w):
            cx = min(x * GRID // w, GRID - 1)
            r, g, b = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            idx = cy * GRID + cx
            total[idx] += lum
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(GRID * GRID)
    ]


def _build_jpx_pdf(raster: Image.Image, colorspace: str) -> bytes:
    """One-page PDF whose only image is ``raster`` JPEG-2000-encoded under
    ``/JPXDecode`` with the given device ``/ColorSpace``."""
    width, height = raster.size
    buf = io.BytesIO()
    raster.save(buf, format="JPEG2000")
    jp2 = buf.getvalue()

    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    document.add_page(page)
    cos_doc = document.get_document()

    stream = COSStream(cos_doc.scratch_file)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), width)
    stream.set_int(COSName.get_pdf_name("Height"), height)
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name(colorspace)
    )
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("JPXDecode"))
    stream.set_int(COSName.get_pdf_name("Length"), len(jp2))
    stream.set_raw_data(jp2)

    image = PDImageXObject(stream)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)

    content = (f"q {width} 0 0 {height} 10 10 cm /{name.get_name()} Do Q").encode(
        "ascii"
    )
    content_stream = COSStream(cos_doc.scratch_file)
    with content_stream.create_output_stream() as out:
        out.write(content)
    page.get_cos_object().set_item(COSName.get_pdf_name("Contents"), content_stream)

    out_buf = io.BytesIO()
    document.save(out_buf)
    document.close()
    return out_buf.getvalue()


def _pypdfbox_decode(pdf_bytes: bytes):
    """Round-trip-load ``pdf_bytes`` and decode its first image XObject."""
    document = PDDocument.load(pdf_bytes)
    try:
        resources = document.get_page(0).get_resources()
        names = list(resources.get_x_object_names())
        assert names, "fixture PDF has no image XObject"
        image = resources.get_x_object(names[0])
        cs = image.get_color_space()
        cs_name = cs.get_name() if cs is not None else "null"
        pil = image.get_image()
        return (
            image.get_width(),
            image.get_height(),
            image.get_bits_per_component(),
            cs_name,
            pil,
        )
    finally:
        document.close()


def _mad_maxdiff(a: list[float], b: list[float]) -> tuple[float, float]:
    assert len(a) == len(b)
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _parse_probe_grid(line: str) -> list[float]:
    marker = " grid "
    idx = line.index(marker)
    return [float(v) for v in line[idx + len(marker) :].split()]


_CASES = [
    ("L", "DeviceGray", 32, 24),
    ("RGB", "DeviceRGB", 32, 24),
    ("CMYK", "DeviceCMYK", 32, 24),
]


@requires_oracle
@pytest.mark.parametrize(
    ("mode", "colorspace", "width", "height"),
    _CASES,
    ids=["gray", "rgb", "cmyk"],
)
def test_jpx_decode_matches_pdfbox(
    tmp_path, mode: str, colorspace: str, width: int, height: int
) -> None:
    """``PDImageXObject.get_image()`` over a ``/JPXDecode`` stream agrees with
    Apache PDFBox's ``getImage()`` — or, when the pinned jar has no JPX reader,
    decodes correctly against the Pillow/imagecodecs ground truth."""
    source = _raster(mode, width, height)
    pdf = _build_jpx_pdf(source, colorspace)
    pdf_path = tmp_path / "jpx.pdf"
    pdf_path.write_bytes(pdf)

    out = run_probe_text("JpxImgProbe", str(pdf_path)).strip()

    # pypdfbox side (always exercised).
    w, h, bpc, cs, pil = _pypdfbox_decode(pdf)
    assert (w, h) == (width, height)
    assert bpc == 8
    assert cs == colorspace
    assert pil is not None
    assert pil.size == (width, height)
    py_grid = _luminance_grid(pil)

    if out == "NO_JPX_READER":
        # Verified: pinned pdfbox-app-3.0.7.jar registers no JPEG 2000
        # ImageReader, so there is no Java raster to diff against. Fall back to
        # a pypdfbox-correctness check vs the imagecodecs/Pillow source the
        # fixture was encoded from.
        ground_truth = _luminance_grid(source)
        mad, maxdiff = _mad_maxdiff(py_grid, ground_truth)
        assert mad < 6.0, f"JPX decode drifts from source (MAD {mad:.2f})"
        assert maxdiff < 60.0, f"JPX decode max cell drift {maxdiff:.0f}"
        # Non-degenerate: a real gradient, not a flat/blank decode.
        assert max(py_grid) - min(py_grid) > 20.0, "JPX decoded to a flat raster"
        pytest.skip(
            "oracle pdfbox-app-3.0.7.jar has no JPEG 2000 ImageReader "
            "(probe reported NO_JPX_READER); asserted pypdfbox decode vs "
            "imagecodecs/Pillow ground truth instead of a Java differential"
        )

    # A JAI-equipped oracle IS present — do the real Java differential.
    assert out.startswith("jpx "), f"unexpected probe output: {out[:80]!r}"
    fields = out.split()
    jw = int(fields[fields.index("w") + 1])
    jh = int(fields[fields.index("h") + 1])
    jbpc = int(fields[fields.index("bpc") + 1])
    assert (jw, jh) == (width, height)
    assert jbpc == bpc
    java_grid = _parse_probe_grid(out)
    mad, maxdiff = _mad_maxdiff(py_grid, java_grid)
    assert mad < 6.0, f"JPX luminance MAD {mad:.2f} vs PDFBox"
    assert maxdiff < 60.0, f"JPX luminance max cell diff {maxdiff:.0f} vs PDFBox"
