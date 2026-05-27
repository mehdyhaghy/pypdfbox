"""Live PDFBox differential parity for transparency *groups* (PDF 32000-1
§11.4.7 / §11.6.4.3 / §11.6.5.3) — the group-level mechanics layered on top
of the per-element blend / ``ca`` / luminosity-SMask coverage already pinned
by ``test_transparency_oracle.py`` (wave 1429).

Covered group features:

* **Group constant alpha (``/ca``)** — a transparency-group Form XObject
  (``/Group << /S /Transparency >>``) containing two overlapping opaque
  rectangles, painted via ``Do`` under an ExtGState ``/ca 0.5``. The group's
  constant alpha applies to the group *as a whole* (one composite at 50 %),
  NOT to each interior element — so the overlap is the group result over the
  page at 50 %, not a double-darkened per-element mix. Exercised for both the
  **isolated** (``/I true``) and **non-isolated** (``/I false``) backdrop
  rules; with fully-opaque interior paint PDFBox yields the same composite for
  both (the non-isolated backdrop is removed before the group composites).
* **Knockout group (``/K true``)** — a group with two overlapping elements
  where each top-level object composites against the group's initial backdrop
  rather than against prior siblings.
* **Luminosity ``/SMask`` with a non-default ``/BC`` grey backdrop** — a
  full-page dark fill gated by a luminosity mask whose group paints a white
  left strip over a ``/BC [0.5]`` grey backdrop. Verified against the oracle:
  the masked-out region (where the mask group paints nothing) stays at the
  page backdrop regardless of the ``/BC`` luminance — PDFBox modulates the
  luminosity by the mask group's coverage, so uncovered = alpha 0.

Same coarse fingerprint as the page-render oracle: exact rendered dimensions
plus a 16x16 average-luminance grid gated at ``MAD < 6`` / ``MAXDIFF < 60``
against ``oracle/probes/RenderProbe.java`` (72 DPI). Correct group renders land
at MAD < 1.2 on these flat fixtures; the guard tests below prove the gate
detects an ignored group wrapper (per-element ``ca`` scores MAD ~14) and an
ignored ``/BC``-coverage rule (mask-as-luminance scores MAD ~65).

Fixtures are synthesised in-memory via pypdfbox's own COS / form-XObject API;
the test commits no binaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_MB = 100  # media-box side, pt (== px at 72 DPI)


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java``."""
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


def _assert_parity(label: str, fixture: Path) -> None:
    """Render ``fixture`` via Java + pypdfbox at 72 DPI and assert exact dims
    plus 16x16 luminance-grid parity within the MAD/MAXDIFF gate."""
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
        f"(maxdiff={maxdiff}) — group mechanics ignored/wrong, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


def _mad_against_oracle(fixture: Path, img: Image.Image) -> float:
    """MAD of an arbitrary rendered image against the oracle fingerprint
    for ``fixture`` — used by the guard tests."""
    _dims, java_grid = _oracle_signature(fixture)
    py_grid = _grid_from_image(img)
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    return sum(diffs) / len(diffs)


# ---------------------------------------------------------------------------
# (a) Group constant alpha — /ca over an isolated vs non-isolated group
# ---------------------------------------------------------------------------

_GRP_BACKDROP_RGB = (0.1, 0.3, 0.9)  # opaque blue page backdrop
# Two overlapping opaque rects inside the group: red then green.
_GRP_FORM_BYTES = (
    b"0.9 0.1 0.1 rg\n10 10 60 60 re\nf\n"
    b"0.1 0.8 0.1 rg\n30 30 60 60 re\nf\n"
)


