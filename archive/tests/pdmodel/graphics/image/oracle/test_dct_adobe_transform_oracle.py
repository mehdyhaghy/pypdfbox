"""Live PDFBox differential parity for the ``/DCTDecode`` (JPEG) **Adobe
APP14 transform** dimension — orthogonal to ``test_dct_decode_oracle.py``.

``test_dct_decode_oracle.py`` already pins the three JPEG *colour spaces* a PDF
can carry (grayscale -> ``/DeviceGray``, YCbCr-RGB -> ``/DeviceRGB``, and an
Adobe-marker CMYK with transform byte ``0`` -> ``/DeviceCMYK``). What it does
*not* exercise is the orthogonal question the brief flags: how the CMYK ink
polarity is resolved as a function of the **Adobe APP14 marker**. PDFBox decodes
a CMYK/YCCK codestream's raw stored samples (Adobe stores them inverted,
``255 = ink-off``) and the polarity it ultimately renders depends on whether
the Adobe APP14 marker is present and on its transform byte:

* **CMYK JPEG with NO Adobe marker** (``dct_cmyk_no_adobe.jpg``). The committed
  Adobe-CMYK fixture in the sibling file carries the marker; this one has it
  stripped. The interesting parity question is whether pypdfbox and PDFBox
  *agree on the un-inversion* when the marker is absent. They do — both un-invert
  the stored CMYK samples, so a saturated-cyan quadrant lands at low-R/high-G,B
  on both sides (a divergence here would flip every saturated channel). pypdfbox
  reaches this via Pillow's JPEG reader, which un-inverts CMYK regardless of the
  marker; PDFBox reaches the same polarity, so the two match.

* **YCCK JPEG** (``dct_ycck.jpg``, Adobe transform byte ``2``). YCCK is the
  *other* Adobe variant — the chroma-subsampled CMYK transform. The probe must
  confirm pypdfbox's YCCK path resolves to the same ``/DeviceCMYK`` raster
  polarity PDFBox produces (transform ``2`` decoded identically on both sides).

Both fixtures are tiny committed JPEGs (see ``PROVENANCE.md``). Each is wrapped
into a one-page image-XObject PDF via ``JPEGFactory.create_from_byte_array`` —
the same factory PDFBox ships, so the image dictionary (incl. the CMYK
``/Decode [1 0 1 0 1 0 1 0]`` array) is built identically on both sides — and
both libraries decode that single artefact.

The Java side reuses ``oracle/probes/JpegImgProbe.java`` (it already walks every
page's image XObjects and emits ``w h bpc cs``, four sampled fully-transformed
RGB triples, and a 16x16 luminance grid of ``getImage()``). ``w/h/bpc/cs`` are
asserted exact; the luminance grid is gated with MAD/MAXDIFF because JPEG is
lossy + decoder-dependent and DeviceCMYK is transformed through PDFBox's bundled
``CGATS001Compat-v2-micro.icc`` profile vs pypdfbox's deterministic subtractive
``PDDeviceCMYK`` transform (a documented colour-cluster divergence, not a
DCT-decode bug). Polarity is asserted strictly via the sampled RGB triples so an
Adobe-inversion regression (the classic trap) is caught hard regardless of the
colour-transform band.
"""

from __future__ import annotations

import io
import pathlib

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
# fixture construction (identical to test_dct_decode_oracle.py)
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


def _luminance_grid(image) -> list[int]:
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
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _sample_pixels(image) -> list[tuple[int, int, int]]:
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
        tuple(int(v) for v in triple.split(",")) for triple in px_blob.split(";")
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
def test_dct_cmyk_no_adobe_marker_polarity_matches_pdfbox(tmp_path) -> None:
    """A CMYK JPEG with the Adobe APP14 marker **stripped** decodes to
    ``/DeviceCMYK`` with the same ink polarity PDFBox produces.

    The complement of ``test_dct_cmyk_app14_polarity_matches_pdfbox`` (which
    carries the marker): here the marker is absent, and the parity question is
    whether the two libraries still agree on un-inverting the stored CMYK
    samples. They do — pypdfbox un-inverts via Pillow's JPEG reader (which
    un-inverts CMYK regardless of the marker) and PDFBox reaches the same
    polarity. A divergence would flip every saturated channel past any
    lossy-codec tolerance.
    """
    java, py = _decode_both("dct_cmyk_no_adobe.jpg", tmp_path)
    jw, jh, jbpc, jcs, jgrid, jpx = java
    pw, ph, pbpc, pcs, pgrid, ppx = py

    assert (pw, ph) == (jw, jh)
    assert pbpc == jbpc == 8
    assert pcs == jcs == "DeviceCMYK"

    # Strict polarity: each saturated sampled channel must land on the same
    # side of mid-grey on both sides. An Adobe-inversion regression flips it.
    for (jr, jg, jb), (pr, pg, pb) in zip(jpx, ppx, strict=True):
        for jv, pv in ((jr, pr), (jg, pg), (jb, pb)):
            if abs(jv - 128) < 40:
                continue
            assert (jv >= 128) == (pv >= 128), (
                f"no-Adobe CMYK polarity mismatch: java {(jr, jg, jb)} "
                f"py {(pr, pg, pb)}"
            )

    mad, maxdiff = _grid_mad_maxdiff(jgrid, pgrid)
    # Same ICC-vs-subtractive band as the Adobe-CMYK case; a polarity
    # inversion would push MAD toward ~120, so this still guards it.
    assert mad < 40, f"no-Adobe CMYK grid MAD beyond ICC-divergence band: {mad}"
    assert maxdiff < 60, f"no-Adobe CMYK grid MAXDIFF too high: {maxdiff}"


@requires_oracle
def test_dct_ycck_transform_matches_pdfbox(tmp_path) -> None:
    """A YCCK JPEG (Adobe APP14 transform byte ``2``) decodes to
    ``/DeviceCMYK`` and resolves to the same raster PDFBox produces.

    YCCK is the chroma-subsampled CMYK Adobe variant — the other transform
    byte. The parity point is that pypdfbox's YCCK -> CMYK -> RGB path lands at
    the same luminance fingerprint PDFBox does (the transform-byte-2 codestream
    decoded identically on both sides), within the lossy-codec gate.
    """
    java, py = _decode_both("dct_ycck.jpg", tmp_path)
    jw, jh, jbpc, jcs, jgrid, _jpx = java
    pw, ph, pbpc, pcs, pgrid, _ppx = py

    assert (pw, ph) == (jw, jh)
    assert pbpc == jbpc == 8
    assert pcs == jcs == "DeviceCMYK"

    mad, maxdiff = _grid_mad_maxdiff(jgrid, pgrid)
    assert mad < 20, f"YCCK grid MAD too high: {mad}"
    assert maxdiff < 60, f"YCCK grid MAXDIFF too high: {maxdiff}"
