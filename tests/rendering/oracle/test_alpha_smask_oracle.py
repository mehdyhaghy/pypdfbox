"""Live PDFBox differential parity for the *alpha-type* ExtGState soft mask.

An ExtGState ``/SMask << /S /Alpha /G <group> >>`` derives the soft-mask alpha
from the transparency GROUP's *accumulated alpha channel* (coverage/opacity),
NOT its luminosity (PDF 32000-1 §11.6.5.2). So a group that paints a shape at
``/ca 1`` over part of the area yields a mask that is fully opaque where the
shape was painted and fully transparent elsewhere — the group's colour and the
backdrop are irrelevant for the alpha case. This contrasts with ``/S
/Luminosity`` (covered by ``test_transparency_oracle.py``) which reads the
group's colour luminance.

Each fixture is a tiny one-page PDF synthesised in-memory via pypdfbox's COS +
content-stream API: a yellow full-page backdrop, then a full-page near-black
fill painted under ``gs`` with the soft mask active. The mask group paints a
**mid-grey** (``0.5 0.5 0.5``) rect over the left half at ``ca 1``:

* **alpha case** — mask = the shape's coverage: left half alpha 1.0 (fill fully
  shows → black), right half alpha 0 (yellow backdrop shows). The group's grey
  colour is irrelevant.
* **luminosity case** (control, same group) — mask = the group's luminance:
  left half ~0.5 (fill at 50% over yellow → mid olive), right half 0 (backdrop).

Because the group is mid-grey, the alpha render (left half fully black) DIFFERS
from the luminosity render (left half half-strength) — the guard test below
asserts this difference, proving ``/S /Alpha`` uses coverage, not luminance.

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a 16x16
average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). A render that
treats ``/S /Alpha`` as luminosity scores the luminosity grid (left half ~mid
olive instead of black) and lands far outside the gate against the Java oracle's
true alpha render — the guard test measures that divergence directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
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
# Same gate as test_transparency_oracle.py — comfortably above the AA ceiling
# (correct flat-fill renders measure MAD<=0.0 here) yet well below the
# gross-failure floor (treating /S /Alpha as luminosity = the half-strength
# left half, MAD well past the gate against the oracle's true alpha render).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)

_BACKDROP_RGB = (1.0, 1.0, 0.0)  # yellow page fill (luma ~226)
_FILL_RGB = (0.0, 0.0, 0.0)  # near-black fill, gated by the mask
_MASK_GREY = 0.5  # mid-grey mask-group colour (luminosity ~0.5)


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


def _build_smask_fixture(path: Path, subtype: str) -> None:
    """Yellow full-page backdrop, then a full-page near-black fill painted
    through an ExtGState ``/SMask`` whose mask group paints a mid-grey rect
    over the left half (x in 0..50) at ``ca 1``.

    ``subtype`` selects ``/S /Alpha`` or ``/S /Luminosity``."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    # Mask group: paint a single mid-grey rect over the left half at full
    # opacity. For /Alpha the mask = coverage (left half alpha 1, right half
    # alpha 0); for /Luminosity the mask = the grey luminance (~0.5) where
    # painted, 0 elsewhere.
    mask_stream = COSStream()
    mask_stream.set_raw_data(
        f"{_MASK_GREY} {_MASK_GREY} {_MASK_GREY} rg\n"
        f"0 0 {_MB // 2} {_MB} re\nf\n".encode("ascii")
    )
    mask_form = PDFormXObject(mask_stream)
    mask_form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB"))
    mask_form.set_group(group)

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name(subtype))
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
        b"1 1 0 rg\n0 0 100 100 re\nf\n"
        b"q\n/GS0 gs\n0 0 0 rg\n0 0 100 100 re\nf\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(path))
    doc.close()


