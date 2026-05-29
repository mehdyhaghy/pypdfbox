"""Live PDFBox differential parity for the form-XObject transparency-group
COMPOSITING surface across the full isolation/knockout matrix (PDF 32000-1
§11.4.7-8).

This is distinct from ``test_transparency_group_oracle.py`` (wave 1429),
which pinned group constant ``/ca``, the luminosity-``/SMask`` ``/BC``
coverage rule, and a single knockout case — and which, for the isolated vs
non-isolated comparison, uses *opaque* interior fills (PDFBox renders those
identically for both isolation modes, see that file's header). It is also
distinct from wave 1448 (page-level ``/Group`` dict round-trip) and wave 1455
(ExtGState soft-mask bbox).

Here the four variants form the 2x2 matrix over the two §11.4.7 group
attributes, each with overlapping *semi-transparent* (``/ca``) fills so the
isolation flag genuinely changes the render:

* **non-isolated, non-knockout** — the group's backdrop is the parent page,
  so the coloured backdrop bleeds through the translucent fills while the
  group renders; backdrop removal recovers the group's own contribution
  before the final composite.
* **isolated, non-knockout** — the group renders onto a fully transparent
  backdrop (§11.4.7.2); the backdrop does not bleed into the group interior.
  A renderer that seeds the group canvas with the parent (the non-isolated
  rule) scores far outside the gate here.
* **non-isolated, knockout** — each top-level element composites with the
  group's *initial* backdrop rather than the accumulated result (§11.4.7.3),
  so the second translucent fill replaces (not blends over) the first in the
  overlap band.
* **isolated, knockout** — both rules combined.

Each fixture draws an orange backdrop on the page, then a transparency-group
form XObject whose content is two overlapping ``/ca 0.55`` fills, invoked with
``Do``.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA — see ``CHANGES.md`` /
``test_render_oracle.py``), so we compare the proven coarse fingerprint:
exact rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/TransparencyGroupCompositeProbe.java`` (72 DPI render,
identical luminance math to ``RenderProbe`` / ``ImageMaskProbe``).

For a flat coloured backdrop with the group painting (semi-transparent)
solid fills over it, PDFBox composites the isolated and non-isolated cases to
the *same* result — backdrop removal recovers the non-isolated group's own
contribution, so the two modes converge (the wave-1429 oracle documents the
same observation for opaque interior paint). The genuine visible difference
between the two isolation modes needs a blend mode or a partially-covering
interior; this surface instead pins the compositing colour exactly against
the oracle and guards the gate with a direct-pixel regression for the
premultiplied-RGB bug fixed in this wave (see below).

Fixtures are tiny one-page PDFs synthesised in-memory via the COS + pdmodel
API (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_image_mask_oracle.py / test_transparency_group_oracle.py —
# comfortably above the AA ceiling yet well below the gross-failure floor
# (seeding the wrong group backdrop, dropping the knockout reset, or applying
# the group constant alpha per-element all diverge far past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 200  # media-box side, pt (== px at 72 DPI)


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``TransparencyGroupCompositeProbe.java`` (integer-division of pixel
    coord over image size, clamped to the last cell). Matches PIL's "L"
    Rec.601 weights."""
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
    """Run TransparencyGroupCompositeProbe on page 0 and parse its
    (dims, 16x16 grid). The probe emits the grid comma-separated."""
    lines = run_probe_text(
        "TransparencyGroupCompositeProbe", str(fixture), "0"
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _build_group_fixture(path: Path, *, isolated: bool, knockout: bool) -> None:
    """One-page PDF: an orange backdrop filling the page, then a
    transparency-group form XObject invoked with ``Do``.

    The form's content is two overlapping fills at ``/ca 0.55`` — a cyan
    rectangle on the left and a magenta rectangle on the right that share a
    central overlap band. The ``/Group`` dict is configured per the
    ``isolated`` / ``knockout`` flags.

    What each flag perturbs:

    * isolation governs whether the orange backdrop shows through the
      semi-transparent fills (non-isolated: the page is the group's backdrop
      so it mixes in; isolated: the group renders over a transparent backdrop
      and composites onto the page once as a whole);
    * knockout governs whether the magenta fill blends over the cyan in the
      overlap band (non-knockout) or replaces it (knockout).
    """
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    # ExtGState carrying the constant non-stroking alpha for the fills.
    gs = COSDictionary()
    gs.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState"))
    gs.set_item(COSName.get_pdf_name("ca"), COSFloat(0.55))

    form_resources = PDResources()
    form_resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), gs
    )

    # Cyan left rect (x 20..120) over magenta right rect (x 80..180), both
    # 60 pt tall centred vertically; overlap band x in [80,120]. /ca applies
    # to each top-level fill.
    form_content = (
        b"/GS0 gs\n"
        b"0 1 1 rg\n"  # cyan
        b"20 70 100 60 re\nf\n"
        b"1 0 1 rg\n"  # magenta
        b"80 70 100 60 re\nf\n"
    )
    form_stream = COSStream()
    form_stream.set_raw_data(form_content)
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    form.set_resources(form_resources)

    group = COSDictionary()
    group.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
    )
    group.set_boolean(COSName.get_pdf_name("I"), isolated)
    group.set_boolean(COSName.get_pdf_name("K"), knockout)
    form.set_group(group)

    # Page resources + content: orange backdrop, then Do the group.
    page_resources = PDResources()
    page_resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Fm0"),
        form.get_cos_object(),
    )
    page.set_resources(page_resources)

    page_content = (
        b"1 0.6 0.1 rg\n"  # orange backdrop
        b"0 0 200 200 re\nf\n"
        b"/Fm0 Do\n"
    )
    contents = COSStream()
    contents.set_raw_data(page_content)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    doc.save(str(path))
    doc.close()


