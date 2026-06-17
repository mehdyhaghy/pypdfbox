"""Live PDFBox differential parity for blend-mode + constant-alpha (``/ca``)
compositing — the §11.3.6 "Interpretation of Alpha" interaction NOT covered by
``test_blend_mode_oracle.py`` or ``test_nonseparable_blend_oracle.py`` (both of
which paint the top rectangle *opaque*, so they pin only the pure blend
function ``B(Cb, Cs)``).

When a non-Normal ``/BM`` blend mode is combined with a non-stroking constant
alpha ``/ca`` < 1.0, the rendered colour is no longer the pure blend. Per PDF
32000-1 §11.3.6 the result composites the *blended* colour over the backdrop
weighted by the source alpha::

    Cr = (1 - as/ar)*Cb + (as/ar)*[(1-ab)*Cs + ab*B(Cb,Cs)]

With an opaque backdrop (``ab = 1``, ``ar = 1``) this collapses to::

    Cr = (1 - as)*Cb + as*B(Cb, Cs)          where as = /ca

So at ``/ca = 0.5`` every pixel in the overlap is the midpoint between the
backdrop colour and the pure-blend colour. A renderer that:

* applies the blend but ignores ``/ca`` (paints the pure blend opaquely), or
* applies ``/ca`` but ignores the blend (alpha-composites the *source* colour,
  not the blended colour), or
* multiplies ``/ca`` into the wrong term,

all land far outside the gate against the correct oracle render. The opaque-top
oracles cannot catch any of these because they fix ``/ca = 1``.

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the proven coarse
fingerprint: exact rendered dimensions plus a 16x16 average-luminance grid,
gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/BlendAlphaProbe.java`` (72 DPI render — identical luminance
math to ``RenderProbe``, dedicated named probe per the wave brief). The
companion direct-pixel test pins the §11.3.6 midpoint formula for ``Multiply``.

Fixtures are synthesised in-memory via pypdfbox's own content-stream API
(``set_blend_mode`` + ``set_non_stroking_alpha_constant`` both write to the
graphics state via ``gs``), so the test is self-contained.
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
# Same gate as test_blend_mode_oracle.py — comfortably above the AA ceiling
# yet well below the gross-failure floor. With /ca = 0.5 the overlap colour is
# the midpoint of backdrop and pure-blend; ignoring /ca (pure blend opaque) or
# ignoring the blend (source over backdrop) both diverge well past this (see
# the dedicated guard tests below).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)

# Magenta backdrop + green top (same colours as the separable opaque-top
# oracle), now painted at /ca = 0.5 under each blend mode. Chosen so the
# §11.3.6 midpoint colour differs materially from both the pure blend and the
# alpha-composited *source*.
_BASE_RGB = (0.9, 0.15, 0.9)
_TOP_RGB = (0.55, 0.9, 0.55)
_CA = 0.5

# Cover a representative spread of separable modes plus one non-separable
# (Luminosity exercises the HSL decomposition path through the alpha mix).
_MODES = [
    "Multiply",
    "Screen",
    "Difference",
    "HardLight",
    "Luminosity",
]


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``BlendAlphaProbe.java`` (integer-division of pixel coord over image size,
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
    """Run BlendAlphaProbe on page 0 and parse its (dims, 16x16 grid).

    The probe emits the grid comma-separated (matching ``ImageMaskProbe``);
    using a dedicated probe keeps the parsing format obvious from the
    probe-name in the test."""
    lines = run_probe_text("BlendAlphaProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _build_blend_alpha_fixture(path: Path, mode: str) -> None:
    """Magenta base rect over the whole page, then a green rect painted under
    ``mode`` at ``/ca = 0.5`` overlapping the centre. Both ``/BM`` and ``/ca``
    are set via ``gs`` (separate ExtGState dicts; the graphics state carries
    both forward to the top fill)."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(*_BASE_RGB)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.set_blend_mode(mode)
    cs.set_non_stroking_alpha_constant(_CA)
    cs.set_non_stroking_color(*_TOP_RGB)
    cs.add_rect(20, 20, 60, 60)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


