"""Live PDFBox differential parity for **sub-byte** (1/2/4 bpc) image-XObject
decode — ``PDImageXObject.get_image()`` over raw DeviceGray and Indexed
rasters whose samples are packed at fewer than 8 bits per component
(PDF 32000-1 §8.9.5.2, §7.4.4 row-byte alignment).

The 8-bit and 16-bit raster decode paths are oracle-pinned elsewhere
(``test_dct_decode_oracle.py``, ``test_image_16bit_oracle.py``); the 1-bit
CCITT bilevel raster is pinned by ``test_ccitt_image_oracle.py``. What is
NOT directly pinned at the ``getImage()`` level is the **generic sub-byte
bit-unpacker** for 2-bpc / 4-bpc samples and the per-row byte-padding it
must honour (a scanline is padded up to a byte boundary, §7.4.4 — a decoder
that packs rows contiguously across the byte boundary shears every row after
the first). Cases:

* **gray2_ramp** — 2-bpc DeviceGray, 4 distinct gray levels (0/1/2/3 →
  0/85/170/255). Width 22 forces a per-row pad (22*2 = 44 bits → 6 bytes,
  4 padding bits): a decoder that ignores the pad shears the ramp.
* **gray4_ramp** — 4-bpc DeviceGray, 16-level left→right ramp. Width 13
  forces a per-row pad (13*4 = 52 bits → 7 bytes, 4 padding bits).
* **gray4_decode** — same 4-bpc gray ramp with ``/Decode [1 0]`` — the
  ramp must render reversed (light→dark). A decoder that ignores /Decode
  on a sub-byte gray image renders the un-inverted ramp.
* **indexed4** — 4-bpc Indexed over a 16-entry DeviceRGB palette; each
  sample is a raw palette index (NOT decode-interpolated), so the
  recovered colour is the palette entry, not a scaled gray. A decoder
  that linearly maps the index to a gray value (the 8-bit-gray mistake)
  diverges grossly.
* **indexed2_decode** — 2-bpc Indexed over a 4-entry palette with
  ``/Decode [3 0]`` — the index ordering reverses (sample 0 → palette
  entry 3, etc.), per §8.9.5.2's Indexed-decode definition.

Pixel-EXACT parity across Java2D vs Pillow is impossible, so we compare the
proven coarse fingerprint emitted by ``oracle/probes/ImageExtractProbe.java``
(``getImage()`` decoded raster, exact w/h/bpc/cs + a 16x16 average-luminance
grid), gated at ``MAD < 6`` / ``MAXDIFF < 60``. w/h/bpc are asserted exact.

Fixtures are tiny one-page PDFs synthesised in-memory from raw packed sample
bytes (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the sibling image oracles — comfortably above the AA/codec
# ceiling, far below the gross-failure floor (a sheared row, ignored /Decode,
# or index-as-gray mistake all land well past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 200  # media-box side, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``ImageExtractProbe.java`` (integer-division of pixel coord over image
    size, clamped to the last cell). Matches PIL's "L" Rec.601 weights."""
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


def _oracle_image(fixture: Path) -> tuple[int, int, int, list[int]]:
    """Run ImageExtractProbe and parse the single image line as
    (w, h, bpc, 16x16 grid)."""
    lines = [
        ln for ln in run_probe_text("ImageExtractProbe", str(fixture)).splitlines() if ln
    ]
    assert len(lines) == 1, f"expected one image, probe emitted: {lines!r}"
    tokens = lines[0].split()
    # "image page <p> name <n> w <w> h <h> bpc <bpc> cs <cs> grid <256 ints>"
    w = int(tokens[tokens.index("w") + 1])
    h = int(tokens[tokens.index("h") + 1])
    bpc = int(tokens[tokens.index("bpc") + 1])
    grid_at = tokens.index("grid") + 1
    grid = [int(v) for v in tokens[grid_at:]]
    assert len(grid) == _GRID * _GRID
    return w, h, bpc, grid


