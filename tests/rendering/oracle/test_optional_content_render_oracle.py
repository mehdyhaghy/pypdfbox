"""Live PDFBox differential parity for optional-content (OCG/OCMD) *render-time
visibility*.

Upstream ``PDFRenderer`` honours a page's optional-content configuration while
rasterising: a marked-content sequence ``/OC <props> BDC ... EMC`` whose OCG (or
OCMD) is OFF in the default config paints nothing, an XObject carrying an OFF
``/OC`` group does not paint, and an OCMD ``AnyOn`` membership over a mix of
ON/OFF groups stays visible. This is distinct from the optional-content *model*
parity (``tests/pdmodel/graphics/optionalcontent/oracle/test_ocg_oracle.py``,
``OcgProbe``) which only checks the OCProperties accessors — here we check the
rendered pixels.

Each case BUILDS a one-page PDF via pypdfbox (no bundled fixture carries OC
marked content with renderable geometry), saves it ONCE to ``tmp_path``, then
renders the same bytes through BOTH the Java oracle (``RenderProbe.java`` at
72 DPI, default render state) and pypdfbox at 72 DPI. Pixel-EXACT parity is
impossible (Pillow vs Java2D AA — see ``test_render_oracle.py``), so we compare
the same coarse fingerprint: exact dimensions plus a 16x16 average-luminance
grid, gated at ``MAD < 6`` / ``MAXDIFF < 60``.

Cases:

* ``oc_block_on`` — two fill blocks, both wrapped in ``/OC`` marked content over
  OCGs that are ON. Both paint (visibility evaluated but nothing hidden).
* ``oc_block_off`` — same geometry, but the *second* block's OCG is OFF in the
  default config. The OFF block must NOT paint.
* ``xobject_oc_off`` — a Form XObject whose ``/OC`` points at an OFF OCG. The
  whole XObject must NOT paint.
* ``ocmd_anyon`` — a fill block under an OCMD (``/P /AnyOn``) over two OCGs, one
  ON and one OFF. ``AnyOn`` => visible, so the block paints.

The flip guard (``test_off_block_flipped_on_diverges``) re-renders the
``oc_block_off`` geometry with the second OCG flipped ON and asserts the result
is *materially different* from the OFF reference — proving visibility is actually
evaluated during rendering, not that everything is drawn regardless.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the rest of the render oracle suite — well above the AA ceiling
# (a correct OC render scores MAD ~0) yet far below a gross failure (an OFF
# block still painted, or an ON block dropped, blows the whole-cell luminance).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 200  # media-box side, pt


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


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _black(cs: PDPageContentStream) -> None:
    cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)


# ----------------------------------------------------------------- builders


def _build_two_blocks(path: Path, *, second_off: bool) -> None:
    """Two filled rectangles, each in its own ``/OC`` marked-content sequence.
    The first OCG is always ON; the second is OFF when ``second_off``."""
    doc, page = _new_doc_page()
    props = PDOptionalContentProperties()
    g1 = PDOptionalContentGroup("Block One")
    g2 = PDOptionalContentGroup("Block Two")
    props.add_group(g1)
    props.add_group(g2)
    props.set_base_state("ON")
    if second_off:
        props.set_group_enabled(g2, False)
    doc.get_document_catalog().set_oc_properties(props)

    cs = PDPageContentStream(doc, page)
    _black(cs)
    cs.begin_marked_content_with_dict("OC", g1)
    cs.add_rect(20, 110, 70, 70)
    cs.fill()
    cs.end_marked_content()
    _black(cs)
    cs.begin_marked_content_with_dict("OC", g2)
    cs.add_rect(110, 20, 70, 70)
    cs.fill()
    cs.end_marked_content()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_xobject_oc_off(path: Path) -> None:
    """A Form XObject whose ``/OC`` references an OFF OCG — must not paint."""
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    doc, page = _new_doc_page()
    props = PDOptionalContentProperties()
    g = PDOptionalContentGroup("Hidden Form")
    props.add_group(g)
    props.set_base_state("ON")
    props.set_group_enabled(g, False)
    doc.get_document_catalog().set_oc_properties(props)

    # Build a Form XObject that fills a black square, then tag its /OC at the
    # OFF group so the whole XObject is suppressed at render time.
    form = PDFormXObject(doc)
    form.set_bbox(PDRectangle(0, 0, _MB, _MB))
    form_cs = PDPageContentStream(doc, form)
    _black(form_cs)
    form_cs.add_rect(20, 20, 140, 140)
    form_cs.fill()
    form_cs.close()
    form.set_optional_content(g)

    cs = PDPageContentStream(doc, page)
    cs.draw_form(form)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_ocmd_anyon(path: Path) -> None:
    """A fill block under an OCMD ``/P /AnyOn`` over two OCGs, one ON one OFF.
    AnyOn => at least one ON => visible, so the block paints."""
    doc, page = _new_doc_page()
    props = PDOptionalContentProperties()
    on_group = PDOptionalContentGroup("On Member")
    off_group = PDOptionalContentGroup("Off Member")
    props.add_group(on_group)
    props.add_group(off_group)
    props.set_base_state("ON")
    props.set_group_enabled(off_group, False)
    doc.get_document_catalog().set_oc_properties(props)

    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(on_group)
    ocmd.add_ocg(off_group)
    ocmd.set_visibility_policy("AnyOn")

    cs = PDPageContentStream(doc, page)
    _black(cs)
    cs.begin_marked_content_with_dict("OC", ocmd)
    cs.add_rect(40, 40, 120, 120)
    cs.fill()
    cs.end_marked_content()
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "oc_block_on": lambda p: _build_two_blocks(p, second_off=False),
    "oc_block_off": lambda p: _build_two_blocks(p, second_off=True),
    "xobject_oc_off": _build_xobject_oc_off,
    "ocmd_anyon": _build_ocmd_anyon,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_optional_content_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

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

    # (b) Perceptual grid parity within tolerance. An OFF layer still painted
    # (or an ON layer dropped) lands far outside this gate.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — OC visibility diverges from PDFBox, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_off_block_flipped_on_diverges(tmp_path: Path) -> None:
    """Guard the gate: the SAME page with the second OCG flipped ON must render
    *materially different* from the OFF reference. Proves OC visibility is
    actually evaluated (the OFF block is suppressed), not that everything paints
    regardless. We compare pypdfbox-vs-pypdfbox grids so the guard is
    independent of the Java oracle."""
    off_pdf = tmp_path / "oc_block_off.pdf"
    on_pdf = tmp_path / "oc_block_on.pdf"
    _build_two_blocks(off_pdf, second_off=True)
    _build_two_blocks(on_pdf, second_off=False)

    with PDDocument.load(off_pdf) as doc:
        off_grid = _grid_from_image(PDFRenderer(doc).render_image_with_dpi(0, 72.0))
    with PDDocument.load(on_pdf) as doc:
        on_grid = _grid_from_image(PDFRenderer(doc).render_image_with_dpi(0, 72.0))

    diffs = [abs(a - b) for a, b in zip(off_grid, on_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    # The second 70x70-pt block is ~12% of the page; suppressing it shifts a
    # whole band of cells from black (~0) to white (255), so the MAD is large.
    assert mad >= _MAD_TOLERANCE, (
        "OC visibility not evaluated: flipping the second OCG ON produced a "
        f"render indistinguishable from the OFF reference (MAD {mad:.2f})"
    )
