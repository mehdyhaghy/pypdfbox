"""Live PDFBox differential parity for inline-image (BI/ID/EI) pixel decode.

We decode every inline image on a page through pypdfbox's
:class:`~pypdfbox.pdmodel.graphics.image.pd_inline_image.PDInlineImage` and
compare its decoded raster against Apache PDFBox's ``PDInlineImage.getImage()``
on the same content stream, via ``oracle/probes/InlineImgProbe.java``.

What we compare per inline image (in stream order):

* **Exact metadata** — ``width``, ``height``, ``bits_per_component`` and the
  resolved colour-space *name* MUST match PDFBox byte-for-byte. A mismatch is
  a real decode bug (wrong abbreviated-key lookup, wrong colour-space
  expansion, etc.), never a rounding artefact.
* **16x16 luminance grid** — the decoded raster (``get_image()``) is
  downsampled to a 16x16 grid of average Rec.601 luminance per cell (0..255),
  matching the cell mapping in ``InlineImgProbe.java``. We compare grids by
  mean-absolute cell difference (MAD) and worst single-cell difference
  (MAXDIFF). A blank/garbled raster blows far past tolerance.

Tolerances. DeviceGray / DeviceRGB / Indexed rasters decode byte-identically
to PDFBox (measured MAD=0, MAXDIFF=0), so they gate tightly. DeviceCMYK is a
documented by-design divergence (CHANGES.md: PDFBox routes through the JVM CMM
while pypdfbox uses explicit subtractive math) — deltas land in the 21-50/255
band, so its grid gets a wider documented tolerance while its metadata is
still asserted exactly.

Fixtures are tiny PDFs synthesised in-memory here (no bundled corpus has the
full abbreviated-filter / abbreviated-colour-space matrix the task requires):
one inline image per abbreviated filter (AHx / A85 / Fl / RL / DCT) and per
abbreviated colour space (G / RGB / CMYK / I), plus a 1-bit bilevel image and
a multi-image page.
"""

from __future__ import annotations

import base64
import io
import zlib

import pytest
from PIL import Image

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Tight gate for byte-exact device/indexed rasters; generous gate for the
# documented CMYK->RGB colour-conversion divergence (see module docstring).
_MAD_TOLERANCE = 4.0
_MAXDIFF_TOLERANCE = 24
_CMYK_MAD_TOLERANCE = 20.0
_CMYK_MAXDIFF_TOLERANCE = 70


# --------------------------------------------------------------------------
# Fixture synthesis — build a one-page PDF whose content stream embeds the
# given inline-image byte blocks.
# --------------------------------------------------------------------------
def _build_pdf(inline_blocks: list[bytes]) -> bytes:
    body = bytearray(b"q 100 0 0 100 50 50 cm\n")
    for block in inline_blocks:
        body += block
    body += b"Q\n"
    content = bytes(body)

    def obj(num: int, data: bytes) -> bytes:
        return f"{num} 0 obj\n".encode() + data + b"\nendobj\n"

    stream_obj = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    parts = [
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(
            3,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Contents 4 0 R /Resources << >> >>",
        ),
        obj(4, stream_obj),
    ]
    pdf = bytearray(b"%PDF-1.7\n")
    offsets: list[int] = []
    for part in parts:
        offsets.append(len(pdf))
        pdf += part
    xref_off = len(pdf)
    pdf += b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % xref_off
    return bytes(pdf)


def _inline(params: bytes, data: bytes) -> bytes:
    return b"BI " + params + b" ID\n" + data + b"\nEI\n"


def _ahx(data: bytes) -> bytes:
    return data.hex().upper().encode() + b">"


def _rle(data: bytes) -> bytes:
    """RunLengthDecode literal-run encoding (length byte 0..127 = N+1 literals)."""
    out = bytearray()
    i = 0
    while i < len(data):
        chunk = data[i : i + 128]
        out.append(len(chunk) - 1)
        out += chunk
        i += 128
    out.append(128)  # EOD
    return bytes(out)


# Inline-image building blocks. Each is (label, inline-bytes, is_cmyk).
def _ahx_gray() -> bytes:
    # 4x4 8-bit DeviceGray gradient via ASCIIHex.
    px = bytes(range(0, 256, 16))[:16]
    return _inline(b"/W 4 /H 4 /BPC 8 /CS /G /F /AHx", _ahx(px))


def _a85_rgb() -> bytes:
    rgb = bytes([200, 30, 30, 30, 200, 30, 30, 30, 200, 200, 200, 30])
    return _inline(b"/W 2 /H 2 /BPC 8 /CS /RGB /F /A85", base64.a85encode(rgb) + b"~>")


def _flate_gray() -> bytes:
    px = bytes(range(0, 256, 16))[:16]
    return _inline(b"/W 4 /H 4 /BPC 8 /CS /G /F /Fl", zlib.compress(px))


def _rl_rgb() -> bytes:
    rgb = bytes([10, 200, 10, 200, 10, 10, 10, 10, 200, 200, 200, 200])
    return _inline(b"/W 2 /H 2 /BPC 8 /CS /RGB /F /RL", _rle(rgb))


def _indexed() -> bytes:
    # 4x4, 2 bpc, palette red/green/blue/white, ASCIIHex-encoded indices.
    lookup = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
    rows = bytes(
        [
            (0 << 6) | (1 << 4) | (2 << 2) | 3,
            (3 << 6) | (2 << 4) | (1 << 2) | 0,
            0,
            (3 << 6) | (3 << 4) | (3 << 2) | 3,
        ]
    )
    params = b"/W 4 /H 4 /BPC 2 /CS [/I /RGB 3 <" + lookup.hex().upper().encode() + b">] /F /AHx"
    return _inline(params, _ahx(rows))


