"""Live PDFBox differential parity for JBIG2 image-XObject decode.

Exercises the full image-XObject decode path — ``PDImageXObject.get_image()``
over a ``/Filter /JBIG2Decode`` stream — against Apache PDFBox 3.0.7's
``PDImageXObject.getImage()`` on the *same* PDF. The bundled
``pdfbox-app-3.0.7.jar`` includes the Apache JBIG2 ImageIO plugin
(``org.apache.pdfbox.jbig2.JBIG2ImageReaderSpi``), so Java's ``getImage()``
decodes JBIG2 out of the box.

There is no bundled JBIG2 sample PDF, so each test BUILDS one: a real
standalone ``.jb2`` codestream (``tests/jbig2/fixtures/``) is wrapped as a
one-page image XObject (DeviceGray, ``BitsPerComponent`` 1, ``Width`` / ``Height``
taken from the decoded page bitmap). Both libraries then decode that single
artefact through ``ImageExtractProbe.java``.

The decoded raster is bilevel, fully deterministic on both sides (pypdfbox's
``/JBIG2Decode`` filter is bit-exact with PDFBox's ``JBIG2Filter`` — verified
separately at the filter level), so the 16x16 luminance fingerprint is asserted
**exactly equal** (worst cell delta 0), not merely within tolerance. The
polarity axis is the key thing this guards: JBIG2 pixel 1 = black, but the image
pipeline wants sample 0 = black; an inverted decode would flip the fingerprint
to a photographic negative.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_FIXTURES = Path(__file__).resolve().parents[4] / "jbig2" / "fixtures"


# ---------------------------------------------------------------------------
# fixture construction
# ---------------------------------------------------------------------------


def _bitmap_dims(jb2_bytes: bytes) -> tuple[int, int]:
    """Decode the page bitmap to recover the intrinsic image dimensions."""
    bitmap = JBIG2Document(ImageInputStream(jb2_bytes)).get_page(1).get_bitmap()
    return bitmap.get_width(), bitmap.get_height()


def _build_jbig2_pdf(jb2_bytes: bytes, width: int, height: int) -> bytes:
    """Wrap ``jb2_bytes`` as a one-page DeviceGray /JBIG2Decode image PDF."""
    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    document.add_page(page)
    cos_doc = document.get_document()

    stream = COSStream(cos_doc.scratch_file)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), width)
    stream.set_int(COSName.get_pdf_name("Height"), height)
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 1)
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("JBIG2Decode"))
    stream.set_int(COSName.get_pdf_name("Length"), len(jb2_bytes))
    stream.set_raw_data(jb2_bytes)

    image = PDImageXObject(stream)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)

    content = (
        f"q {width} 0 0 {height} 0 0 cm /{name.get_name()} Do Q"
    ).encode("ascii")
    content_stream = COSStream(cos_doc.scratch_file)
    with content_stream.create_output_stream() as out:
        out.write(content)
    page.get_cos_object().set_item(COSName.get_pdf_name("Contents"), content_stream)

    buf = io.BytesIO()
    document.save(buf)
    document.close()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# fingerprinting (mirrors ImageExtractProbe.java cell mapping exactly)
# ---------------------------------------------------------------------------


def _luminance_grid(image: Image.Image) -> list[int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(y * _GRID // height, _GRID - 1)
        for x in range(width):
            cx = min(x * _GRID // width, _GRID - 1)
            r, g, b = pixels[x, y]
            lum = round(0.299 * r + 0.587 * g + 0.114 * b)
            idx = cy * _GRID + cx
            total[idx] += lum
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _py_decode_grid(pdf_bytes: bytes) -> tuple[int, int, int, str, list[int]]:
    document = PDDocument.load(pdf_bytes)
    try:
        page = document.get_page(0)
        resources = page.get_resources()
        names = list(resources.get_x_object_names())
        assert names, "fixture PDF has no image XObject"
        image = resources.get_x_object(names[0])
        cs = image.get_color_space()
        cs_name = cs.get_name() if cs is not None else "null"
        pil = image.get_image()
        assert pil is not None, "pypdfbox failed to decode the JBIG2 image"
        return (
            image.get_width(),
            image.get_height(),
            image.get_bits_per_component(),
            cs_name,
            _luminance_grid(pil),
        )
    finally:
        document.close()


def _java_decode(probe_output: str) -> tuple[int, int, int, str, list[int]]:
    line = probe_output.strip().splitlines()[0]
    tokens = line.split()
    w = int(tokens[tokens.index("w") + 1])
    h = int(tokens[tokens.index("h") + 1])
    bpc = int(tokens[tokens.index("bpc") + 1])
    cs = tokens[tokens.index("cs") + 1]
    grid_at = tokens.index("grid")
    grid = [int(t) for t in tokens[grid_at + 1 :]]
    return w, h, bpc, cs, grid


def _assert_parity(jb2_name: str, tmp_path) -> None:
    jb2_bytes = (_FIXTURES / jb2_name).read_bytes()
    width, height = _bitmap_dims(jb2_bytes)
    pdf_bytes = _build_jbig2_pdf(jb2_bytes, width, height)

    fixture = tmp_path / "jbig2.pdf"
    fixture.write_bytes(pdf_bytes)

    jw, jh, jbpc, jcs, jgrid = _java_decode(
        run_probe_text("ImageExtractProbe", str(fixture))
    )
    pw, ph, pbpc, pcs, pgrid = _py_decode_grid(pdf_bytes)

    assert (pw, ph, pbpc, pcs) == (jw, jh, jbpc, jcs), (
        f"metadata divergence: py=({pw},{ph},{pbpc},{pcs}) "
        f"java=({jw},{jh},{jbpc},{jcs})"
    )
    assert len(pgrid) == len(jgrid) == _GRID * _GRID
    # pypdfbox's JBIG2 decode is bit-exact with PDFBox's, so the
    # downsampled fingerprint must agree exactly (no codec slack).
    assert pgrid == jgrid, (
        f"luminance fingerprint divergence\n  java={jgrid}\n  py  ={pgrid}"
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("jb2_name", ["003.jb2", "005.jb2", "006.jb2"])
def test_jbig2_image_get_image_parity(jb2_name: str, tmp_path) -> None:
    _assert_parity(jb2_name, tmp_path)