def _build_group_fixture(
    path: Path,
    *,
    isolated: bool,
    knockout: bool = False,
    ca: float = 0.5,
    wrap_in_group: bool = True,
) -> None:
    """Build a page with a blue backdrop and a Form XObject (optionally a
    transparency group) painted via ``Do`` under an ExtGState ``/ca``."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    form_stream = COSStream()
    form_stream.set_raw_data(_GRP_FORM_BYTES)
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    if wrap_in_group:
        group = COSDictionary()
        group.set_item(
            COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
        )
        group.set_item(COSName.get_pdf_name("I"), COSBoolean.get_boolean(isolated))
        group.set_item(COSName.get_pdf_name("K"), COSBoolean.get_boolean(knockout))
        form.set_group(group)

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("ca"), COSFloat(ca))

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), egs
    )
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Fm0"),
        form.get_cos_object(),
    )

    contents = COSStream()
    contents.set_raw_data(
        b"0.1 0.3 0.9 rg\n0 0 100 100 re\nf\n"
        b"q\n/GS0 gs\n/Fm0 Do\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(path))
    doc.close()


@requires_oracle
@pytest.mark.parametrize("isolated", [True, False], ids=["isolated", "non_isolated"])
def test_group_constant_alpha_matches_pdfbox(isolated: bool, tmp_path: Path) -> None:
    """An ``/I true``/``/I false`` transparency group at ``/ca 0.5`` composites
    as a single object at 50 % over the page backdrop — matching PDFBox for
    both the isolated (clear backdrop) and non-isolated (parent backdrop,
    removed before composite) rules."""
    label = "isolated" if isolated else "non_isolated"
    fixture = tmp_path / f"group_ca_{label}.pdf"
    _build_group_fixture(fixture, isolated=isolated, ca=0.5)
    _assert_parity(f"group_ca/{label}", fixture)


@requires_oracle
def test_group_alpha_applies_to_group_not_each_element(tmp_path: Path) -> None:
    """Direct-pixel companion: the group ``/ca 0.5`` must apply to the group
    composite (each opaque interior region appears at 50 % over the backdrop),
    not per-element. The red-only region therefore reads the 50/50 mix of red
    and the blue backdrop — not a double-blended value."""
    fixture = tmp_path / "group_ca_isolated.pdf"
    _build_group_fixture(fixture, isolated=True, ca=0.5)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # PIL (20, 80) == PDF (20, 20): inside the red rect (10..70) only.
    red_only = img.getpixel((20, 80))
    backdrop = tuple(round(_GRP_BACKDROP_RGB[i] * 255) for i in range(3))
    red = (230, 26, 26)  # 0.9/0.1/0.1 rg
    expected = tuple(round(red[i] * 0.5 + backdrop[i] * 0.5) for i in range(3))
    assert all(abs(red_only[i] - expected[i]) <= 4 for i in range(3)), (
        f"red-only group region {red_only} != group-alpha mix {expected} — "
        f"group /ca applied per-element instead of to the group"
    )


@requires_oracle
def test_opaque_group_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the same group geometry at ``/ca 1.0`` (the
    group painted fully opaque) must land outside tolerance versus the
    ``/ca 0.5`` oracle — proving the gate detects an ignored / dropped group
    alpha rather than passing everything."""
    half = tmp_path / "group_ca_isolated.pdf"
    _build_group_fixture(half, isolated=True, ca=0.5)
    _dims, java_grid = _oracle_signature(half)

    opaque = tmp_path / "group_ca_one.pdf"
    _build_group_fixture(opaque, isolated=True, ca=1.0)
    with PDDocument.load(opaque) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an opaque (ca 1.0) group passes the ca 0.5 gate"
    )


@requires_oracle
def test_group_alpha_is_not_applied_per_element(tmp_path: Path) -> None:
    """Companion proof that group ``/ca`` is applied to the group as a whole,
    not to each interior element. Re-paint the group's interior geometry
    *outside* any group, each fill carrying ``ca 0.5`` directly; the resulting
    overlap pixel differs materially from the group composite (where the
    overlap is the opaque interior green at 50 % over the backdrop).

    This nails the semantic the fingerprint gate is coarse about: with the
    group wrapper the overlap reads green-over-backdrop at 50 %; per-element it
    reads green-over-(red-over-backdrop) — a visibly different colour."""
    grouped = tmp_path / "group_ca_isolated.pdf"
    _build_group_fixture(grouped, isolated=True, ca=0.5)
    per_element = tmp_path / "no_group_ca.pdf"
    _build_group_fixture(per_element, isolated=True, ca=0.5, wrap_in_group=False)

    with PDDocument.load(grouped) as doc:
        g_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    with PDDocument.load(per_element) as doc:
        p_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")

    # PIL (50, 50) == PDF centre overlap of the red (10..70) and green (30..90)
    # rects. Group: green at 50 % over the page. Per-element: green at 50 %
    # over (red at 50 % over the page) — a different mix.
    g_overlap = g_img.getpixel((50, 50))
    p_overlap = p_img.getpixel((50, 50))
    spread = sum(abs(g_overlap[i] - p_overlap[i]) for i in range(3))
    assert spread >= 12, (
        f"group overlap {g_overlap} ~= per-element overlap {p_overlap}; the "
        f"group alpha must compose the group as a unit, not per element"
    )


# ---------------------------------------------------------------------------
# (b) Knockout group — /K true
# ---------------------------------------------------------------------------


