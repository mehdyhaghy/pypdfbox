"""PDFBOX-6315 (3.0 branch, unreleased 3.0.9): a self-referencing optional
content visibility expression (``/VE``) must not recurse forever.

Upstream ``PageDrawer.isHiddenVisibilityExpression`` now threads a visited
set of ``/VE`` arrays; re-entering one logs "endless recursion detected in
visibility expression" and counts as not hidden. These tests feed the same
cyclic expressions through the renderer and assert the upstream decision.
"""

import logging
import time

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.pdf_renderer import PDFRenderer

_NOT = COSName.get_pdf_name("Not")
_AND = COSName.get_pdf_name("And")
_OR = COSName.get_pdf_name("Or")


def _ve(op: COSName, *operands: object) -> COSArray:
    arr = COSArray()
    arr.add(op)
    for o in operands:
        arr.add(o)  # type: ignore[arg-type]
    return arr


def _self_ref(op: COSName, *extra: object) -> COSArray:
    arr = _ve(op, *extra)
    arr.add(arr)
    return arr


def _doc_with_ocmd(ve: COSArray, ocg_on: bool = True) -> tuple[
    PDDocument, PDOptionalContentMembershipDictionary, PDOptionalContentGroup
]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, 20, 20))
    doc.add_page(page)
    ocp = PDOptionalContentProperties()
    group = PDOptionalContentGroup("L")
    ocp.add_group(group)
    ocp.set_group_enabled(group, ocg_on)
    doc.get_document_catalog().set_oc_properties(ocp)
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(group)
    ocmd.set_visibility_expression(ve)
    resources = PDResources()
    resources.put(COSName.get_pdf_name("Properties"), COSName.get_pdf_name("oc1"),
                  ocmd.get_cos_object())
    page.set_resources(resources)
    page.get_cos_object().set_item(COSName.CONTENTS, _content_stream(doc))
    return doc, ocmd, group


def _content_stream(doc: PDDocument) -> object:
    from pypdfbox.cos import COSStream

    stream = COSStream()
    stream.set_data(b"/OC /oc1 BDC 0 0 1 rg 0 0 20 20 re f EMC")
    return stream


@pytest.mark.parametrize(
    ("ve_factory", "expect_hidden"),
    [
        # [/Not <self>]: inner re-entry is "not hidden", so Not -> hidden.
        (lambda g: _self_ref(_NOT), True),
        # [/And <self>]: re-entry is not hidden -> And not hidden.
        (lambda g: _self_ref(_AND), False),
        # [/Or <self>]: re-entry is not hidden -> Or not hidden.
        (lambda g: _self_ref(_OR), False),
        # [/And <OFF ocg> <self>]: the OFF group hides it before the cycle.
        (lambda g: _self_ref(_AND, g.get_cos_object()), True),
    ],
    ids=["not_self", "and_self", "or_self", "and_off_then_self"],
)
def test_self_referencing_ve_decision(ve_factory, expect_hidden: bool,
                                      caplog: pytest.LogCaptureFixture) -> None:
    doc = PDDocument()
    ocp = PDOptionalContentProperties()
    group = PDOptionalContentGroup("L")
    ocp.add_group(group)
    ocp.set_group_enabled(group, False)
    doc.get_document_catalog().set_oc_properties(ocp)
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(group)
    ocmd.set_visibility_expression(ve_factory(group))
    renderer = PDFRenderer(doc)
    with caplog.at_level(logging.WARNING):
        start = time.monotonic()
        assert renderer._property_list_is_hidden(ocmd) is expect_hidden
        assert time.monotonic() - start < 1.0
    doc.close()


def test_cycle_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    doc, ocmd, _group = _doc_with_ocmd(_self_ref(_NOT))
    with caplog.at_level(logging.WARNING):
        PDFRenderer(doc)._property_list_is_hidden(ocmd)
    assert "endless recursion detected in visibility expression" in caplog.text
    doc.close()


def test_mutual_recursion_terminates() -> None:
    a = _ve(_NOT)
    b = _ve(_NOT, a)
    a.add(b)
    doc, ocmd, _group = _doc_with_ocmd(a)
    # a -> Not(b) -> Not(a re-entered = not hidden) -> b hidden -> a visible.
    assert PDFRenderer(doc)._property_list_is_hidden(ocmd) is False
    doc.close()


def test_shared_subexpression_counts_once_like_upstream() -> None:
    """Upstream never removes an array from the visited set, so a sub-array
    referenced twice is "not hidden" on its second visit."""
    doc = PDDocument()
    ocp = PDOptionalContentProperties()
    group = PDOptionalContentGroup("L")
    ocp.add_group(group)
    ocp.set_group_enabled(group, False)
    doc.get_document_catalog().set_oc_properties(ocp)
    inner = _ve(_AND, group.get_cos_object())  # hidden (group OFF)
    ve = _ve(_OR, inner, inner)
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(group)
    ocmd.set_visibility_expression(ve)
    # First visit: hidden; second visit: re-entry -> not hidden -> Or visible.
    assert PDFRenderer(doc)._property_list_is_hidden(ocmd) is False
    doc.close()


def test_empty_ve_falls_back_to_policy() -> None:
    """An empty ``/VE`` is ignored and ``/P`` + ``/OCGs`` decide (AnyOn)."""
    doc, ocmd, _group = _doc_with_ocmd(COSArray(), ocg_on=False)
    assert PDFRenderer(doc)._property_list_is_hidden(ocmd) is True
    doc.close()


@pytest.mark.parametrize(
    ("ve_factory", "painted"),
    [(lambda: _self_ref(_NOT), False), (lambda: _self_ref(_AND), True)],
    ids=["not_self_hidden", "and_self_visible"],
)
def test_render_page_with_cyclic_ve(ve_factory, painted: bool) -> None:
    """End to end: render a page whose ``BDC /OC`` references an OCMD with a
    cyclic ``/VE``; it finishes promptly and paints per upstream."""
    doc, _ocmd, _group = _doc_with_ocmd(ve_factory())
    start = time.monotonic()
    image = PDFRenderer(doc).render_image(0)
    assert time.monotonic() - start < 10.0
    pixel = image.convert("RGB").getpixel((10, 10))
    if painted:
        assert pixel == (0, 0, 255)
    else:
        assert pixel == (255, 255, 255)
    doc.close()


def test_page_drawer_visibility_expression_uses_visited_set() -> None:
    doc, _ocmd, _group = _doc_with_ocmd(_self_ref(_NOT))
    renderer = PDFRenderer(doc)
    drawer = PageDrawer.__new__(PageDrawer)
    drawer._renderer = renderer
    assert drawer.is_hidden_visibility_expression(_self_ref(_NOT)) is True
    assert drawer.is_hidden_visibility_expression(_self_ref(_AND)) is False
    doc.close()
