"""Live PDFBox differential parity for separable blend-mode compositing.

Covers the eleven *separable* blend modes of PDF 32000-1 §11.3.5.1 set via
an ExtGState ``/BM`` entry (the ``gs`` operator): ``Multiply`` / ``Screen`` /
``Overlay`` / ``Darken`` / ``Lighten`` / ``ColorDodge`` / ``ColorBurn`` /
``HardLight`` / ``SoftLight`` / ``Difference`` / ``Exclusion``.

Each fixture is a tiny one-page PDF: a magenta base rectangle filling the
page, then a smaller green rectangle painted *over* it under one blend mode.
The overlap region must therefore show the **blended** colour (per the §11.3.5
formula), not the green top opaque (blend ignored) and not the magenta base
unchanged (top dropped). The base/top colours were chosen so every mode's
blended luminance differs from the opaque-top luminance by >= 27 (per cell),
which is what makes the gate below a real discriminator.

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a
16x16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). The gate is
the proven discriminator from ``test_render_oracle.py``. Measured here, every
mode's correct blended render lands at MAD <= 0.4 / MAXDIFF <= 1, while a
render that *ignores* the blend (green top painted opaque) lands at
MAD 9.7-42.8 / MAXDIFF 27-120 — well outside the gate (see the dedicated
guard test below).

Fixtures are synthesised in-memory via pypdfbox's own content-stream API
(``PDPageContentStream.set_blend_mode`` writes the ExtGState ``/BM``), so the
test is self-contained.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_render_oracle.py — comfortably above the AA ceiling
# (correct blended renders measure MAD<=0.4) yet well below the gross-failure
# floor (an ignored blend = MAD 9.7-42.8 depending on mode).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)

# Magenta base + green top: chosen so the §11.3.5 blended luminance differs
# from the opaque-top luminance by >= 27 per cell for *every* separable mode,
# making the MAD gate a genuine "did the blend happen?" discriminator.
_BASE_RGB = (0.9, 0.15, 0.9)
_TOP_RGB = (0.55, 0.9, 0.55)

# The eleven separable blend modes (PDF 32000-1 §11.3.5.1). ``Normal`` is the
# no-op baseline already covered by test_render_oracle.py, so it's excluded.
_MODES = [
    "Multiply",
    "Screen",
    "Overlay",
    "Darken",
    "Lighten",
    "ColorDodge",
    "ColorBurn",
    "HardLight",
    "SoftLight",
    "Difference",
    "Exclusion",
]


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


def _build_blend_fixture(path: Path, mode: str) -> None:
    """Magenta base rect over the whole page, then a green rect painted under
    ``mode`` (set via an ExtGState ``/BM``) overlapping the centre."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(*_BASE_RGB)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.set_blend_mode(mode)
    cs.set_non_stroking_color(*_TOP_RGB)
    cs.add_rect(20, 20, 60, 60)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


@requires_oracle
@pytest.mark.parametrize("mode", _MODES, ids=_MODES)
def test_blend_mode_render_matches_pdfbox(mode: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"blend_{mode}.pdf"
    _build_blend_fixture(fixture, mode)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{mode}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance. A blend that is ignored
    # (top opaque), dropped (base unchanged), or computed with the wrong
    # formula lands far outside this gate (see the guard test below).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{mode}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — blend ignored/wrong formula, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{mode}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_overlap_region_is_actually_blended(tmp_path: Path) -> None:
    """Verify the blend *happened*: the overlap centre pixel for Multiply
    must equal the per-channel product of base and top (not the opaque top,
    not the unchanged base). This is the direct-pixel companion to the
    fingerprint gate — it pins the actual §11.3.5.1 formula rather than just
    "different from blank"."""
    fixture = tmp_path / "blend_Multiply.pdf"
    _build_blend_fixture(fixture, "Multiply")

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # Centre of the 60x60 top rect (user-space 20..80) — device px (50, 50).
    cr, cg, cb = img.getpixel((50, 50))

    # Multiply(base, top) per channel, in 0..255.
    exp = tuple(round(_BASE_RGB[i] * _TOP_RGB[i] * 255) for i in range(3))
    top = tuple(round(_TOP_RGB[i] * 255) for i in range(3))
    base = tuple(round(_BASE_RGB[i] * 255) for i in range(3))

    # Within a small AA/rounding tolerance of the multiplied colour …
    assert all(abs((cr, cg, cb)[i] - exp[i]) <= 4 for i in range(3)), (
        f"Multiply overlap pixel {(cr, cg, cb)} != expected blended {exp}"
    )
    # … and clearly NOT the opaque top or the unchanged base.
    assert (cr, cg, cb) != top, "overlap shows opaque top — blend was ignored"
    assert (cr, cg, cb) != base, "overlap shows base — top was dropped"


@requires_oracle
def test_ignored_blend_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering a blend fixture with the ``/BM`` entry
    stripped (green top painted opaque, i.e. blend ignored) must land outside
    tolerance, proving the gate detects an ignored blend rather than passing
    everything. Uses ``Multiply`` (the strongest discriminator here)."""
    from pypdfbox.cos import COSName  # noqa: PLC0415

    fixture = tmp_path / "blend_Multiply.pdf"
    _build_blend_fixture(fixture, "Multiply")
    _dims, java_grid = _oracle_signature(fixture)

    bm = COSName.get_pdf_name("BM")
    resources = COSName.get_pdf_name("Resources")
    ext_g_state = COSName.get_pdf_name("ExtGState")
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        egs = page.get_cos_object().get_dictionary_object(
            resources
        ).get_dictionary_object(ext_g_state)
        for key in list(egs.key_set()):
            gs = egs.get_dictionary_object(key)
            if gs.get_dictionary_object(bm) is not None:
                gs.remove_item(bm)
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored blend mode passes the MAD gate"
    )
