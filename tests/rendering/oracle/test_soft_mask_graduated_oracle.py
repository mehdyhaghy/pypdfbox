"""Live PDFBox differential parity for a *continuous-tone* (multi-level)
ExtGState ``/SMask`` luminosity soft mask (PDF 32000-1 §11.6.5.2-3).

The existing soft-mask oracles all exercise BINARY mask coverage — the mask
group either fully paints a region (luminance → alpha 1) or leaves it
untouched (coverage 0 → alpha 0):

* ``test_transparency_oracle.py`` — white left strip (alpha 1) over a black
  ``/BC`` backdrop (alpha 0).
* ``test_alpha_smask_oracle.py`` — a single mid-grey (0.5) covered region vs an
  untouched region (the luminosity *control* for the alpha-vs-coverage proof).
* ``test_soft_mask_backdrop_color_oracle.py`` / ``test_soft_mask_bbox_oracle.py``
  — covered-white vs untouched regions, pinning the ``/BC`` / outside-bbox
  rules.

NONE of them pin the renderer's continuous-tone behaviour: a *fully-covered*
mask group whose luminance varies across several distinct INTERMEDIATE levels,
each of which must map to a distinct PARTIAL mask alpha. This is exactly where
``PDFRenderer._render_soft_mask_alpha``'s ``luminance * coverage`` formula
(§11.6.5.3) could diverge from PDFBox — a wrong luminance weighting (Rec.601
vs flat average), a gamma, or a binarising threshold would all pass the binary
tests above while landing the partial-alpha bands at the wrong strength.

The fixture is a yellow full-page backdrop with a full-page near-black fill
painted through a luminosity ``/SMask`` whose mask group fully covers the page
with FOUR equal vertical bands of luminance 1.0 / 0.75 / 0.5 / 0.25. Each band
is full-coverage, so the mask alpha is the band luminance directly — the
near-black fill therefore shows over the yellow backdrop at four monotonically
decreasing strengths (band 0 ≈ black, band 3 ≈ mostly-yellow). Confirmed at
parity against the live Java oracle (MAD 0.00 / MAXDIFF 0) — this test is a
regression pin, no production change was needed.

The direct-pixel guard below asserts the four bands are monotonically lighter
(distinct partial alphas), which a binarising or wrong-weight mask would break.

Pixel-EXACT parity is generally impossible (Pillow vs Java2D anti-aliasing —
see ``CHANGES.md`` / ``test_render_oracle.py``), so we compare the proven
coarse fingerprint: exact rendered dimensions plus a 16x16 average-luminance
grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI).

Fixtures are synthesised in-memory via pypdfbox's own COS / form-XObject API;
the test commits no binaries.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the sibling soft-mask oracles — comfortably above the AA ceiling
# (this flat-band fixture measures MAD 0.00) yet well below the gross-failure
# floor (a binarised or wrong-weight mask shifts the partial-alpha bands well
# past the gate).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== device px at 72 DPI)
_BACKDROP_RGB = (0.95, 0.9, 0.1)  # yellow page fill
_FILL_RGB = (0.1, 0.1, 0.1)  # near-black fill, gated by the mask
# Four full-coverage mask-group bands of decreasing luminance → decreasing
# partial mask alpha → the dark fill shows at decreasing strength over yellow.
_BANDS = (1.0, 0.75, 0.5, 0.25)
_BAND_W = _MB // len(_BANDS)  # 25 pt each
_BAND_CENTRES = tuple(i * _BAND_W + _BAND_W // 2 for i in range(len(_BANDS)))


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


def _build_graduated_smask_fixture(path: Path) -> None:
    """Yellow page backdrop + full-page near-black fill gated by a luminosity
    ``/SMask`` whose mask group fully covers the page with four equal vertical
    bands of luminance 1.0 / 0.75 / 0.5 / 0.25. Each band is full-coverage, so
    the mask alpha equals the band luminance and the dark fill shows over the
    yellow backdrop at four decreasing strengths."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    band_ops = b"".join(
        f"{lum} {lum} {lum} rg\n{i * _BAND_W} 0 {_BAND_W} {_MB} re\nf\n".encode(
            "ascii"
        )
        for i, lum in enumerate(_BANDS)
    )
    mask_stream = COSStream()
    mask_stream.set_raw_data(band_ops)
    mask_form = PDFormXObject(mask_stream)
    mask_form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB"))
    mask_form.set_group(group)

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("SMask"), smask)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), egs
    )

    contents = COSStream()
    contents.set_raw_data(
        b"0.95 0.9 0.1 rg\n0 0 100 100 re\nf\n"
        b"q\n/GS0 gs\n0.1 0.1 0.1 rg\n0 0 100 100 re\nf\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(path))
    doc.close()


@requires_oracle
def test_graduated_luminosity_smask_matches_pdfbox(tmp_path: Path) -> None:
    """A full-coverage, multi-level luminosity mask must match Java PDFBox's
    render within the 16x16 fingerprint gate. The discriminating behaviour:
    each band's INTERMEDIATE luminance maps to a distinct PARTIAL mask alpha
    (``luminance * coverage``) — a binarising or wrong-weight mask shifts the
    bands well outside the gate against the oracle."""
    fixture = tmp_path / "smask_graduated.pdf"
    _build_graduated_smask_fixture(fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} (maxdiff={maxdiff}) — "
        f"continuous-tone luminosity mask mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} (mad={mad:.2f}) — "
        f"a band diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_bands_are_distinct_partial_alphas(tmp_path: Path) -> None:
    """Direct-pixel proof that the four intermediate luminance bands produce
    four DISTINCT partial mask alphas, not a binary on/off mask.

    The near-black fill over a yellow backdrop gated by mask alpha ``a`` lands
    at ``fill * a + backdrop * (1 - a)``. As the band luminance (== alpha)
    decreases 1.0 → 0.25, the rendered band must get monotonically LIGHTER
    (closer to the yellow backdrop), with a material gap between adjacent
    bands — which only holds if each intermediate luminance maps to its own
    partial alpha (a binarising mask would collapse bands to ≤2 levels)."""
    fixture = tmp_path / "smask_graduated.pdf"
    _build_graduated_smask_fixture(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
    lums = [img.getpixel((cx, _MB // 2)) for cx in _BAND_CENTRES]

    # Band 0 (alpha 1.0) ≈ the near-black fill; band 3 (alpha 0.25) is mostly
    # the yellow backdrop — and strictly increasing in between.
    for i in range(len(lums) - 1):
        assert lums[i + 1] - lums[i] >= 20, (
            f"band {i} luma {lums[i]} → band {i + 1} luma {lums[i + 1]} are not "
            f"distinct partial alphas (gap < 20) — mask appears binarised, not "
            f"continuous-tone"
        )


@requires_oracle
def test_binarised_mask_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: emulate a *binarised* mask (every covered band forced to
    full alpha 1 — the dark fill painted opaquely everywhere) and confirm it
    lands outside tolerance against the correct continuous-tone oracle render,
    proving the gate detects a thresholded mask rather than passing both
    interpretations."""
    fixture = tmp_path / "smask_graduated.pdf"
    _build_graduated_smask_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    # Wrong behaviour: a mask binarised to alpha 1 over the whole page → the
    # near-black fill opaque everywhere (bands 1-3 lose their partial alpha).
    emulated = Image.new(
        "RGB", (_MB, _MB), tuple(round(_FILL_RGB[i] * 255) for i in range(3))
    )
    py_grid = _grid_from_image(emulated)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a binarised (all-alpha-1) mask passes the MAD gate "
        f"(observed mad={mad:.2f})"
    )
