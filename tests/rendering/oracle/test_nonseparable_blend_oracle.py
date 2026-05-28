"""Live PDFBox differential parity for non-separable HSL blend-mode compositing.

Covers the four *non-separable* blend modes of PDF 32000-1 §11.3.5.3 set via
an ExtGState ``/BM`` entry (the ``gs`` operator): ``Hue`` / ``Saturation`` /
``Color`` / ``Luminosity``. Unlike the eleven separable modes (covered in
``test_blend_mode_oracle.py``), these operate on the **(Hue, Saturation,
Luminosity) decomposition** of source + backdrop, not per-channel:

* ``Hue``        — backdrop's S + L, source's H
                   ``SetLum(SetSat(Cs, Sat(Cb)), Lum(Cb))``
* ``Saturation`` — backdrop's H + L, source's S
                   ``SetLum(SetSat(Cb, Sat(Cs)), Lum(Cb))``
* ``Color``      — backdrop's L, source's H + S
                   ``SetLum(Cs, Lum(Cb))``
* ``Luminosity`` — backdrop's H + S, source's L
                   ``SetLum(Cb, Lum(Cs))``

The fixture is the same shape as the separable test (magenta-ish base over the
page, smaller top rectangle painted under the blend mode), but the base and
top colours are chosen so every HSL mode produces a clearly distinct overlap
RGB from the opaque source — see the precomputed table in
``_EXPECTED_OVERLAP_RGB`` below.

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing), so we
compare the same coarse fingerprint as ``test_render_oracle.py``: exact
rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against ``oracle/probes/RenderProbe.java``
(renders the page at 72 DPI).

The companion ``test_overlap_pixel_matches_spec_formula`` test pins each
mode's overlap centre pixel to the spec ``SetLum`` / ``SetSat`` /
``ClipColor`` composition, directly proving the §11.3.5.3 HSL decomposition
was used (vs an opaque-source render, vs a Y=0.299/0.587/0.114 luminance
formula mistakenly substituted for ``Lum`` = 0.30/0.59/0.11, vs the
separable per-channel fallback). This direct-pixel guard catches
``Luminosity`` in particular, where the blended luminance equals the source
luminance — the luminance grid alone cannot distinguish ``Luminosity`` from
``Normal``, so the chroma check is the real discriminator there.

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
# Same gate as test_render_oracle.py / test_blend_mode_oracle.py — well above
# the AA ceiling (correct blended renders measure MAD<=0.4 on small pages) yet
# well below the gross-failure floor (a render that ignored the blend would
# land at MAD 9+ on the H/S/Color rows; Luminosity is handled by the chroma
# guard below since its blended luminance equals the source luminance).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)

# Orange base + cool blue top: source has a clearly distinct hue *and*
# saturation *and* luminance vs the backdrop, so every HSL formula produces a
# materially different overlap colour from the opaque source. Precomputed
# expected overlap RGBs (per the §11.3.5.3 spec formulas, integer-rounded
# from 0..1 floats) are pinned in ``_EXPECTED_OVERLAP_RGB`` below.
_BASE_RGB = (0.9, 0.4, 0.1)
_TOP_RGB = (0.2, 0.4, 0.8)

# Opaque source overlap RGB (Normal mode == top RGB).
_NORMAL_OVERLAP_RGB = tuple(round(c * 255) for c in _TOP_RGB)  # (51, 102, 204)

# Expected centre-pixel RGB for each non-separable mode at the overlap. These
# come from the spec's HSL composition (Lum = 0.30R + 0.59G + 0.11B; SetSat
# preserves component ordering; ClipColor preserves luminance while clamping)
# applied to (_BASE_RGB, _TOP_RGB). Validated against the upstream
# ``BlendMode.java`` non-separable helpers (PDFBox 3.0.7).
_EXPECTED_OVERLAP_RGB: dict[str, tuple[int, int, int]] = {
    "Hue":        (77, 137, 255),
    "Saturation": (205, 109, 52),
    "Color":      (85, 136, 238),
    "Luminosity": (188, 70, 0),
}

_MODES = list(_EXPECTED_OVERLAP_RGB.keys())


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
    """Orange base rect over the whole page, then a blue rect painted under
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
def test_nonseparable_blend_mode_render_matches_pdfbox(
    mode: str, tmp_path: Path
) -> None:
    fixture = tmp_path / f"hsl_{mode}.pdf"
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

    # (b) Perceptual grid parity within tolerance. Java PDFBox and pypdfbox
    # both implement the same §11.3.5.3 HSL formula, so their 16x16 grids
    # must agree within AA tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{mode}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — HSL blend diverges from PDFBox, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{mode}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("mode", _MODES, ids=_MODES)
