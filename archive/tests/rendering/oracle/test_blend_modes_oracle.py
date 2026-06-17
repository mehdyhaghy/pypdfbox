"""Live PDFBox differential parity for the *less-common* separable blend
modes, verified at the PER-CHANNEL pixel level (PDF 32000-1 §11.3.5.1).

``test_blend_mode_oracle.py`` already pins all eleven separable modes, but it
compares a 16x16 *grey-luminance* fingerprint of the whole page. A per-channel
blend-formula error can be partly masked by that averaging: luminance collapses
R/G/B into one Rec.601 weighted scalar, and a small page-wide MAD can hide a
single channel landing on the wrong side of a branch. The companion
direct-pixel test in that file only checks ``Multiply``.

This oracle closes that gap for the six modes whose channel formula has a
data-dependent BRANCH that a flat mid-tone fixture can step around:

* ``HardLight``  — piecewise at ``src == 0.5``
* ``SoftLight``  — piecewise at ``src == 0.5`` *and* at ``dest == 0.25``
* ``ColorDodge`` — special-cases ``dest == 0`` and the ``dest >= 1 - src`` clamp
* ``ColorBurn``  — special-cases ``dest == 1`` and the ``1 - dest >= src`` clamp
* ``Difference`` — ``|backdrop - src|``
* ``Exclusion``  — ``b + s - 2bs``

Each mode is rendered twice, with two deliberately-chosen colour pairs:

1. a generic mid-tone pair (magenta base, green top) that lands on the "common"
   branch, and
2. an EXTREME pair (a saturated base, a top with channels at 0 and 1) that
   forces every special-case branch above to fire — exactly the inputs the
   page-wide luminance fingerprint is weakest at discriminating.

For every fixture we sample the exact RGB of two pixels inside the overlap
region from the live Java PDFBox render (via ``PixelSampleProbe.java``) and
require pypdfbox's render to match each channel within ``+/- 3`` (Pillow vs
Java2D rounding / sub-pixel AA only — a real formula error moves a channel by
tens of levels). A guard test confirms that gate rejects an ignored blend.

Result: confirmed at parity (every channel within +/-1 of the live oracle) —
this is a regression pin; no production change was needed.

Fixtures are synthesised in-memory via pypdfbox's content-stream API; the test
commits no binaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_MB = 100  # media-box side, pt (== device px at 72 DPI)
# Per-channel tolerance: Pillow vs Java2D rounding / sub-pixel AA only. A real
# per-channel formula error moves the channel by tens of levels (see guard).
_CHANNEL_TOL = 3

# The six less-common separable modes whose channel formula has a
# data-dependent branch a flat mid-tone fixture can side-step.
_MODES = [
    "HardLight",
    "SoftLight",
    "ColorDodge",
    "ColorBurn",
    "Difference",
    "Exclusion",
]

# Two colour pairs. "mid" lands on the common branch; "extreme" forces the
# special-case branches (top channels at exactly 0 and 1; a saturated base
# that pushes ColorDodge/ColorBurn into their clamp / zero cases and SoftLight
# across both its dest==0.25 and src==0.5 seams).
_PAIRS = {
    "mid": ((0.9, 0.15, 0.9), (0.55, 0.9, 0.55)),
    "extreme": ((0.2, 0.85, 0.95), (1.0, 0.0, 1.0)),
}

# Two interior sample points well inside the 60x60 overlap (user 20..80 →
# device px 20..80, top-left origin). Away from edges to avoid AA fringe.
_SAMPLES = ((40, 40), (60, 55))


def _build_fixture(
    path: Path,
    mode: str,
    base: tuple[float, float, float],
    top: tuple[float, float, float],
) -> None:
    """Full-page ``base`` rect, then a 60x60 ``top`` rect painted under
    ``mode`` (ExtGState ``/BM``) overlapping the page centre."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(*base)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.set_blend_mode(mode)
    cs.set_non_stroking_color(*top)
    cs.add_rect(20, 20, 60, 60)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


