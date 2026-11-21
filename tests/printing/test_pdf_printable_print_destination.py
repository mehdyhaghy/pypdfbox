"""Printing renders for ``RenderDestination.PRINT``.

Upstream ``PDFPrintable.print`` calls ``renderPageToGraphics(...,
RenderDestination.PRINT)``, so an optional content group's
``/Usage /Print /PrintState`` decides whether it prints, not its
``/View`` state. ``PDFPageable`` hands out ``PDFPrintable`` instances, so it
inherits the same destination.
"""

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.printing.pdf_pageable import PDFPageable
from pypdfbox.printing.pdf_printable import PDFPrintable
from pypdfbox.rendering.pdf_renderer import PDFRenderer

_N = COSName.get_pdf_name
_BLUE_FILL = b"/OC /oc1 BDC 0 0 1 rg 0 0 20 20 re f EMC"


def _doc(view_state: str, print_state: str) -> PDDocument:
    usage = COSDictionary()
    for key, state in (("View", view_state), ("Print", print_state)):
        sub = COSDictionary()
        sub.set_item(_N(key + "State"), _N(state))
        usage.set_item(_N(key), sub)
    group = PDOptionalContentGroup("L")
    group.get_cos_object().set_item(_N("Usage"), usage)

    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, 20, 20))
    doc.add_page(page)
    ocp = PDOptionalContentProperties()
    ocp.add_group(group)
    ocp.set_group_enabled(group, True)
    doc.get_document_catalog().set_oc_properties(ocp)
    resources = PDResources()
    resources.put(_N("Properties"), _N("oc1"), group.get_cos_object())
    page.set_resources(resources)
    stream = COSStream()
    stream.set_data(_BLUE_FILL)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    return doc


def _is_blue(img: Image.Image) -> bool:
    width, height = img.size
    return img.convert("RGB").getpixel((width // 2, height // 2)) == (0, 0, 255)


@pytest.mark.parametrize(
    ("view_state", "print_state", "painted"),
    [("OFF", "ON", True), ("ON", "OFF", False)],
    ids=["view_off_print_on", "view_on_print_off"],
)
@pytest.mark.parametrize("dpi", [0.0, 144.0], ids=["default_dpi", "dpi_144"])
def test_printable_render_honors_print_state(
    view_state: str, print_state: str, painted: bool, dpi: float,
) -> None:
    doc = _doc(view_state, print_state)
    try:
        assert _is_blue(PDFPrintable(doc, dpi=dpi).render(0)) is painted
    finally:
        doc.close()


@pytest.mark.parametrize(
    ("view_state", "print_state", "painted"),
    [("OFF", "ON", True), ("ON", "OFF", False)],
    ids=["view_off_print_on", "view_on_print_off"],
)
def test_printable_print_draws_print_destination_image(
    view_state: str, print_state: str, painted: bool,
) -> None:
    doc = _doc(view_state, print_state)
    try:
        drawn: list[Image.Image] = []

        class _Graphics:
            def draw_image(self, img: Image.Image, _x: int, _y: int) -> None:
                drawn.append(img)

        assert PDFPrintable(doc).print(graphics=_Graphics(), page_index=0) == 0
        assert len(drawn) == 1
        assert _is_blue(drawn[0]) is painted
    finally:
        doc.close()


@pytest.mark.parametrize(
    ("view_state", "print_state", "painted"),
    [("OFF", "ON", True), ("ON", "OFF", False)],
    ids=["view_off_print_on", "view_on_print_off"],
)
def test_pageable_printable_honors_print_state(
    view_state: str, print_state: str, painted: bool,
) -> None:
    doc = _doc(view_state, print_state)
    try:
        printable = PDFPageable(doc).get_printable(0)
        assert _is_blue(printable.render()) is painted
    finally:
        doc.close()


def test_print_differs_from_default_export_render() -> None:
    # No /Export entry: the default EXPORT render paints the group, the
    # print render hides it because /PrintState is OFF.
    doc = _doc("ON", "OFF")
    try:
        assert _is_blue(PDFRenderer(doc).render_image(0))
        assert not _is_blue(PDFPrintable(doc).render(0))
    finally:
        doc.close()
