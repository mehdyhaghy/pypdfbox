"""Live PDFBox differential parity for the ExtGState ``/SMask`` luminosity
soft-mask ``/BC`` (backdrop colour) surface (PDF 32000-1 §11.6.5.2).

A luminosity ``/SMask`` may declare a ``/BC`` backdrop colour — the colour
the mask transparency-group composites *against*. A reader might plausibly
expect a white ``/BC`` to drive the mask luminance to 1 (fully OPAQUE) in
every area the mask group does not paint — opening the masked paint across
the whole page — and a black ``/BC`` to drive it to 0 (fully transparent).

That is NOT how Apache PDFBox 3.0.7 behaves. ``PageDrawer.TransparencyGroup``
fills the group buffer with ``/BC`` (``Graphics2D.clearRect``) but then
removes that backdrop contribution (``GroupGraphics.removeBackdrop``) before
the luminosity mask is taken from the buffer, so the resulting mask alpha is
the group result modulated by the group's own COVERAGE. An area the mask
group never paints contributes mask alpha 0 (the page backdrop shows through)
*regardless of the ``/BC`` luminance*. White-``/BC`` and black-``/BC``
renders of the same fixture are therefore IDENTICAL — ``/BC`` does not bleed
its luminance into uncovered regions.

pypdfbox mirrors this exactly: ``PDFRenderer._render_soft_mask_alpha`` seeds
the mask canvas with the ``/BC`` colour at alpha 0 and computes
``luminance * coverage``, so an uncovered pixel (coverage 0) yields mask
alpha 0 for any ``/BC``. Confirmed at parity against the live Java oracle
(MAD 0.00 / MAXDIFF 0 on every variant) — this test is a regression pin, no
production change was needed.

The discriminating guard below asserts the rule directly: the white-``/BC``
and black-``/BC`` renders are byte-for-byte equal on the fingerprint, and a
hypothetical "white ``/BC`` opens uncovered regions" render lands far outside
the gate against the correct oracle.

This complements ``test_soft_mask_bbox_oracle.py`` (wave 1455), which pinned
the OUTSIDE-the-bbox case for a group that fully covered its small bbox; here
the mask group's ``/BBox`` is the WHOLE page but the group only paints part
of it, so the untouched-but-INSIDE-bbox region is the surface under test —
the region where ``/BC`` would matter if it bled.

Pixel-EXACT parity is generally impossible (Pillow vs Java2D anti-aliasing —
see ``CHANGES.md`` / ``test_render_oracle.py``), so we compare the proven
coarse fingerprint: exact rendered dimensions plus a 16x16 average-luminance
grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/SoftMaskBackdropColorProbe.java`` (72 DPI; identical
luminance math to ``RenderProbe``).

Fixtures are synthesised in-memory via pypdfbox's own COS / form-XObject API;
the test commits no binaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the sibling soft-mask oracles — comfortably above the AA ceiling
# yet well below the gross-failure floor (these flat fixtures measure MAD 0.00).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== device px at 72 DPI)
_BACKDROP_RGB = (0.95, 0.9, 0.1)  # yellow page fill
_FILL_RGB = (0.1, 0.1, 0.1)  # near-black fill, gated by the mask


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``SoftMaskBackdropColorProbe.java`` (integer-division of pixel coord over
    image size, clamped to the last cell). Matches PIL's "L" Rec.601 weights."""
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
    """Run SoftMaskBackdropColorProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text(
        "SoftMaskBackdropColorProbe", str(fixture), "0"
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mask_group(coverage: str) -> PDFormXObject:
    """A full-page-``/BBox`` transparency-group form XObject whose content
    paints a WHITE region per ``coverage`` (so the rest of the bbox stays
    UNTOUCHED — that uncovered region is the ``/BC`` surface under test).

    * ``"corner"`` — a white 30x30 square in the lower-left corner only.
    * ``"strip"``  — a white 40-pt-wide vertical strip on the left.
    """
    stream = COSStream()
    if coverage == "corner":
        stream.set_raw_data(b"1 1 1 rg\n0 0 30 30 re\nf\n")
    else:  # "strip"
        stream.set_raw_data(b"1 1 1 rg\n0 0 40 100 re\nf\n")
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    form.set_group(group)
    return form


def _build_fixture(path: Path, coverage: str, bc: float | None) -> None:
    """Yellow page backdrop + full-page near-black fill gated by an ExtGState
    ``/SMask`` (``/Luminosity``) whose mask group ``/BBox`` is the WHOLE page
    but whose content covers only part of it (``coverage``). ``bc`` is the
    single-component ``/BC`` backdrop luminance (or ``None`` to omit ``/BC``,
    which defaults to black)."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    mask_form = _mask_group(coverage)

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
    if bc is not None:
        bc_arr = COSArray()
        bc_arr.add(COSFloat(bc))
        smask.set_item(COSName.get_pdf_name("BC"), bc_arr)

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