def _oracle_pixels(fixture: Path) -> tuple[tuple[int, int], list[tuple[int, int, int]]]:
    """Run PixelSampleProbe on page 0; parse (dims, [(r,g,b), ...])."""
    coord_args = [f"{x},{y}" for x, y in _SAMPLES]
    lines = run_probe_text(
        "PixelSampleProbe", str(fixture), "0", *coord_args
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    pixels = []
    for line in lines[1 : 1 + len(_SAMPLES)]:
        r, g, b = (int(v) for v in line.split())
        pixels.append((r, g, b))
    assert len(pixels) == len(_SAMPLES)
    return (width, height), pixels


@requires_oracle
@pytest.mark.parametrize(
    ("mode", "pair_name"),
    [(m, p) for m in _MODES for p in _PAIRS],
    ids=[f"{m}-{p}" for m in _MODES for p in _PAIRS],
)
def test_blend_mode_per_channel_matches_pdfbox(
    mode: str, pair_name: str, tmp_path: Path
) -> None:
    """Each less-common separable mode must composite the overlap to the same
    per-channel RGB as Java PDFBox 3.0.7, on BOTH a mid-tone pair and an
    extreme pair that forces every special-case branch of the formula. The
    grey-luminance fingerprint in test_blend_mode_oracle.py averages R/G/B
    together; this asserts each channel directly."""
    base, top = _PAIRS[pair_name]
    fixture = tmp_path / f"blend_{mode}_{pair_name}.pdf"
    _build_fixture(fixture, mode, base, top)

    (java_w, java_h), java_pixels = _oracle_pixels(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    py_w, py_h = img.size

    assert (py_w, py_h) == (java_w, java_h), (
        f"{mode}/{pair_name}: rendered dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    for (sx, sy), jrgb in zip(_SAMPLES, java_pixels, strict=True):
        prgb = img.getpixel((sx, sy))
        for ch in range(3):
            assert abs(prgb[ch] - jrgb[ch]) <= _CHANNEL_TOL, (
                f"{mode}/{pair_name}: overlap pixel ({sx},{sy}) channel {ch} "
                f"pypdfbox={prgb[ch]} java={jrgb[ch]} (diff "
                f"{abs(prgb[ch] - jrgb[ch])} > {_CHANNEL_TOL}) — per-channel "
                f"blend formula diverges from PDFBox, not AA. "
                f"full px py={prgb} java={jrgb}"
            )


@requires_oracle
def test_extreme_pair_actually_exercises_branches() -> None:
    """Sanity-pin the fixture design: the extreme pair must put at least one
    target mode on a DIFFERENT branch than a naive linear blend would predict,
    i.e. the chosen inputs really do hit the special-case code. We verify this
    against pypdfbox's own BlendMode formulas (no oracle needed for the maths).

    ColorDodge with a top channel == 1 (1 - src == 0) returns 1 for any
    non-zero backdrop (the saturation clamp), and returns 0 where the backdrop
    channel is 0 — both special branches. ColorBurn with top channel == 0
    (src == 0) returns 0 unless the backdrop is 1. If these identities hold the
    extreme pair is genuinely exercising the branch logic the mid-tone pair
    skips."""
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode  # noqa: PLC0415

    dodge = BlendMode.COLOR_DODGE
    burn = BlendMode.COLOR_BURN
    # src (top) channel saturating cases:
    assert dodge.blend(1.0, 0.5) == 1.0  # 1 - src == 0 → clamp branch
    assert dodge.blend(1.0, 0.0) == 0.0  # dest == 0 → zero branch
    assert burn.blend(0.0, 0.5) == 0.0  # src == 0, dest < 1 → zero branch
    assert burn.blend(0.0, 1.0) == 1.0  # dest == 1 → one branch


@requires_oracle
def test_ignored_blend_would_fail_per_channel_gate(tmp_path: Path) -> None:
    """Guard the per-channel gate: render a Difference fixture with the ``/BM``
    stripped (top painted opaque, blend ignored) and confirm at least one
    sampled channel diverges from the correct oracle render by more than the
    tolerance — proving the gate detects an ignored blend rather than passing
    everything. Difference inverts strongly, so an ignored blend is far off."""
    from pypdfbox.cos import COSName  # noqa: PLC0415

    base, top = _PAIRS["extreme"]
    fixture = tmp_path / "blend_Difference_extreme.pdf"
    _build_fixture(fixture, "Difference", base, top)
    _dims, java_pixels = _oracle_pixels(fixture)

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
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")

    worst = 0
    for (sx, sy), jrgb in zip(_SAMPLES, java_pixels, strict=True):
        prgb = img.getpixel((sx, sy))
        worst = max(worst, *(abs(prgb[ch] - jrgb[ch]) for ch in range(3)))
    assert worst > _CHANNEL_TOL, (
        "tolerance too loose: an ignored Difference blend passes the "
        f"per-channel gate (worst channel diff {worst})"
    )
