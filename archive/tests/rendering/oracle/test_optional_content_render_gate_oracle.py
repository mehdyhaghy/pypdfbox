"""Live PDFBox differential parity for the OPTIONAL-CONTENT RENDER-TIME
visibility gate — the surfaces NOT already pinned by
``test_optional_content_render_oracle.py`` (wave 1430, page-content ``BDC /OC``
+ Form-XObject ``/OC`` + OCMD ``/P /AnyOn``) or
``test_annot_appearance_oc_oracle.py`` (the same gate inside an annotation
appearance stream).

This file pins the remaining orthogonal render-gate code paths (PDF 32000-1
§8.11.4 / §11.4.4):

* **Image-XObject /OC** (``Do`` gate #2 over an *image* XObject —
  ``xobject.get_oc()``). The existing render oracle exercises the gate on a
  *Form* XObject (which suppresses a content-stream walk); an image XObject
  exercises the distinct image-drawing path. An image whose own ``/OC`` entry
  names an OFF group must NOT paint; forced ON it paints.
* **OCMD with a /VE visibility expression** (``[/Not [ocg]]``). The existing
  oracle uses an OCMD ``/P /AnyOn`` policy; a ``/VE`` expression routes the
  render gate through ``PDOptionalContentMembershipDictionary.evaluate_ve``
  (the And/Or/Not tree walk) rather than the ``/P`` policy fallback.
  ``[/Not [g]]`` over an OFF group is VISIBLE; flipping the group ON makes the
  expression FALSE so the content is hidden — the inverse of a bare-OCG gate,
  which catches a renderer that ignores ``/VE`` and falls back to the policy.
* **Nested /OC** — an inner ``BDC /OC`` (an ON group) nested inside an outer
  ``BDC /OC`` (an OFF group). The outer hides everything until its ``EMC``, so
  the inner content stays hidden despite its own group being ON. This drives
  the renderer's ``_nest_hidden_ocg`` depth counter past 1; a renderer that
  used a boolean "currently hidden" flag instead of a nesting count would
  wrongly un-hide at the inner ``EMC``.

Each fixture is rendered TWICE through the same probe / renderer: once
as-authored and once with the gating OCG force-enabled, and the OFF vs ON
renders must visibly differ (gate is real, not a no-op). Both states must
match Java PDFBox within the established 16x16 luminance fingerprint gate
(``MAD < 6`` / ``MAXDIFF < 60``, 72 DPI) against
``oracle/probes/OptionalContentRenderProbe.java``.

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
content-stream + optional-content API (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
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
# Same gate as the sibling render-parity oracles — comfortably above the AA
# ceiling yet well below the gross-failure floor (a gate that paints hidden
# content, or wrongly suppresses visible content, blows whole bands of cells).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_IMG = 64  # source image side, px
_MB = 200  # media-box side, pt
_OCG_NAME = "Layer1"


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``OptionalContentRenderProbe.java`` (integer-division of pixel coord over
    image size, clamped to the last cell). Matches PIL's "L" Rec.601
    weights."""
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


def _oracle_signature(
    fixture: Path, *force_on: str
) -> tuple[tuple[int, int], list[int]]:
    """Run OptionalContentRenderProbe on page 0, optionally force-enabling
    the named OCG(s) first, and parse its (dims, 16x16 grid)."""
    args = [str(fixture), "0", *force_on]
    lines = run_probe_text("OptionalContentRenderProbe", *args).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _py_signature(
    fixture: Path, *force_on: str
) -> tuple[tuple[int, int], list[int]]:
    """Render page 0 with pypdfbox, optionally force-enabling the named
    OCG(s) in the default config first, and return its (dims, 16x16 grid)."""
    with PDDocument.load(fixture) as doc:
        if force_on:
            ocp = doc.get_document_catalog().get_optional_content_properties()
            if ocp is not None:
                for name in force_on:
                    ocp.set_group_enabled(name, True)
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _install_ocg_off(
    doc: PDDocument, name: str
) -> tuple[PDOptionalContentProperties, PDOptionalContentGroup]:
    """Register an OCG in the catalog's /OCProperties, OFF in the default /D
    config so the gated content starts hidden. Returns (properties, group)."""
    ocp = PDOptionalContentProperties()
    ocg = PDOptionalContentGroup(name)
    ocp.add_group(ocg)
    ocp.set_group_enabled(ocg, False)  # /D /OFF — hidden by default
    doc.get_document_catalog().set_optional_content_properties(ocp)
    return ocp, ocg


def _fill_backdrop(cs: PDPageContentStream, rgb: tuple[float, float, float]) -> None:
    cs.set_non_stroking_color(*rgb)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()


