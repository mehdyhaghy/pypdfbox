"""Live PDFBox differential parity for image ``/SMask`` *matte*, ``/SMask``
``/Decode`` and non-8-bit ``/SMask`` compositing.

Complements ``test_soft_mask_oracle.py`` (plain /SMask alpha) and
``test_image_decode_mask_oracle.py`` (/Decode on the base image + stencil
polarity). The edge cases here all live on the *soft mask* itself:

* **/Matte (PDF §11.6.5.3)** — when a soft mask carries a ``/Matte`` array, the
  base image's colour samples were *pre-blended* against that matte colour, so
  the renderer must *un-pre-multiply* before compositing:
  ``c = matte + (c' - matte) / alpha`` (PDFBox ``applyMask`` Q16.15 path). We
  pre-blend a solid red against a 50%-grey matte at a left→right alpha ramp;
  correct un-premultiplication recovers solid red everywhere alpha>0, so over a
  matching 50%-grey page the painted region reads as a clean red fade. Ignoring
  the matte (treating it as 0) leaves the darkened pre-blended colour, which
  diverges from the PDFBox reference — the guard test below proves it.
* **/SMask with /Decode [1 0]** — an inverted-alpha decode on the soft mask. A
  left→right alpha ramp under ``/Decode [1 0]`` becomes right→left.
* **4-bpc /SMask** — a soft mask with /BitsPerComponent 4 (samples 0..15),
  which must be scaled to 8-bit alpha, not used raw.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA), so we compare the same
coarse fingerprint the page-render oracle uses: exact rendered dimensions plus
a 16x16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI).

Fixtures are tiny one-page PDFs synthesised in-memory: the RGB base + 8-bit
SMask are produced by pypdfbox's ``LosslessFactory``, then the SMask's COS dict
is mutated to carry the /Matte, /Decode or 4-bpc raster under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt
_MATTE = (0.5, 0.5, 0.5)  # 50% grey matte / page backdrop


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell)."""
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


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run RenderProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _fill_backdrop(cs: PDPageContentStream, rgb: tuple[float, float, float]) -> None:
    cs.set_non_stroking_color(*rgb)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()


def _alpha_ramp(reverse: bool = False) -> Image.Image:
    """Left→right 0..255 alpha ramp (or right→left if ``reverse``)."""
    alpha = Image.new("L", (_IMG, _IMG))
    apx = alpha.load()
    for x in range(_IMG):
        col = round(x * 255 / (_IMG - 1))
        if reverse:
            col = 255 - col
        for y in range(_IMG):
            apx[x, y] = col
    return alpha


def _smask_of(image) -> object:
    """Resolve the /SMask Image XObject COS dict on a base image."""
    return image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("SMask"))


def _build_matte_fixture(path: Path) -> None:
    """Solid *white* pre-blended against a 50% grey matte at a left→right
    alpha ramp, with the soft mask carrying ``/Matte [0.5 0.5 0.5]``,
    composited over a **black** page. Correct un-premultiplication recovers
    solid white (the true colour) before compositing over black, so the
    painted region reads as a clean white→black fade tracking the alpha
    ramp. Ignoring the matte composites the *darkened* pre-blended colour
    instead, which is materially dimmer (the matte and backdrop differ, so
    the premultiplied identity does not collapse) — the guard test asserts
    this divergence is outside tolerance."""
    true_color = (255, 255, 255)
    alpha = _alpha_ramp()
    apx = alpha.load()
    # Pre-blend: c' = matte*255 + (c - matte*255) * a/255  (premultiply).
    base = Image.new("RGB", (_IMG, _IMG))
    bpx = base.load()
    m = [round(v * 255) for v in _MATTE]
    for x in range(_IMG):
        for y in range(_IMG):
            a = apx[x, y] / 255.0
            bpx[x, y] = tuple(
                round(m[i] + (true_color[i] - m[i]) * a) for i in range(3)
            )
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, rgba)
    smask = _smask_of(image)
    matte = COSArray()
    for v in _MATTE:
        matte.add(COSFloat(v))
    smask.set_item(COSName.get_pdf_name("Matte"), matte)
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.0, 0.0, 0.0))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_smask_decode_fixture(path: Path) -> None:
    """Solid red + grayscale /SMask left→right alpha ramp, but the soft mask
    carries ``/Decode [1 0]`` (inverted alpha): the painted region fades
    right→left instead. Over a blue backdrop."""
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    alpha = _alpha_ramp()
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, rgba)
    smask = _smask_of(image)
    decode = COSArray()
    decode.add(COSFloat(1.0))
    decode.add(COSFloat(0.0))
    smask.set_item(COSName.get_pdf_name("Decode"), decode)
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.3, 0.9))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_smask_4bpc_fixture(path: Path) -> None:
    """Solid red + a 4-bpc /SMask carrying a left→right alpha ramp (samples
    0..15, packed two-per-byte). Over a blue backdrop — same visual as the
    8-bit ramp, but the SMask raster must be scaled from 4-bit, not raw."""
    base = Image.new("RGB", (_IMG, _IMG), (220, 30, 30))
    # placeholder 8-bit alpha so LosslessFactory builds the /SMask scaffold.
    rgba = base.convert("RGBA")
    rgba.putalpha(_alpha_ramp())

    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, rgba)
    smask = _smask_of(image)

    # Author a 4-bpc gray raster: per-row 0..15 ramp, two samples per byte.
    row_bytes = (_IMG + 1) // 2
    packed = bytearray(row_bytes * _IMG)
    for y in range(_IMG):
        for x in range(_IMG):
            s4 = round(x * 15 / (_IMG - 1)) & 0x0F
            bi = y * row_bytes + (x // 2)
            if x % 2 == 0:
                packed[bi] = (packed[bi] & 0x0F) | (s4 << 4)
            else:
                packed[bi] = (packed[bi] & 0xF0) | s4
    smask.set_int(COSName.get_pdf_name("BitsPerComponent"), 4)
    # Replace the raw stream bytes (create_output_stream(None) drops any
    # existing /Filter so the raster is the packed 4-bpc samples as authored).
    with smask.create_output_stream() as out:
        out.write(bytes(packed))

    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.3, 0.9))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "smask_matte": _build_matte_fixture,
    "smask_decode_inverted": _build_smask_decode_fixture,
    "smask_4bpc": _build_smask_4bpc_fixture,
}


def _render_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_smask_matte_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _render_grid(fixture)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — SMask matte/decode/bpc mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_ignored_matte_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the matte fixture *without* /Matte (the
    soft mask treated as plain alpha, so the darkened pre-blended colour is
    composited) must land outside tolerance, proving matte handling matters."""
    fixture = tmp_path / "smask_matte.pdf"
    _build_matte_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    # Strip /Matte from the SMask, then render: pypdfbox composites the
    # pre-blended (darkened) base colour straight through the alpha.
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        for name in resources.get_x_object_names():
            xobj = resources.get_x_object(name)
            smask = xobj.get_cos_object().get_dictionary_object(
                COSName.get_pdf_name("SMask")
            )
            if smask is not None:
                smask.remove_item(COSName.get_pdf_name("Matte"))
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: ignoring /Matte still passes the MAD gate "
        f"(mad={mad:.2f}) — the matte un-premultiplication is not observable"
    )