@requires_oracle
def test_knockout_group_matches_pdfbox(tmp_path: Path) -> None:
    """A ``/K true`` group with two overlapping elements at ``/ca 0.5``.

    The lite renderer approximates knockout via a snapshot-restore at each
    top-level paint (documented in DEFERRED.md, closed wave 1379); it lands
    within the MAD gate on this overlapping-rect case."""
    fixture = tmp_path / "group_knockout.pdf"
    _build_group_fixture(fixture, isolated=True, knockout=True, ca=0.5)
    _assert_parity("group/knockout", fixture)


# ---------------------------------------------------------------------------
# (c) Luminosity /SMask with a non-default /BC grey backdrop
# ---------------------------------------------------------------------------

_SMASK_BACKDROP_RGB = (0.95, 0.9, 0.1)  # yellow page fill
_SMASK_FILL_RGB = (0.1, 0.1, 0.1)  # near-black fill, gated by the mask


def _build_bc_smask_fixture(path: Path, bc: float) -> None:
    """Yellow page backdrop + full-page near-black fill through a luminosity
    ``/SMask`` whose mask group paints a white left strip over a ``/BC [bc]``
    grey backdrop. The masked-out region (mask group paints nothing) stays at
    the yellow backdrop regardless of ``bc`` — PDFBox modulates luminosity by
    the mask group's coverage."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    mask_stream = COSStream()
    mask_stream.set_raw_data(b"1 1 1 rg\n0 0 30 100 re\nf\n")  # white left strip
    mask_form = PDFormXObject(mask_stream)
    mask_form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    group = COSDictionary()
    group.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
    )
    mask_form.set_group(group)

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
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


@requires_oracle
def test_luminosity_smask_grey_backdrop_matches_pdfbox(tmp_path: Path) -> None:
    """A luminosity ``/SMask`` with a ``/BC [0.5]`` grey backdrop: only the
    white-strip region (mask coverage + luminance 1) shows the dark fill; the
    masked-out region stays yellow (uncovered → alpha 0 regardless of the
    grey ``/BC`` luminance)."""
    fixture = tmp_path / "smask_bc_grey.pdf"
    _build_bc_smask_fixture(fixture, 0.5)
    _assert_parity("smask/bc_grey", fixture)


@requires_oracle
def test_luminosity_smask_bc_does_not_open_uncovered_region(tmp_path: Path) -> None:
    """Direct-pixel companion: the masked-out region (mask group paints
    nothing) keeps the yellow backdrop even though ``/BC`` is mid-grey — the
    mask alpha is luminance modulated by coverage, so uncovered = 0."""
    fixture = tmp_path / "smask_bc_grey.pdf"
    _build_bc_smask_fixture(fixture, 0.5)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    left = img.getpixel((15, 50))  # mask white strip → fill visible
    right = img.getpixel((70, 50))  # mask uncovered → backdrop visible

    fill = tuple(round(_SMASK_FILL_RGB[i] * 255) for i in range(3))
    backdrop = tuple(round(_SMASK_BACKDROP_RGB[i] * 255) for i in range(3))
    assert all(abs(left[i] - fill[i]) <= 6 for i in range(3)), (
        f"masked-in strip {left} != gated fill {fill}"
    )
    assert all(abs(right[i] - backdrop[i]) <= 6 for i in range(3)), (
        f"masked-out region {right} != backdrop {backdrop} — /BC luminance "
        f"wrongly opened the uncovered region"
    )


@requires_oracle
def test_bc_luminance_as_floor_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: treating ``/BC [0.5]`` as a 50 % alpha floor across the
    uncovered region (the pre-fix behaviour — luminance of the whole seeded
    backdrop) must land outside tolerance versus the coverage-modulated
    oracle, proving the gate detects an ignored coverage rule."""
    fixture = tmp_path / "smask_bc_grey.pdf"
    _build_bc_smask_fixture(fixture, 0.5)
    _dims, java_grid = _oracle_signature(fixture)

    # Emulate the pre-fix behaviour: render the dark fill at a flat 50 % over
    # the whole page (what a luminance-of-/BC-everywhere mask would produce).
    backdrop = Image.new(
        "RGB",
        (_MB, _MB),
        tuple(round(_SMASK_BACKDROP_RGB[i] * 255) for i in range(3)),
    )
    fill = Image.new(
        "RGBA",
        (_MB, _MB),
        (*(round(_SMASK_FILL_RGB[i] * 255) for i in range(3)), 128),
    )
    emulated = backdrop.convert("RGBA")
    emulated.alpha_composite(fill)
    py_grid = _grid_from_image(emulated.convert("RGB"))

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a /BC-luminance-floor mask passes the gate"
    )
