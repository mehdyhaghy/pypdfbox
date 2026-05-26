"""Live PDFBox differential parity for ``/DCTDecode`` (JPEG) image decode.

Exercises the full image-XObject decode path — ``PDImageXObject.get_image()``
over a ``/Filter /DCTDecode`` stream — against Apache PDFBox 3.0.7's
``PDImageXObject.getImage()`` on the *same* PDF, across the three JPEG colour
spaces a PDF can carry:

* **grayscale** JPEG  -> ``/DeviceGray``
* **YCbCr-RGB** JPEG  -> ``/DeviceRGB`` (the JPEG default colour transform)
* **CMYK / YCCK** JPEG with the **Adobe APP14** transform marker ->
  ``/DeviceCMYK`` (the classic *inverted-CMYK trap*).

Each test builds its host PDF from a committed JPEG fixture
(``tests/fixtures/dct/*.jpg``) via ``JPEGFactory.create_from_byte_array`` — the
same factory PDFBox ships — so the image dictionary (incl. the CMYK
``/Decode [1 0 1 0 1 0 1 0]`` array PDFBox attaches) is built identically on
both sides. Both libraries then decode that single artefact.

The Java side runs through ``oracle/probes/JpegImgProbe.java``: it walks every
page's image XObjects and emits ``w h bpc cs``, four sampled fully-transformed
RGB triples (``px``), and a 16x16 average-luminance fingerprint of
``getImage()``. ``w/h/bpc/cs`` are asserted exact.

Tolerances — JPEG is lossy + decoder-dependent (Java ImageIO vs Pillow/
libjpeg-turbo), so the luminance grid is compared with MAD/MAXDIFF, never byte
equality:

* gray + RGB: MAD < 6, MAXDIFF < 60 (the RenderProbe gate). The two codecs
  agree to within codec anti-aliasing; observed MAD ~0, MAXDIFF <= 1.
* CMYK/APP14: **polarity** is asserted strictly via the sampled RGB triples —
  each channel agrees in sign of deviation from mid-grey, so an inversion (the
  trap) is caught hard. The luminance-grid MAD is allowed a wider band because
  PDFBox transforms DeviceCMYK through its bundled
  ``CGATS001Compat-v2-micro.icc`` profile while pypdfbox uses the deterministic
  subtractive transform in ``PDDeviceCMYK`` (a documented colour-cluster
  divergence, not a DCT-decode bug). Observed CMYK grid MAD ~21, MAXDIFF ~49.
"""

from __future__ import annotations

import io
import pathlib

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_FIXTURES = pathlib.Path(__file__).resolve().parents[4] / "fixtures" / "dct"


# ---------------------------------------------------------------------------
# fixture construction
# ---------------------------------------------------------------------------


def _build_host_pdf(jpeg_bytes: bytes) -> bytes:
    """Wrap ``jpeg_bytes`` in a one-page image-XObject PDF via JPEGFactory."""
    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    document.add_page(page)

    image = JPEGFactory.create_from_byte_array(document, jpeg_bytes)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)

    width = image.get_width()
    height = image.get_height()
    cos_doc = document.get_document()
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
# fingerprinting (mirrors JpegImgProbe.java cell mapping exactly)
# ---------------------------------------------------------------------------


def _luminance_grid(image: Image.Image) -> list[int]:
    """16x16 average Rec.601 luminance fingerprint, row-major, matching
    ``JpegImgProbe.java``'s integer cell mapping."""
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