# (coverage, /BC) — each leaves an untouched-inside-bbox region whose value
# would shift with /BC if the backdrop bled.
_VARIANTS = {
    "corner_bc_white": ("corner", 1.0),
    "corner_bc_black": ("corner", 0.0),
    "corner_bc_grey": ("corner", 0.5),
    "corner_bc_absent": ("corner", None),
    "strip_bc_white": ("strip", 1.0),
    "strip_bc_black": ("strip", 0.0),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_VARIANTS), ids=list(_VARIANTS))
def test_backdrop_color_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each ``/BC`` variant must match Java PDFBox's render of the same fixture
    within the 16x16 fingerprint gate. The discriminating behaviour: the
    untouched-inside-bbox region stays at the page backdrop (mask alpha 0,
    coverage-modulated) independent of ``/BC`` — a renderer that bled ``/BC``
    luminance into the uncovered region lands far outside the gate."""
    coverage, bc = _VARIANTS[label]
    fixture = tmp_path / f"{label}.pdf"
    _build_fixture(fixture, coverage, bc)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
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
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — /BC backdrop-colour path mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("coverage", ["corner", "strip"], ids=["corner", "strip"])
def test_white_and_black_bc_render_identically(
    coverage: str, tmp_path: Path
) -> None:
    """Direct proof of the discriminating rule against the oracle: a white
    ``/BC`` and a black ``/BC`` produce the SAME PDFBox render — the backdrop
    colour does not bleed into the uncovered region. We assert PDFBox's own
    white-``/BC`` and black-``/BC`` fingerprints are equal, and that pypdfbox
    matches the (shared) oracle for both."""
    white_fx = tmp_path / f"{coverage}_white.pdf"
    black_fx = tmp_path / f"{coverage}_black.pdf"
    _build_fixture(white_fx, coverage, 1.0)
    _build_fixture(black_fx, coverage, 0.0)

    (_w_dims, white_grid) = _oracle_signature(white_fx)
    (_b_dims, black_grid) = _oracle_signature(black_fx)

    # PDFBox itself renders white-/BC and black-/BC identically.
    assert white_grid == black_grid, (
        f"{coverage}: oracle white-/BC vs black-/BC diverge — the /BC backdrop "
        f"is observable in PDFBox 3.0.7 for this fixture; the parity model in "
        f"_render_soft_mask_alpha (coverage-modulated, /BC-neutral) needs review"
    )

    with PDDocument.load(white_fx) as doc:
        py_white = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )
    with PDDocument.load(black_fx) as doc:
        py_black = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )
    assert py_white == py_black, (
        f"{coverage}: pypdfbox white-/BC vs black-/BC diverge — /BC wrongly "
        f"bled into the uncovered region"
    )
    for label, py_grid in (("white", py_white), ("black", py_black)):
        diffs = [abs(a - b) for a, b in zip(white_grid, py_grid, strict=True)]
        mad = sum(diffs) / len(diffs)
        assert mad < _MAD_TOLERANCE, (
            f"{coverage}/{label}: mad {mad:.2f} >= {_MAD_TOLERANCE} vs oracle"
        )


@requires_oracle
def test_white_bc_bleed_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: emulate the (wrong) "white ``/BC`` opens the uncovered
    region" behaviour — the dark fill painted opaquely everywhere the mask
    group did not paint — and confirm it lands outside tolerance against the
    correct oracle render, proving the gate detects a ``/BC`` bleed rather than
    passing both interpretations."""
    fixture = tmp_path / "corner_bc_white.pdf"
    _build_fixture(fixture, "corner", 1.0)
    _dims, java_grid = _oracle_signature(fixture)

    # Wrong behaviour: dark fill fully opaque over the whole page (white /BC
    # opening the masked paint everywhere the group left uncovered).
    emulated = Image.new(
        "RGB", (_MB, _MB), tuple(round(_FILL_RGB[i] * 255) for i in range(3))
    )
    py_grid = _grid_from_image(emulated)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a white-/BC-bleed render passes the MAD gate "
        f"(observed mad={mad:.2f})"
    )