def _pack_samples(samples: list[int], width: int, height: int, bpc: int) -> bytes:
    """MSB-first bit-pack of single-component samples with per-row padding to
    a byte boundary (PDF 32000-1 §7.4.4). ``samples`` is row-major,
    ``width * height`` long."""
    mask = (1 << bpc) - 1
    out = bytearray()
    for y in range(height):
        bit_buf = 0
        bit_cnt = 0
        for x in range(width):
            bit_buf = (bit_buf << bpc) | (samples[y * width + x] & mask)
            bit_cnt += bpc
            while bit_cnt >= 8:
                bit_cnt -= 8
                out.append((bit_buf >> bit_cnt) & 0xFF)
        if bit_cnt > 0:  # flush the row's trailing partial byte (padded with 0s)
            out.append((bit_buf << (8 - bit_cnt)) & 0xFF)
    return bytes(out)


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _draw_and_save(path: Path, image: PDImageXObject) -> None:
    """Place ``image`` on a one-page PDF over a black backdrop and save."""
    doc, page = _new_doc_page()
    # Re-bind the image's COS object into this document so its indirect
    # references resolve on save (the image is built free-standing).
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(0.0, 0.0, 0.0)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _gray_image(
    width: int,
    height: int,
    bpc: int,
    samples: list[int],
    decode: list[float] | None = None,
) -> PDImageXObject:
    stream = COSStream()
    stream.set_raw_data(_pack_samples(samples, width, height, bpc))
    image = PDImageXObject(stream)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    stream.set_item("ColorSpace", COSName.get_pdf_name("DeviceGray"))
    if decode is not None:
        arr = COSArray()
        for v in decode:
            arr.add(COSFloat(v))
        stream.set_item("Decode", arr)
    return image


def _indexed_image(
    width: int,
    height: int,
    bpc: int,
    samples: list[int],
    palette: list[tuple[int, int, int]],
    decode: list[float] | None = None,
) -> PDImageXObject:
    """Indexed image: ``[/Indexed /DeviceRGB hival <lookup>]``."""
    hival = len(palette) - 1
    lookup = bytes(c for entry in palette for c in entry)
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("Indexed"))
    cs_array.add(COSName.get_pdf_name("DeviceRGB"))
    cs_array.add(COSInteger.get(hival))
    cs_array.add(COSString(lookup))

    stream = COSStream()
    stream.set_raw_data(_pack_samples(samples, width, height, bpc))
    image = PDImageXObject(stream)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    stream.set_item("ColorSpace", cs_array)
    if decode is not None:
        arr = COSArray()
        for v in decode:
            arr.add(COSFloat(v))
        stream.set_item("Decode", arr)
    return image


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------

_W2, _H2 = 22, 16  # 22*2 = 44 bits/row → 6 bytes, 4 padding bits
_W4, _H4 = 13, 16  # 13*4 = 52 bits/row → 7 bytes, 4 padding bits


