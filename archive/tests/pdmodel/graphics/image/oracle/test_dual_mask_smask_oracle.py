"""Live PDFBox differential parity for an image XObject carrying **both**
``/Mask`` and ``/SMask`` (PDF 32000-1 §8.9.6 / §11.6.5.1).

The spec leaves results "unspecified" when both forms coexist, so the parity
target is whatever Apache PDFBox actually does — verified via the 3.0.7 oracle
``RenderProbe``. Disassembling ``PDImageXObject.getImage(Rectangle, int)``
(jbytecode) shows the explicit ordering:

``getSoftMask()`` and ``getMask()`` are both fetched, then the SMask branch is
preferred over the explicit-mask branch — when SMask is non-null PDFBox always
takes the SMask path and the explicit /Mask stream is silently dropped. (The
color-key form is a different /Mask shape — an array — and is applied at base
decode regardless.) So for dual-stream /Mask + /SMask the rendered parity
target is simply "/SMask wins".

This complements:

* ``test_soft_mask_oracle.py`` (each of /SMask, explicit /Mask, color-key /Mask
  on their own) — covers the single-mask paths.
* ``test_smask_matte_oracle.py`` (/SMask /Matte, /Decode, 4-bpc bpc).
* ``test_image_decode_mask_oracle.py`` (/Decode + /ImageMask stencil paint).

Fixtures: a one-page PDF with an RGB image authored via ``LosslessFactory``,
where we attach BOTH an explicit 1-bpc stencil /Mask (left half = masked out)
AND an 8-bit luminosity /SMask (left→right alpha ramp). Both are committed
into the image's COS dict. PDFBox renders the SMask alpha and ignores the
stencil — pypdfbox must do the same. Pixel-EXACT parity is impossible (Pillow
vs Java2D AA), so we compare the proven coarse fingerprint: exact rendered
dimensions plus a 16x16 average-luminance grid, gated at ``MAD < 6`` /
``MAXDIFF < 60`` (matches the other rendering oracle gates).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_soft_mask_oracle.py / test_smask_matte_oracle.py.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt


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


def _build_dual_mask_smask_fixture(path: Path) -> None:
    """Author a single image XObject carrying BOTH:

    * an explicit 1-bpc ``/Mask`` stencil knocking out the *left* half, and
    * an 8-bit luminosity ``/SMask`` left→right alpha ramp,

    composited over a black backdrop. Per PDFBox the SMask wins — the
    rendered result is the ramp-modulated white image (black on the left,
    full white on the right), with the stencil silently ignored. The
    fixture exists to prove pypdfbox follows the same ordering (smask wins,
    not the explicit /Mask, and not both at once)."""
    base = Image.new("RGB", (_IMG, _IMG), (255, 255, 255))

    # /SMask: left→right 0..255 luminance ramp (alpha) — fully opaque on
    # the right, fully transparent on the left. High contrast against the
    # black backdrop makes the parity-vs-divergence signal large.
    alpha = Image.new("L", (_IMG, _IMG))
    apx = alpha.load()
    for x in range(_IMG):
        col = round(x * 255 / (_IMG - 1))
        for y in range(_IMG):
            apx[x, y] = col
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)

    # /Mask explicit stencil: right half = 1 (masked out), left half = 0
    # (painted). Deliberately picks the *high-alpha* half of the SMask ramp
    # to knock out so that any code path that combined /Mask with /SMask
    # would delete the brightest end of the painted image. The SMask-only
    # PDFBox reference renders that bright region fully, so a "combine
    # both" regression diverges far past the MAD gate (proven by the guard
    # test below).
    stencil = Image.new("1", (_IMG, _IMG), 0)
    spx = stencil.load()
    for x in range(_IMG):
        val = 1 if x >= _IMG // 2 else 0
        for y in range(_IMG):
            spx[x, y] = val

    doc, page = _new_doc_page()
    # LosslessFactory splits RGBA into RGB raster + 8-bit /SMask.
    image = LosslessFactory.create_from_image(doc, rgba)
    assert image.has_soft_mask()
    # Attach the stencil as /Mask on the same base image — both entries
    # now coexist on the same COS dict.
    mask = LosslessFactory.create_from_image(doc, stencil)
    mask.set_image_mask(True)
    image.set_mask(mask)
    assert image.has_explicit_mask()
    assert image.has_soft_mask()

    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.0, 0.0, 0.0))
    cs.draw_image(image, 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


@requires_oracle
def test_dual_mask_smask_renders_smask_path(tmp_path: Path) -> None:
    """When an image carries both /Mask (explicit stencil) and /SMask,
    PDFBox 3.0.7 applies only the /SMask. pypdfbox must produce the same
    rendered fingerprint within the standard MAD/MAXDIFF gate."""
    fixture = tmp_path / "dual_mask_smask.pdf"
    _build_dual_mask_smask_fixture(fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        "dual /Mask+/SMask: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"dual /Mask+/SMask: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — likely composing both masks, but PDFBox "
        "applies only /SMask in this case"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"dual /Mask+/SMask: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_composing_both_masks_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: if pypdfbox were to *combine* /Mask AND /SMask (the
    naive interpretation of "both"), the contradictory left-half stencil
    would zero-out the right edge of the SMask ramp and the rendered grid
    would diverge from the SMask-only PDFBox reference. Simulating that
    composition by multiplying the SMask alpha by the stencil alpha must
    score outside the MAD gate, proving the parity test would detect it."""
    fixture = tmp_path / "dual_mask_smask.pdf"
    _build_dual_mask_smask_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    # Render with both masks composed: combine the SMask ramp with the
    # right-half-zero stencil so the *high-alpha* end of the SMask vanishes
    # — a visually dramatic departure from the SMask-only PDFBox reference.
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    rgba = img.convert("RGBA")
    width, height = rgba.size
    px = rgba.load()
    # Image was painted at user-space (40, 60) sized 120x120. The page is
    # 200pt; render at 72 DPI ⇒ 1pt = 1px. So the image lives at
    # x ∈ [40, 160) in the rendered canvas. Zero out the *right*-half pixels
    # of that strip to simulate the stencil knocking out the bright end of
    # the SMask ramp.
    x_mid, x_hi = 100, 160
    for y in range(height):
        for x in range(x_mid, x_hi):
            r, g, b, _a = px[x, y]
            px[x, y] = (r, g, b, 0)
    # Re-flatten over the black backdrop the fixture uses.
    backdrop = Image.new("RGB", rgba.size, (0, 0, 0))
    backdrop.paste(rgba, (0, 0), rgba)
    simulated_grid = _grid_from_image(backdrop)

    diffs = [abs(a - b) for a, b in zip(java_grid, simulated_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: composing /Mask with /SMask still passes the "
        f"MAD gate (mad={mad:.2f}) — the parity test would not catch a "
        "regression that started honouring both"
    )