def _build_image_oc_fixture(path: Path) -> None:
    """An image XObject carrying its own ``/OC`` entry naming an OFF group.
    With the group OFF the image must not paint (green backdrop only); forced
    ON the blue raster paints over the centre."""
    doc, page = _new_doc_page()
    _ocp, ocg = _install_ocg_off(doc, _OCG_NAME)

    raster = Image.new("RGB", (_IMG, _IMG), (30, 60, 220))  # blue
    image = LosslessFactory.create_from_image(doc, raster)
    image.set_oc(ocg)
    assert image.get_oc() is not None

    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.7, 0.2))  # green
    cs.draw_image(image, 50, 50, 100, 100)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_ocmd_ve_not_fixture(path: Path) -> None:
    """A red square gated by an OCMD whose ``/VE`` is ``[/Not [Layer1]]`` over
    an OFF group. ``Not(OFF)`` => VISIBLE, so as-authored the red square
    paints over the green backdrop. Force-enabling Layer1 makes the
    expression ``Not(ON)`` => HIDDEN, so the red square disappears — the
    inverse of a bare-OCG gate. A renderer that ignored /VE and fell back to
    the /P policy would get the polarity backwards on one of the two states.
    """
    doc, page = _new_doc_page()
    _ocp, ocg = _install_ocg_off(doc, _OCG_NAME)

    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(ocg)
    # /VE = [/Not <ocg>] — a Not operator over a single OCG-dictionary leaf
    # operand (PDF 32000-1 §8.11.2.4; operands are OCG dicts directly, not
    # singleton arrays).
    ve = COSArray()
    ve.add(COSName.get_pdf_name("Not"))
    ve.add(ocg.get_cos_object())
    ocmd.set_visibility_expression(ve)

    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.7, 0.2))  # green
    cs.begin_marked_content_with_dict("OC", ocmd)
    cs.set_non_stroking_color(0.85, 0.1, 0.1)  # red
    cs.add_rect(50, 50, 100, 100)
    cs.fill()
    cs.end_marked_content()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_nested_oc_fixture(path: Path) -> None:
    """A red square painted inside an inner ``BDC /OC`` (an ON group) that is
    itself nested inside an outer ``BDC /OC`` (the OFF Layer1 group). The
    outer hides everything until its ``EMC``, so as-authored the red square is
    hidden (green backdrop only). Force-enabling Layer1 un-hides the outer and
    the inner-ON content paints. Drives ``_nest_hidden_ocg`` depth past 1."""
    doc, page = _new_doc_page()
    ocp, outer = _install_ocg_off(doc, _OCG_NAME)
    inner = PDOptionalContentGroup("InnerOn")
    ocp.add_group(inner)
    ocp.set_group_enabled(inner, True)  # inner is ON

    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (0.1, 0.7, 0.2))  # green
    cs.begin_marked_content_with_dict("OC", outer)  # OFF — hides everything
    cs.begin_marked_content_with_dict("OC", inner)  # ON — but still nested
    cs.set_non_stroking_color(0.85, 0.1, 0.1)  # red
    cs.add_rect(50, 50, 100, 100)
    cs.fill()
    cs.end_marked_content()  # inner EMC — must NOT un-hide (outer still off)
    cs.end_marked_content()  # outer EMC
    cs.close()
    doc.save(str(path))
    doc.close()


# Each builder pairs with the OCG name(s) the "ON" state force-enables. For
# the /VE-Not case, enabling Layer1 HIDES the content (Not(ON) == False), so
# its visible/hidden polarity is reversed vs the bare-OCG cases — but the
# OFF/ON renders still differ, which is all the parametrised parity asserts.
_BUILDERS = {
    "image_oc": _build_image_oc_fixture,
    "ocmd_ve_not": _build_ocmd_ve_not_fixture,
    "nested_oc": _build_nested_oc_fixture,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
@pytest.mark.parametrize("state", ["off", "on"], ids=["off", "on"])
def test_optional_content_render_gate_matches_pdfbox(
    label: str, state: str, tmp_path: Path
) -> None:
    """Each orthogonal render-gate surface, in both its as-authored (off) and
    force-enabled (on) states, must match Java PDFBox's render of the same
    state within the 16x16 fingerprint gate."""
    fixture = tmp_path / f"{label}_{state}.pdf"
    _BUILDERS[label](fixture)
    force_on = (_OCG_NAME,) if state == "on" else ()

    (java_w, java_h), java_grid = _oracle_signature(fixture, *force_on)
    (py_w, py_h), py_grid = _py_signature(fixture, *force_on)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}/{state}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}/{state}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — optional-content gate mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}/{state}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_off_and_on_renders_visibly_differ(label: str, tmp_path: Path) -> None:
    """Proof the gate is real, not a no-op: the as-authored render and the
    force-enabled render must differ well beyond the AA tolerance. A renderer
    that ignored the gate entirely would produce identical renders."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    _off_dims, off_grid = _py_signature(fixture)
    _on_dims, on_grid = _py_signature(fixture, _OCG_NAME)

    diffs = [abs(a - b) for a, b in zip(off_grid, on_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: as-authored and force-enabled renders are nearly identical "
        f"(mad={mad:.2f}) — the optional-content render gate appears to be a no-op"
    )