def _build_gray2_ramp(path: Path) -> None:
    """2-bpc DeviceGray vertical bands: column x → level (x * 4 // width)."""
    samples = [min(3, x * 4 // _W2) for _y in range(_H2) for x in range(_W2)]
    _draw_and_save(path, _gray_image(_W2, _H2, 2, samples))


def _build_gray4_ramp(path: Path) -> None:
    """4-bpc DeviceGray left→right 16-level ramp."""
    samples = [min(15, x * 16 // _W4) for _y in range(_H4) for x in range(_W4)]
    _draw_and_save(path, _gray_image(_W4, _H4, 4, samples))


def _build_gray4_decode(path: Path) -> None:
    """4-bpc DeviceGray ramp with /Decode [1 0] — renders reversed."""
    samples = [min(15, x * 16 // _W4) for _y in range(_H4) for x in range(_W4)]
    _draw_and_save(path, _gray_image(_W4, _H4, 4, samples, decode=[1.0, 0.0]))


# Distinct, well-separated palette colours so a wrong index maps to a
# visibly wrong luminance.
_PALETTE16 = [
    (r, g, b)
    for r in (0, 255)
    for g in (0, 255)
    for b in (0, 255)
] + [
    (64, 64, 64),
    (128, 128, 128),
    (192, 192, 192),
    (255, 128, 0),
    (0, 128, 255),
    (128, 0, 128),
    (0, 255, 128),
    (255, 0, 128),
]


def _build_indexed4(path: Path) -> None:
    """4-bpc Indexed over the 16-entry palette; column x → index
    (x * 16 // width). Recovered colour = palette[index]."""
    samples = [min(15, x * 16 // _W4) for _y in range(_H4) for x in range(_W4)]
    _draw_and_save(path, _indexed_image(_W4, _H4, 4, samples, _PALETTE16))


_PALETTE4 = [
    (0, 0, 0),  # index 0 — black
    (255, 0, 0),  # index 1 — red
    (0, 255, 0),  # index 2 — green
    (255, 255, 255),  # index 3 — white
]


def _build_indexed2_decode(path: Path) -> None:
    """2-bpc Indexed over a 4-entry palette with /Decode [3 0] — the index
    ordering reverses so sample 0 → palette[3] (white), sample 3 →
    palette[0] (black)."""
    samples = [min(3, x * 4 // _W2) for _y in range(_H2) for x in range(_W2)]
    _draw_and_save(
        path, _indexed_image(_W2, _H2, 2, samples, _PALETTE4, decode=[3.0, 0.0])
    )


_BUILDERS = {
    "gray2_ramp": (_build_gray2_ramp, _W2, _H2, 2),
    "gray4_ramp": (_build_gray4_ramp, _W4, _H4, 4),
    "gray4_decode": (_build_gray4_decode, _W4, _H4, 4),
    "indexed4": (_build_indexed4, _W4, _H4, 4),
    "indexed2_decode": (_build_indexed2_decode, _W2, _H2, 2),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_sub_byte_image_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each sub-byte raster's pypdfbox ``get_image()`` decode must match
    Apache PDFBox's ``getImage()`` within the 16x16 fingerprint gate, with
    exact width/height/bpc."""
    builder, exp_w, exp_h, exp_bpc = _BUILDERS[label]
    fixture = tmp_path / f"{label}.pdf"
    builder(fixture)

    java_w, java_h, java_bpc, java_grid = _oracle_image(fixture)
    assert (java_w, java_h, java_bpc) == (exp_w, exp_h, exp_bpc)

    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        names = list(resources.get_x_object_names())
        assert len(names) == 1
        image = resources.get_x_object(names[0])
        py_img = image.get_image()
    assert py_img is not None, f"{label}: pypdfbox get_image() returned None"
    py_w, py_h = py_img.size
    py_grid = _grid_from_image(py_img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: decoded raster dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — sub-byte samples mis-unpacked, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond codec rounding"
    )


@requires_oracle
def test_gray4_decode_inverts_ramp(tmp_path: Path) -> None:
    """Direct proof the sub-byte gray /Decode [1 0] is honoured: with the
    default decode the LEFT of the image is dark (sample 0) and the RIGHT
    light (sample 15); /Decode [1 0] flips this so the LEFT is light and the
    RIGHT dark. A decoder that ignores /Decode on a sub-byte gray raster
    renders the un-inverted ramp (left dark)."""
    plain = tmp_path / "gray4_ramp.pdf"
    inverted = tmp_path / "gray4_decode.pdf"
    _build_gray4_ramp(plain)
    _build_gray4_decode(inverted)

    def left_right_luma(fixture: Path) -> tuple[float, float]:
        with PDDocument.load(fixture) as doc:
            names = list(doc.get_page(0).get_resources().get_x_object_names())
            img = doc.get_page(0).get_resources().get_x_object(names[0]).get_image()
        gray = img.convert("L")
        w, h = gray.size
        px = gray.load()
        third = max(1, w // 3)
        left = sum(px[x, y] for y in range(h) for x in range(third)) / (third * h)
        right = sum(
            px[w - 1 - x, y] for y in range(h) for x in range(third)
        ) / (third * h)
        return left, right

    pl, pr = left_right_luma(plain)
    il, ir = left_right_luma(inverted)
    # Plain ramp: left dark, right light.
    assert pr - pl > 40, f"plain ramp not left-dark→right-light (l={pl:.1f} r={pr:.1f})"
    # Inverted ramp: left light, right dark.
    assert il - ir > 40, (
        f"/Decode [1 0] not applied to sub-byte gray (l={il:.1f} r={ir:.1f})"
    )


@requires_oracle
def test_indexed4_uses_palette_not_gray(tmp_path: Path) -> None:
    """Direct proof Indexed sub-byte samples are palette lookups, not
    linearly-scaled gray. Palette index 1 is pure blue (``(0, 0, 255)``,
    luma ≈ 29); if the decoder treated the index as an 8-bit-scaled gray it
    would render index 1 as a neutral gray (1/15 * 255 ≈ 17 on all three
    channels). The recovered raster must contain a clearly *blue-dominant*
    pixel for the index-1 column, which a gray decode can never produce."""
    fixture = tmp_path / "indexed4.pdf"
    _build_indexed4(fixture)
    assert _PALETTE16[1] == (0, 0, 255)  # guard the assumption below
    with PDDocument.load(fixture) as doc:
        names = list(doc.get_page(0).get_resources().get_x_object_names())
        img = doc.get_page(0).get_resources().get_x_object(names[0]).get_image()
    rgb = img.convert("RGB")
    # index = x * 16 // width; index 1 occupies a band near the left.
    band1_x = next(x for x in range(_W4) if x * 16 // _W4 == 1)
    r, g, b = rgb.getpixel((band1_x, _H4 // 2))
    assert b > 150 and r < 80 and g < 80, (
        f"indexed4 index-1 pixel {(r, g, b)} is not palette blue — "
        "Indexed samples decoded as gray, not palette lookups"
    )