def test_overlap_pixel_matches_spec_formula(
    mode: str, tmp_path: Path
) -> None:
    """Pin the §11.3.5.3 HSL composition: the centre of the overlap region
    must equal the spec-computed RGB (within small AA tolerance), proving:

    * The blend mode was actually exercised (vs rendered as ``Normal`` —
      would yield the opaque source colour (51, 102, 204)).
    * The HSL decomposition uses ``Lum`` = 0.30R + 0.59G + 0.11B (per spec),
      not the Rec. 601 Y = 0.299/0.587/0.114 luminance formula.
    * The full RGB-triple composition is used, not a per-channel separable
      fallback (a per-channel formula cannot reproduce the spec's
      ``SetSat`` / ``SetLum`` / ``ClipColor`` arithmetic).

    This is the direct discriminator for ``Luminosity`` in particular —
    its blended luminance equals the source luminance, so the 16x16
    luminance grid alone cannot distinguish ``Luminosity`` from ``Normal``;
    the chroma check here is the load-bearing guard for that mode.
    """
    fixture = tmp_path / f"hsl_{mode}.pdf"
    _build_blend_fixture(fixture, mode)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # Centre of the 60x60 top rect (user-space 20..80) — device px (50, 50).
    cr, cg, cb = img.getpixel((50, 50))
    expected = _EXPECTED_OVERLAP_RGB[mode]

    # Within a small AA/rounding tolerance of the spec-blended colour …
    assert all(abs((cr, cg, cb)[i] - expected[i]) <= 4 for i in range(3)), (
        f"{mode}: overlap pixel {(cr, cg, cb)} != spec-blended {expected} "
        f"(tolerance 4 per channel) — HSL formula wrong or not applied"
    )
    # … and clearly NOT the opaque source colour (would indicate the blend
    # mode was ignored and the source painted as Normal).
    assert (cr, cg, cb) != _NORMAL_OVERLAP_RGB, (
        f"{mode}: overlap shows opaque source {_NORMAL_OVERLAP_RGB} — "
        "the blend mode was ignored and the top painted as Normal"
    )


@requires_oracle
def test_ignored_nonseparable_blend_would_fail_chroma_guard(
    tmp_path: Path,
) -> None:
    """Guard the chroma gate: if the ``/BM`` entry is stripped (so the top
    paints opaque as ``Normal``) the overlap centre pixel for ``Color``
    must clearly diverge from the expected HSL-blended RGB, proving the
    chroma assertion above detects an ignored non-separable blend rather
    than passing everything. Uses ``Color`` — its expected (85, 136, 238)
    vs the Normal opaque source (51, 102, 204) sits well outside the
    per-channel tolerance of 4."""
    from pypdfbox.cos import COSName  # noqa: PLC0415

    fixture = tmp_path / "hsl_Color.pdf"
    _build_blend_fixture(fixture, "Color")

    bm = COSName.get_pdf_name("BM")
    resources = COSName.get_pdf_name("Resources")
    ext_g_state = COSName.get_pdf_name("ExtGState")
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        egs = (
            page.get_cos_object()
            .get_dictionary_object(resources)
            .get_dictionary_object(ext_g_state)
        )
        for key in list(egs.key_set()):
            gs = egs.get_dictionary_object(key)
            if gs.get_dictionary_object(bm) is not None:
                gs.remove_item(bm)
        img = (
            PDFRenderer(doc)
            .render_image_with_dpi(0, 72.0)
            .convert("RGB")
        )
    cr, cg, cb = img.getpixel((50, 50))
    expected = _EXPECTED_OVERLAP_RGB["Color"]

    max_channel_delta = max(abs((cr, cg, cb)[i] - expected[i]) for i in range(3))
    assert max_channel_delta > 4, (
        "tolerance too loose: an ignored non-separable blend mode passes "
        f"the per-channel chroma gate (got {(cr, cg, cb)} vs expected "
        f"blended {expected}, max delta {max_channel_delta})"
    )
