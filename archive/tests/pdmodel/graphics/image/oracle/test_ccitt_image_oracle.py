"""Live PDFBox differential parity for CCITT Group 3/4 fax image decode.

Exercises the full image-XObject decode path — ``PDImageXObject.get_image()``
over a ``/Filter /CCITTFaxDecode`` stream — against Apache PDFBox 3.0.7's
``PDImageXObject.getImage()`` on the *same* PDF.

There is no bundled CCITTFax sample PDF, so each test BUILDS one: a small
bilevel raster is CCITT-encoded (via pypdfbox's libtiff-backed CCITT encoder,
which after wave 1418 produces a stream byte-identical to PDFBox's own
``CCITTFactory``), wrapped in a one-page image-XObject PDF, and saved once.
Both libraries then decode that single artefact.

The Java side runs through ``oracle/probes/CcittImgProbe.java``: it walks every
page's image XObjects and emits ``w h bpc cs`` plus a 16x16 average-luminance
fingerprint of ``getImage()``. ``w/h/bpc/cs`` are asserted exact; the grid is
asserted within a tiny tolerance (a bilevel raster downsampled identically on
both sides agrees to a couple of luminance levels at most — block-boundary
rounding is the only source of slack).

Coverage:

* Group 4 (``K < 0``), Group 3 1-D (``K == 0``), Group 3 2-D (``K > 0``).
* ``/BlackIs1`` false (default) and true — the polarity axis that wave 1418
  fixed (pypdfbox previously decoded every CCITT image as the exact
  bit-inverse of PDFBox).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.filter import CCITTFaxDecode
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16


# ---------------------------------------------------------------------------
# fixture construction
# ---------------------------------------------------------------------------


def _checker_raster(width: int, height: int) -> Image.Image:
    """A 4x4-block checkerboard bilevel image (PIL "1": 0 = black, 1 = white)."""
    img = Image.new("1", (width, height), 1)
    for y in range(height):
        for x in range(width):
            if ((x // 4) + (y // 4)) % 2 == 0:
                img.putpixel((x, y), 0)
    return img


def _build_ccitt_pdf(
    raster: Image.Image,
    *,
    k: int,
    black_is_1: bool,
) -> bytes:
    """Build a one-page PDF whose only image is ``raster`` CCITT-encoded
    with the given ``/K`` and ``/BlackIs1``. Returns the saved PDF bytes."""
    width, height = raster.size

    enc_dict = COSDictionary()
    enc_parms = COSDictionary()
    enc_parms.set_int("Columns", width)
    enc_parms.set_int("Rows", height)
    enc_parms.set_int("K", k)
    if black_is_1:
        enc_parms.set_boolean("BlackIs1", True)
    enc_dict.set_item(COSName.get_pdf_name("DecodeParms"), enc_parms)

    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raster.tobytes()), enc_buf, enc_dict)
    encoded = enc_buf.getvalue()

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
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("CCITTFaxDecode"))
    dec_parms = COSDictionary()
    dec_parms.set_int("K", k)
    dec_parms.set_int("Columns", width)
    dec_parms.set_int("Rows", height)
    if black_is_1:
        dec_parms.set_boolean("BlackIs1", True)
    stream.set_item(COSName.get_pdf_name("DecodeParms"), dec_parms)
    stream.set_int(COSName.get_pdf_name("Length"), len(encoded))
    stream.set_raw_data(encoded)

    image = PDImageXObject(stream)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)

    content = (
        f"q {width} 0 0 {height} 10 10 cm /{name.get_name()} Do Q"
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
# fingerprinting (mirrors CcittImgProbe.java cell mapping exactly)
# ---------------------------------------------------------------------------


def _luminance_grid(image: Image.Image) -> list[int]:
    """16x16 average Rec.601 luminance fingerprint, row-major, matching
    ``CcittImgProbe.java``'s integer cell mapping."""
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
    """Decode the first image XObject with pypdfbox; return its metadata
    plus the luminance fingerprint."""
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
        assert pil is not None, "pypdfbox failed to decode the CCITT image"
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
    """Parse a single ``CcittImgProbe`` output line into the same tuple."""
    line = probe_output.strip().splitlines()[0]
    tokens = line.split()
    # ccitt page <p> name <n> w <w> h <h> bpc <bpc> cs <cs> grid <256 ints>
    w = int(tokens[tokens.index("w") + 1])
    h = int(tokens[tokens.index("h") + 1])
    bpc = int(tokens[tokens.index("bpc") + 1])
    cs = tokens[tokens.index("cs") + 1]
    grid_at = tokens.index("grid")
    grid = [int(t) for t in tokens[grid_at + 1 :]]
    return w, h, bpc, cs, grid


def _assert_parity(pdf_bytes: bytes, tmp_path) -> None:
    fixture = tmp_path / "ccitt.pdf"
    fixture.write_bytes(pdf_bytes)

    jw, jh, jbpc, jcs, jgrid = _java_decode(
        run_probe_text("CcittImgProbe", str(fixture))
    )
    pw, ph, pbpc, pcs, pgrid = _py_decode_grid(pdf_bytes)

    assert (pw, ph, pbpc, pcs) == (jw, jh, jbpc, jcs), (
        f"metadata divergence: py=({pw},{ph},{pbpc},{pcs}) "
        f"java=({jw},{jh},{jbpc},{jcs})"
    )
    assert len(pgrid) == len(jgrid) == _GRID * _GRID
    worst = max(abs(p - j) for p, j in zip(pgrid, jgrid, strict=True))
    assert worst <= 6, (
        f"luminance fingerprint divergence (worst cell delta {worst})\n"
        f"  java={jgrid}\n  py  ={pgrid}"
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("k", "label"),
    [(-1, "g4"), (0, "g3_1d"), (2, "g3_2d")],
    ids=["g4", "g3-1d", "g3-2d"],
)
def test_ccitt_image_k_modes_parity(k: int, label: str, tmp_path) -> None:
    pdf = _build_ccitt_pdf(_checker_raster(32, 16), k=k, black_is_1=False)
    _assert_parity(pdf, tmp_path)


@requires_oracle
@pytest.mark.parametrize("black_is_1", [False, True], ids=["blackis0", "blackis1"])
def test_ccitt_image_black_is_1_parity(black_is_1: bool, tmp_path) -> None:
    pdf = _build_ccitt_pdf(_checker_raster(24, 24), k=-1, black_is_1=black_is_1)
    _assert_parity(pdf, tmp_path)


@requires_oracle
def test_ccitt_encoder_stream_matches_pdfbox_byte_for_byte(tmp_path) -> None:
    """After wave 1418 pypdfbox's CCITT encoder produces a Group-4 strip
    byte-identical to PDFBox's ``CCITTFactory.createFromImage``. We anchor
    that with the ``CcittEncRefProbe`` reference encoder so a future encoder
    regression (polarity, byte-alignment) is caught directly, not just via
    the decoded-grid tolerance."""
    from pypdfbox.pdmodel.graphics.image.ccitt_factory import CCITTFactory
    from tests.oracle.harness import run_probe

    raster = _checker_raster(16, 16)
    document = PDDocument()
    try:
        image = CCITTFactory.create_from_image(document, raster)
        cos = image.get_cos_object()
        assert isinstance(cos, COSStream)
        py_strip = bytes(cos.get_raw_data())
    finally:
        document.close()

    java_strip = run_probe("CcittEncRefProbe", "16", "16", "checker")
    assert py_strip == java_strip, (
        "pypdfbox CCITT encoder diverged from PDFBox CCITTFactory:\n"
        f"  py  ={py_strip.hex()}\n  java={java_strip.hex()}"
    )