@requires_oracle
@pytest.mark.parametrize("subtype", ["Alpha", "Luminosity"], ids=["alpha", "luminosity"])
def test_smask_subtype_render_matches_pdfbox(subtype: str, tmp_path: Path) -> None:
    """Both the alpha-type and (control) luminosity-type soft masks must match
    Java PDFBox's render of the same fixture within the fingerprint gate."""
    fixture = tmp_path / f"smask_{subtype.lower()}.pdf"
    _build_smask_fixture(fixture, subtype)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{subtype}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance. Treating /S /Alpha as
    # luminosity (or vice versa) lands far outside this gate.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{subtype}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — soft mask wrong subtype/formula, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{subtype}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_alpha_smask_uses_coverage_not_luminance(tmp_path: Path) -> None:
    """Direct-pixel proof that ``/S /Alpha`` derives the mask from the group's
    *coverage*, not its colour luminance.

    The mask group paints a mid-grey rect over the left half at ``ca 1``:

    * alpha case → that region's coverage is 1.0, so the near-black fill shows
      at full strength (~black).
    * luminosity case (same group) → that region's luminance is ~0.5, so the
      fill shows at half strength over the yellow backdrop (mid olive).

    The painted-region pixel must therefore DIFFER materially between the two,
    which is only possible if the alpha case reads coverage rather than the
    group's grey luminance."""
    alpha_pdf = tmp_path / "smask_alpha.pdf"
    lum_pdf = tmp_path / "smask_luminosity.pdf"
    _build_smask_fixture(alpha_pdf, "Alpha")
    _build_smask_fixture(lum_pdf, "Luminosity")

    with PDDocument.load(alpha_pdf) as doc:
        alpha_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    with PDDocument.load(lum_pdf) as doc:
        lum_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")

    # Centre of the painted (left) half — the masked-in region.
    alpha_left = alpha_img.getpixel((_MB // 4, _MB // 2))
    lum_left = lum_img.getpixel((_MB // 4, _MB // 2))

    # Alpha → coverage 1.0 → near-black fill fully visible.
    assert max(alpha_left) <= 10, (
        f"alpha-type painted region {alpha_left} is not the fully-gated fill — "
        "/S /Alpha appears to read luminance instead of coverage"
    )
    # Luminosity → grey luminance ~0.5 → fill at half strength over yellow,
    # so the region stays well above black.
    assert min(lum_left[:2]) >= 90, (
        f"luminosity-type painted region {lum_left} is unexpectedly dark — "
        "control case did not read the mid-grey group luminance"
    )
    # The two must differ materially in the painted region — the load-bearing
    # discriminator between coverage-driven and luminance-driven masks.
    channel_gap = max(
        abs(alpha_left[i] - lum_left[i]) for i in range(3)
    )
    assert channel_gap >= 60, (
        f"alpha {alpha_left} vs luminosity {lum_left} differ by only "
        f"{channel_gap} — /S /Alpha is not distinguished from /S /Luminosity"
    )


@requires_oracle
def test_alpha_smask_treated_as_luminosity_would_fail_tolerance(
    tmp_path: Path,
) -> None:
    """Guard the gate: rendering the *alpha* fixture but rewriting the mask
    subtype to ``/Luminosity`` (the exact bug this surface guards against)
    must land outside tolerance against the Java oracle's true ``/S /Alpha``
    render, proving the gate detects a coverage-vs-luminance mix-up."""
    fixture = tmp_path / "smask_alpha.pdf"
    _build_smask_fixture(fixture, "Alpha")
    _dims, java_grid = _oracle_signature(fixture)

    smask_key = COSName.get_pdf_name("SMask")
    s_key = COSName.get_pdf_name("S")
    resources_key = COSName.get_pdf_name("Resources")
    ext_g_state_key = COSName.get_pdf_name("ExtGState")
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        egs = (
            page.get_cos_object()
            .get_dictionary_object(resources_key)
            .get_dictionary_object(ext_g_state_key)
        )
        for key in list(egs.key_set()):
            gs = egs.get_dictionary_object(key)
            smask = gs.get_dictionary_object(smask_key)
            if smask is not None:
                smask.set_item(s_key, COSName.get_pdf_name("Luminosity"))
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: treating an /S /Alpha mask as /Luminosity "
        "passes the MAD gate against the oracle's true alpha render"
    )