def _sample_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    """Read the same four RGB sample points JpegImgProbe.java emits."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pts = (
        (width // 8, height // 8),
        ((width * 7) // 8, height // 8),
        (width // 8, (height * 7) // 8),
        (width // 2, height // 2),
    )
    out = []
    for x, y in pts:
        x = min(max(x, 0), width - 1)
        y = min(max(y, 0), height - 1)
        out.append(rgb.getpixel((x, y)))
    return out


def _py_decode(pdf_bytes: bytes):
    """Decode the first image XObject with pypdfbox; return metadata + grid +
    sampled RGB triples."""
    document = PDDocument.load(pdf_bytes)
    try:
        resources = document.get_page(0).get_resources()
        names = list(resources.get_x_object_names())
        assert names, "fixture PDF has no image XObject"
        image = resources.get_x_object(names[0])
        cs = image.get_color_space()
        cs_name = cs.get_name() if cs is not None else "null"
        pil = image.get_image()
        assert pil is not None, "pypdfbox failed to decode the JPEG image"
        return (
            image.get_width(),
            image.get_height(),
            image.get_bits_per_component(),
            cs_name,
            _luminance_grid(pil),
            _sample_pixels(pil),
        )
    finally:
        document.close()


def _java_decode(probe_output: str):
    """Parse one JpegImgProbe output line into the same tuple."""
    line = probe_output.strip().splitlines()[0]
    tokens = line.split()
    w = int(tokens[tokens.index("w") + 1])
    h = int(tokens[tokens.index("h") + 1])
    bpc = int(tokens[tokens.index("bpc") + 1])
    cs = tokens[tokens.index("cs") + 1]
    px_blob = tokens[tokens.index("px") + 1]
    px = [
        tuple(int(v) for v in triple.split(","))
        for triple in px_blob.split(";")
    ]
    grid_at = tokens.index("grid")
    grid = [int(t) for t in tokens[grid_at + 1 :]]
    return w, h, bpc, cs, grid, px


def _grid_mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    assert len(a) == len(b) == _GRID * _GRID
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _decode_both(jpeg_name: str, tmp_path):
    jpeg_bytes = (_FIXTURES / jpeg_name).read_bytes()
    pdf_bytes = _build_host_pdf(jpeg_bytes)
    fixture = tmp_path / "dct.pdf"
    fixture.write_bytes(pdf_bytes)
    java = _java_decode(run_probe_text("JpegImgProbe", str(fixture)))
    py = _py_decode(pdf_bytes)
    return java, py


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_dct_gray_decode_matches_pdfbox(tmp_path) -> None:
    """A grayscale JPEG decodes to ``/DeviceGray`` with a luminance grid
    matching PDFBox within the lossy-codec gate."""
    java, py = _decode_both("dct_gray.jpg", tmp_path)
    jw, jh, jbpc, jcs, jgrid, _jpx = java
    pw, ph, pbpc, pcs, pgrid, _ppx = py

    assert (pw, ph) == (jw, jh)
    assert pbpc == jbpc == 8
    assert pcs == jcs == "DeviceGray"
    mad, maxdiff = _grid_mad_maxdiff(jgrid, pgrid)
    assert mad < 6, f"gray grid MAD too high: {mad}"
    assert maxdiff < 60, f"gray grid MAXDIFF too high: {maxdiff}"


@requires_oracle
def test_dct_rgb_decode_matches_pdfbox(tmp_path) -> None:
    """A YCbCr-RGB JPEG decodes to ``/DeviceRGB`` with a luminance grid
    matching PDFBox within the lossy-codec gate."""
    java, py = _decode_both("dct_rgb.jpg", tmp_path)
    jw, jh, jbpc, jcs, jgrid, jpx = java
    pw, ph, pbpc, pcs, pgrid, ppx = py

    assert (pw, ph) == (jw, jh)
    assert pbpc == jbpc == 8
    assert pcs == jcs == "DeviceRGB"
    mad, maxdiff = _grid_mad_maxdiff(jgrid, pgrid)
    assert mad < 6, f"rgb grid MAD too high: {mad}"
    assert maxdiff < 60, f"rgb grid MAXDIFF too high: {maxdiff}"
    # RGB is a direct codec round-trip; sampled channels agree closely.
    for (jr, jg, jb), (pr, pg, pb) in zip(jpx, ppx, strict=True):
        assert abs(jr - pr) < 60 and abs(jg - pg) < 60 and abs(jb - pb) < 60


@requires_oracle
def test_dct_cmyk_app14_polarity_matches_pdfbox(tmp_path) -> None:
    """A CMYK JPEG carrying the Adobe APP14 transform marker decodes to
    ``/DeviceCMYK`` with **correct polarity** — the inverted-CMYK trap.

    Polarity is asserted strictly: each sampled channel must land on the same
    side of mid-grey as PDFBox (an Adobe-inversion bug flips every channel and
    blows far past this). The luminance grid is allowed a wider MAD band
    because PDFBox transforms DeviceCMYK through its bundled
    ``CGATS001Compat-v2-micro.icc`` profile while pypdfbox uses the
    deterministic subtractive transform in ``PDDeviceCMYK`` — a documented
    colour-cluster divergence, not a DCT-decode bug. MAXDIFF still sits under
    the RenderProbe ceiling.
    """
    java, py = _decode_both("dct_cmyk_app14.jpg", tmp_path)
    jw, jh, jbpc, jcs, jgrid, jpx = java
    pw, ph, pbpc, pcs, pgrid, ppx = py

    assert (pw, ph) == (jw, jh)
    assert pbpc == jbpc == 8
    assert pcs == jcs == "DeviceCMYK"

    # Strict polarity: for each sampled channel, pypdfbox and PDFBox must
    # agree which side of mid-grey (128) the value sits on. A polarity
    # inversion (the classic Adobe-CMYK trap) would put them on opposite
    # sides for the saturated channels.
    for (jr, jg, jb), (pr, pg, pb) in zip(jpx, ppx, strict=True):
        for jv, pv in ((jr, pr), (jg, pg), (jb, pb)):
            # Skip near-mid-grey channels where "side" is ambiguous; the trap
            # manifests on the saturated channels (|v - 128| large).
            if abs(jv - 128) < 40:
                continue
            assert (jv >= 128) == (pv >= 128), (
                f"CMYK polarity mismatch: java {(jr, jg, jb)} py {(pr, pg, pb)}"
            )

    mad, maxdiff = _grid_mad_maxdiff(jgrid, pgrid)
    # Wide MAD band documents the ICC-vs-subtractive colour divergence; a
    # polarity inversion would push MAD toward ~120, so this still guards it.
    assert mad < 40, f"CMYK grid MAD beyond ICC-divergence band: {mad}"
    assert maxdiff < 60, f"CMYK grid MAXDIFF too high: {maxdiff}"
