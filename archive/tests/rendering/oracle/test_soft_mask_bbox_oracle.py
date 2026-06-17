"""Live PDFBox differential parity for ExtGState ``/SMask`` soft masks whose
mask transparency-group ``/BBox`` is SMALLER THAN (or offset from) the region
the masked paint covers (PDF 32000-1 §11.6.5.2 / §11.6.5.3).

Existing soft-mask oracles all use a mask group whose ``/BBox`` covers the
whole painted region:

* ``test_transparency_group_oracle.py`` — luminosity ``/SMask`` with a
  non-default ``/BC`` grey backdrop, mask group ``/BBox [0 0 100 100]``
  (full page). It pins that an *uncovered* region inside the BBox stays at
  alpha 0 regardless of ``/BC``.
* ``test_smask_transfer_oracle.py`` / ``test_alpha_smask_oracle.py`` — also
  full-coverage mask groups.

The orthogonal case NONE of those pin is what happens to the soft-mask value
**outside the mask group's /BBox**. A reader might plausibly think a
luminosity ``/BC`` backdrop "bleeds" the backdrop luminance across the whole
device area (so ``/BC [1]`` white would open the masked paint everywhere the
group does not reach). It does NOT: PDFBox renders the mask group into a
buffer sized to the group bbox and the soft-mask alpha is the rendered
luminance *modulated by the group's coverage* — outside the bbox the group
has zero coverage, so the mask alpha is 0 and the page backdrop shows through,
independent of ``/BC``. This holds for both:

* a bbox anchored at the origin but narrower than the page
  (``/BBox [0 0 40 100]``), and
* a bbox both offset and narrower (``/BBox [10 10 40 60]``),

and for both the ``/Luminosity`` and ``/Alpha`` mask subtypes (for ``/Alpha``
the ``/BC`` is irrelevant; the result is the same coverage-gated alpha).

Confirmed at parity against the live Java oracle (MAD 0.00 / MAXDIFF 0 on
every variant) — this test is a regression pin, no production change was
needed. The companion direct-pixel guard below asserts the discriminating
behaviour explicitly: a ``/BC [1]`` (white) backdrop must NOT open the masked
fill outside the mask group's small bbox.

Pixel-EXACT parity is generally impossible (Pillow vs Java2D anti-aliasing —
see ``CHANGES.md`` / ``test_render_oracle.py``), so we compare the proven
coarse fingerprint: exact rendered dimensions plus a 16x16 average-luminance
grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/SoftMaskBBoxProbe.java`` (72 DPI; identical luminance math to
``RenderProbe`` — dedicated named probe per the wave brief).

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
    ``SoftMaskBBoxProbe.java`` (integer-division of pixel coord over image
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


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run SoftMaskBBoxProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("SoftMaskBBoxProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _smask_group(
    bbox: tuple[float, float, float, float], paint_rgb: tuple[float, float, float]
) -> PDFormXObject:
    """A transparency-group form XObject whose content paints a solid strip
    in ``paint_rgb`` over the left 40 pt of the page, with its ``/BBox`` set
    to ``bbox`` (which clips that strip to the bbox region)."""
    stream = COSStream()
    r, g, b = paint_rgb
    stream.set_raw_data(f"{r} {g} {b} rg\n0 0 40 100 re\nf\n".encode("ascii"))
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(*bbox))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    form.set_group(group)
    return form


def _build_fixture(
    path: Path,
    subtype: str,
    bbox: tuple[float, float, float, float],
    bc: float | None,
) -> None:
    """Yellow page backdrop + full-page near-black fill gated by an ExtGState
    ``/SMask`` whose mask group ``/BBox`` is ``bbox`` (smaller than the page).
    For ``/Luminosity`` the mask group paints a white strip over a ``/BC``
    backdrop; for ``/Alpha`` it paints a grey strip (colour irrelevant)."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    if subtype == "Luminosity":
        mask_form = _smask_group(bbox, (1.0, 1.0, 1.0))  # white strip
    else:
        mask_form = _smask_group(bbox, (0.5, 0.5, 0.5))  # grey strip

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name(subtype))
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


# (subtype, bbox, /BC) — each a distinct outside-bbox configuration.
_VARIANTS = {
    "lum_white_bc_narrow_bbox": ("Luminosity", (0, 0, 40, _MB), 1.0),
    "lum_black_bc_narrow_bbox": ("Luminosity", (0, 0, 40, _MB), 0.0),
    "lum_grey_bc_offset_bbox": ("Luminosity", (10, 10, 40, 60), 0.5),
    "lum_white_bc_offset_bbox": ("Luminosity", (10, 10, 40, 60), 1.0),
    "alpha_narrow_bbox": ("Alpha", (0, 0, 40, _MB), None),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_VARIANTS), ids=list(_VARIANTS))
def test_soft_mask_small_bbox_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each soft-mask-with-small-bbox variant must match Java PDFBox's render
    of the same fixture within the 16x16 fingerprint gate. The discriminating
    behaviour: outside the mask group's bbox the mask alpha is 0 (coverage),
    independent of ``/BC`` — a renderer that bleeds ``/BC`` luminance across
    the whole device area (opening the masked fill outside the bbox) lands far
    outside the gate against the oracle."""
    subtype, bbox, bc = _VARIANTS[label]
    fixture = tmp_path / f"{label}.pdf"
    _build_fixture(fixture, subtype, bbox, bc)

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
        f"(maxdiff={maxdiff}) — soft-mask bbox path mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_white_bc_does_not_open_paint_outside_bbox(tmp_path: Path) -> None:
    """Direct-pixel proof of the discriminating rule: with ``/BC [1]`` (white)
    and a narrow mask-group ``/BBox [0 0 40 100]``, the masked dark fill is
    visible *inside* the bbox (where the white strip is painted) but the region
    *outside* the bbox keeps the yellow page backdrop — the white ``/BC`` does
    NOT bleed across the whole device area. A renderer that filled outside-bbox
    with the ``/BC`` luminance would open the dark fill there too."""
    fixture = tmp_path / "lum_white_bc_narrow_bbox.pdf"
    _build_fixture(fixture, "Luminosity", (0, 0, 40, _MB), 1.0)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    inside = img.getpixel((10, 50))  # inside bbox, mask white → fill visible
    outside = img.getpixel((70, 50))  # outside bbox → backdrop, not the fill

    fill = tuple(round(_FILL_RGB[i] * 255) for i in range(3))
    backdrop = tuple(round(_BACKDROP_RGB[i] * 255) for i in range(3))
    assert all(abs(inside[i] - fill[i]) <= 6 for i in range(3)), (
        f"inside-bbox region {inside} != gated fill {fill}"
    )
    assert all(abs(outside[i] - backdrop[i]) <= 6 for i in range(3)), (
        f"outside-bbox region {outside} != backdrop {backdrop} — white /BC "
        f"wrongly bled across the device area outside the mask group bbox"
    )


@requires_oracle
def test_white_bc_bleed_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: emulate the (wrong) "white ``/BC`` bleeds everywhere"
    behaviour — the dark fill painted opaquely across the whole page — and
    confirm it lands outside tolerance against the correct oracle render,
    proving the gate detects an outside-bbox ``/BC`` bleed rather than passing
    both interpretations."""
    fixture = tmp_path / "lum_white_bc_narrow_bbox.pdf"
    _build_fixture(fixture, "Luminosity", (0, 0, 40, _MB), 1.0)
    _dims, java_grid = _oracle_signature(fixture)

    # Wrong behaviour: dark fill fully opaque over the whole page (white /BC
    # opening the masked paint everywhere outside the small bbox too).
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
