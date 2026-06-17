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
from pypdfbox.rendering.pdf_renderer import PDFRenderer
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


# ==========================================================================
# Render-level parity — full PDFRenderer page render vs PDFBox PDFRenderer.
#
# The decode-level tests above compare ``PDInlineImage.get_image()`` rasters.
# These render-level tests instead run the whole inline-image paint path
# (``PDFRenderer`` -> ``_op_inline_image`` -> ``show_inline_image``) against
# Java PDFBox's ``PDFRenderer.renderImageWithDPI`` via ``RenderProbe.java``.
# This is what exercises the *paint* side: a ``/IM true`` stencil must take
# the current non-stroking colour (not be pasted as a literal black/white
# raster), abbreviated + full key names must both parse, and EI must be
# detected past the raw binary body.
# ==========================================================================
_RENDER_MAD_TOLERANCE = 6.0
_RENDER_MAXDIFF_TOLERANCE = 60


def _build_render_pdf(content: bytes) -> bytes:
    """One-page 200x200 PDF whose content stream is ``content`` verbatim
    (no implicit ``cm`` wrapper — each render case supplies its own CTM /
    colour state)."""

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


def _draw_inline(prefix: bytes, params: bytes, data: bytes) -> bytes:
    """Content stream: optional colour/state ``prefix`` then an inline image
    scaled to fill a 100x100 box centred on the 200x200 page."""
    return prefix + b"q 100 0 0 100 50 50 cm\n" + _inline(params, data) + b"Q\n"


# (a) /IM true stencil painted in a colour: 8x8 1-bpc, top half opaque
#     (sample 0 -> painted), bottom half transparent (sample 1). Fill red.
def _render_image_mask() -> bytes:
    stencil = bytes([0, 0, 0, 0, 0xFF, 0xFF, 0xFF, 0xFF])
    return _draw_inline(b"1 0 0 rg\n", b"/W 8 /H 8 /IM true", stencil)


# (b) /RGB 8-bpc inline image via /AHx.
def _render_ahx_rgb() -> bytes:
    rgb = bytes([200, 30, 30, 30, 200, 30, 30, 30, 200, 200, 200, 30])
    return _draw_inline(b"", b"/W 2 /H 2 /BPC 8 /CS /RGB /F /AHx", _ahx(rgb))


# (c) /Fl Flate inline image (DeviceGray gradient).
def _render_flate_gray() -> bytes:
    px = bytes(range(0, 256, 16))[:16]
    return _draw_inline(b"", b"/W 4 /H 4 /BPC 8 /CS /G /F /Fl", zlib.compress(px))


# (d) Full (long-form) key names — confirms both abbreviated and full forms
#     parse + paint identically. Same RGB raster as (b) but every key spelled
#     out (Width/Height/BitsPerComponent/ColorSpace/Filter + DeviceRGB +
#     ASCIIHexDecode).
def _render_full_keys_rgb() -> bytes:
    rgb = bytes([200, 30, 30, 30, 200, 30, 30, 30, 200, 200, 200, 30])
    params = (
        b"/Width 2 /Height 2 /BitsPerComponent 8 "
        b"/ColorSpace /DeviceRGB /Filter /ASCIIHexDecode"
    )
    return _draw_inline(b"", params, _ahx(rgb))


_RENDER_CASES: list[tuple[str, bytes]] = [
    ("image_mask_red", _render_image_mask()),
    ("ahx_rgb", _render_ahx_rgb()),
    ("flate_gray", _render_flate_gray()),
    ("full_keys_rgb", _render_full_keys_rgb()),
]


def _render_oracle_signature(
    tmp_path, pdf_bytes: bytes
) -> tuple[tuple[int, int], list[int]]:
    fixture = tmp_path / "inline_render.pdf"
    fixture.write_bytes(pdf_bytes)
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


@requires_oracle
@pytest.mark.parametrize(
    ("label", "content"),
    [(c[0], _build_render_pdf(c[1])) for c in _RENDER_CASES],
    ids=[c[0] for c in _RENDER_CASES],
)
def test_inline_image_render_matches_pdfbox(
    tmp_path, label: str, content: bytes
) -> None:
    """Full-page render parity: PDFRenderer paints each inline image the
    same way Java PDFBox does — exact dims + 16x16 luminance grid within
    perceptual tolerance."""
    (java_w, java_h), java_grid = _render_oracle_signature(tmp_path, content)

    with PDDocument.load(content) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _RENDER_MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_RENDER_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — inline image painted grossly differently"
    )
    assert maxdiff < _RENDER_MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_RENDER_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond AA / codec tolerance"
    )


@requires_oracle
def test_blank_inline_render_would_fail_tolerance(tmp_path) -> None:
    """Guard the render gate: a blank-white page is far from the painted
    inline-image reference, so the gate discriminates a real paint from a
    silently-dropped (unpainted) inline image."""
    content = _build_render_pdf(_render_image_mask())
    _dims, java_grid = _render_oracle_signature(tmp_path, content)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _RENDER_MAD_TOLERANCE, (
        "tolerance too loose: a blank render passes the inline-image MAD gate"
    )