_VARIANTS = {
    "nonisolated_nonknockout": {"isolated": False, "knockout": False},
    "isolated_nonknockout": {"isolated": True, "knockout": False},
    "nonisolated_knockout": {"isolated": False, "knockout": True},
    "isolated_knockout": {"isolated": True, "knockout": True},
}


@requires_oracle
@pytest.mark.parametrize("label", list(_VARIANTS), ids=list(_VARIANTS))
def test_transparency_group_composite_matches_pdfbox(
    label: str, tmp_path: Path
) -> None:
    """Each isolated/knockout transparency-group variant must match Java
    PDFBox's render of the same fixture within the 16x16 fingerprint gate."""
    fixture = tmp_path / f"{label}.pdf"
    _build_group_fixture(fixture, **_VARIANTS[label])

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — group compositing mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_isolated_and_nonisolated_both_track_oracle(tmp_path: Path) -> None:
    """The isolated and non-isolated renders must each track their own Java
    oracle (which, for this flat-backdrop geometry, are the same image —
    backdrop removal converges the two modes). This guards against a renderer
    that handles only one isolation mode while breaking the other."""
    iso = tmp_path / "iso.pdf"
    non = tmp_path / "non.pdf"
    _build_group_fixture(iso, isolated=True, knockout=False)
    _build_group_fixture(non, isolated=False, knockout=False)

    with PDDocument.load(iso) as doc:
        iso_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )
    with PDDocument.load(non) as doc:
        non_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )

    _, iso_oracle = _oracle_signature(iso)
    _, non_oracle = _oracle_signature(non)
    iso_mad = sum(
        abs(a - b) for a, b in zip(iso_grid, iso_oracle, strict=True)
    ) / len(iso_grid)
    non_mad = sum(
        abs(a - b) for a, b in zip(non_grid, non_oracle, strict=True)
    ) / len(non_grid)
    assert iso_mad < _MAD_TOLERANCE, (
        f"isolated render diverges from its oracle (mad={iso_mad:.2f})"
    )
    assert non_mad < _MAD_TOLERANCE, (
        f"non-isolated render diverges from its oracle (mad={non_mad:.2f})"
    )


@requires_oracle
def test_isolated_group_color_not_premultiplied(tmp_path: Path) -> None:
    """Direct-pixel regression pin for the premultiplied-RGB bug fixed this
    wave. An isolated group clips its content to its /BBox, so each interior
    fill composites through the clip-mask paint path onto the group's
    *transparent* RGBA canvas. The pre-fix path used PIL ``paste(rgb, mask)``,
    which blends the source RGB toward the (black) destination — producing
    premultiplied colour ``(0,140,140,140)`` for a cyan fill at ``/ca 0.55``.
    That premultiplied colour darkens wrongly when the group composites onto
    the orange page, yielding ``(115,146,89)`` instead of the spec
    ``(115,209,152)``. PDFBox renders ``(115,209,152)``; assert pypdfbox now
    matches and is nowhere near the premultiplied result."""
    fixture = tmp_path / "iso.pdf"
    _build_group_fixture(fixture, isolated=True, knockout=False)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    cyan_only = img.getpixel((40, 100))  # cyan over orange via the group
    expected = (115, 209, 152)  # PDFBox's value at this pixel
    premultiplied_bug = (115, 146, 89)  # the pre-fix premultiplied result
    assert all(abs(cyan_only[i] - expected[i]) <= 4 for i in range(3)), (
        f"isolated cyan region {cyan_only} != PDFBox {expected} — "
        f"group-canvas colour wrong (was {premultiplied_bug} when premultiplied)"
    )
    assert (
        sum(abs(cyan_only[i] - premultiplied_bug[i]) for i in range(3)) > 40
    ), f"isolated cyan region {cyan_only} matches the premultiplied bug value"