@requires_oracle
@pytest.mark.parametrize("mode", _MODES, ids=_MODES)
def test_blend_alpha_render_matches_pdfbox(mode: str, tmp_path: Path) -> None:
    """Each blend-mode + ``/ca`` variant must match Java PDFBox's render of
    the same fixture within the 16x16 fingerprint gate."""
    fixture = tmp_path / f"blend_alpha_{mode}.pdf"
    _build_blend_alpha_fixture(fixture, mode)

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

    # (b) Perceptual grid parity within tolerance. The §11.3.6 alpha mix of
    # backdrop + blend must agree with PDFBox within AA tolerance; a renderer
    # that mis-weights /ca lands outside the gate (see guard tests below).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{mode}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — blend+/ca mis-composited, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{mode}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_overlap_pixel_matches_alpha_blend_formula(tmp_path: Path) -> None:
    """Pin the §11.3.6 alpha-aware blend: for ``Multiply`` at ``/ca = 0.5``
    over an opaque backdrop, the overlap centre pixel must equal the midpoint
    of the backdrop colour and the pure-Multiply colour:

        Cr = (1 - ca)*Cb + ca*(Cb * Cs)

    This directly distinguishes the correct §11.3.6 composition from the two
    plausible bugs the opaque-top oracle cannot see: ignoring ``/ca`` (would
    yield the pure-blend colour) and ignoring the blend (would yield the
    alpha-composited *source* colour ``(1-ca)*Cb + ca*Cs``)."""
    fixture = tmp_path / "blend_alpha_Multiply.pdf"
    _build_blend_alpha_fixture(fixture, "Multiply")

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # Centre of the 60x60 top rect (user-space 20..80) — device px (50, 50).
    cr, cg, cb = img.getpixel((50, 50))

    # Pure Multiply(base, top) per channel, then alpha-mix with backdrop.
    blend = [_BASE_RGB[i] * _TOP_RGB[i] for i in range(3)]
    expected = tuple(
        round(((1 - _CA) * _BASE_RGB[i] + _CA * blend[i]) * 255) for i in range(3)
    )
    # The two bugs the opaque-top oracle cannot distinguish:
    pure_blend = tuple(round(blend[i] * 255) for i in range(3))
    source_over = tuple(
        round(((1 - _CA) * _BASE_RGB[i] + _CA * _TOP_RGB[i]) * 255) for i in range(3)
    )

    assert all(abs((cr, cg, cb)[i] - expected[i]) <= 4 for i in range(3)), (
        f"Multiply+/ca overlap pixel {(cr, cg, cb)} != §11.3.6 midpoint "
        f"{expected} (tolerance 4 per channel)"
    )
    assert (cr, cg, cb) != pure_blend, (
        f"overlap shows pure blend {pure_blend} — /ca was ignored"
    )
    assert (cr, cg, cb) != source_over, (
        f"overlap shows alpha-composited source {source_over} — blend ignored"
    )


@requires_oracle
def test_ignored_ca_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the ``Multiply`` fixture with the ``/ca``
    ExtGState entry stripped (top painted as the *pure blend*, fully opaque)
    must land outside tolerance against the correct ``/ca = 0.5`` oracle
    render — proving the gate detects an ignored constant alpha rather than
    passing both. ``Multiply`` is the strongest discriminator here."""
    from pypdfbox.cos import COSName  # noqa: PLC0415

    fixture = tmp_path / "blend_alpha_Multiply.pdf"
    _build_blend_alpha_fixture(fixture, "Multiply")
    _dims, java_grid = _oracle_signature(fixture)

    ca_key = COSName.get_pdf_name("ca")
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
            if gs.get_dictionary_object(ca_key) is not None:
                gs.remove_item(ca_key)
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored /ca (pure-blend opaque) passes the "
        f"MAD gate (observed mad={mad:.2f})"
    )