def _bilevel() -> bytes:
    # 8x2 1-bit DeviceGray: row0 = alternating, row1 = half/half.
    data = bytes([0b10101010, 0b11110000])
    return _inline(b"/W 8 /H 2 /BPC 1 /CS /G", data)


def _dct_rgb() -> bytes:
    im = Image.new("RGB", (8, 8))
    for y in range(8):
        for x in range(8):
            im.putpixel((x, y), (x * 32, y * 32, 128))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return _inline(b"/W 8 /H 8 /BPC 8 /CS /RGB /F /DCT", buf.getvalue())


def _cmyk() -> bytes:
    cmyk = bytes([0, 0, 0, 0, 255, 0, 0, 0, 0, 255, 0, 0, 0, 0, 0, 255])
    return _inline(b"/W 2 /H 2 /BPC 8 /CS /CMYK", cmyk)


# (label, [inline blocks], is_cmyk) — single-image pages plus one multi-image.
_CASES: list[tuple[str, list[bytes], bool]] = [
    ("ahx_gray", [_ahx_gray()], False),
    ("a85_rgb", [_a85_rgb()], False),
    ("flate_gray", [_flate_gray()], False),
    ("rl_rgb", [_rl_rgb()], False),
    ("indexed_2bpc", [_indexed()], False),
    ("bilevel_1bpc", [_bilevel()], False),
    ("dct_rgb", [_dct_rgb()], False),
    ("cmyk", [_cmyk()], True),
    ("multi_image", [_ahx_gray(), _a85_rgb(), _indexed()], False),
]


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — must match InlineImgProbe.java."""
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


def _pypdfbox_signatures(
    pdf_bytes: bytes,
) -> list[tuple[tuple[int, int, int, str], list[int]]]:
    """Decode every inline image on page 0 with pypdfbox; return per-image
    ((w, h, bpc, cs_name), 16x16 grid) in stream order."""
    out: list[tuple[tuple[int, int, int, str], list[int]]] = []
    with PDDocument.load(pdf_bytes) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        parser = PDFStreamParser(RandomAccessReadBuffer(page.get_contents()))
        for token in parser.tokens():
            if isinstance(token, Operator) and token.get_name() == "BI":
                image = PDInlineImage(
                    token.get_image_parameters(),
                    token.get_image_data(),
                    resources,
                )
                raster = image.get_image()
                assert raster is not None, "pypdfbox failed to decode inline raster"
                meta = (
                    image.get_width(),
                    image.get_height(),
                    image.get_bits_per_component(),
                    image.get_color_space().get_name(),
                )
                out.append((meta, _grid_from_image(raster)))
    return out


def _oracle_signatures(
    tmp_path, pdf_bytes: bytes
) -> list[tuple[tuple[int, int, int, str], list[int]]]:
    """Run InlineImgProbe.java; parse per-image ((w,h,bpc,cs), 16x16 grid)."""
    fixture = tmp_path / "inline.pdf"
    fixture.write_bytes(pdf_bytes)
    text = run_probe_text("InlineImgProbe", str(fixture), "0")
    lines = text.splitlines()
    out: list[tuple[tuple[int, int, int, str], list[int]]] = []
    for i in range(0, len(lines), 2):
        head = lines[i].split()
        meta = (int(head[0]), int(head[1]), int(head[2]), head[3])
        grid = [int(v) for v in lines[i + 1].split()]
        assert len(grid) == _GRID * _GRID
        out.append((meta, grid))
    return out


@requires_oracle
@pytest.mark.parametrize(
    ("label", "blocks", "is_cmyk"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_inline_image_decode_matches_pdfbox(
    tmp_path, label: str, blocks: list[bytes], is_cmyk: bool
) -> None:
    pdf_bytes = _build_pdf(blocks)
    java = _oracle_signatures(tmp_path, pdf_bytes)
    py = _pypdfbox_signatures(pdf_bytes)

    assert len(py) == len(java), (
        f"{label}: pypdfbox found {len(py)} inline images, PDFBox found {len(java)}"
    )

    mad_tol = _CMYK_MAD_TOLERANCE if is_cmyk else _MAD_TOLERANCE
    maxdiff_tol = _CMYK_MAXDIFF_TOLERANCE if is_cmyk else _MAXDIFF_TOLERANCE

    for idx, ((py_meta, py_grid), (java_meta, java_grid)) in enumerate(
        zip(py, java, strict=True)
    ):
        # (a) metadata exact — width / height / bpc / colour-space name.
        assert py_meta == java_meta, (
            f"{label}[{idx}]: inline-image metadata diverges from PDFBox: "
            f"pypdfbox={py_meta} java={java_meta}"
        )
        # (b) decoded raster fingerprint within tolerance.
        diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
        mad = sum(diffs) / len(diffs)
        maxdiff = max(diffs)
        assert mad < mad_tol, (
            f"{label}[{idx}]: mean abs cell diff {mad:.2f} >= {mad_tol} "
            f"(maxdiff={maxdiff}) — grossly divergent inline-image raster"
        )
        assert maxdiff < maxdiff_tol, (
            f"{label}[{idx}]: worst cell diff {maxdiff} >= {maxdiff_tol} "
            f"(mad={mad:.2f}) — a region diverges far beyond codec tolerance"
        )


@requires_oracle
def test_blank_inline_raster_would_fail_tolerance(tmp_path) -> None:
    """Guard the gate: a blank-white raster is far outside tolerance for an
    inline image PDFBox decodes with content. Confirms the gate discriminates
    correct decodes from gross failures rather than passing everything."""
    pdf_bytes = _build_pdf([_indexed()])
    (java_meta, java_grid), = _oracle_signatures(tmp_path, pdf_bytes)
    del java_meta
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a blank inline raster passes the MAD gate"
    )
