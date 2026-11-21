"""Optional content ``/Usage`` render states drive rendering per destination.

Upstream ``PageDrawer.isHiddenOCG`` asks the group for
``getRenderState(destination)`` first (``/View /ViewState`` for VIEW,
``/Print /PrintState`` for PRINT, then the ``/Export /ExportState``
fallback). ``OFF`` hides, ``ON`` shows whatever ``/OCProperties`` says, and
only when no usage state applies does ``isGroupEnabled`` decide.
``renderImage`` without a destination uses EXPORT, ``renderPageToGraphics``
uses VIEW.
"""

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
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
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from pypdfbox.rendering.render_destination import RenderDestination

_N = COSName.get_pdf_name
_BLUE_FILL = b"/OC /oc1 BDC 0 0 1 rg 0 0 20 20 re f EMC"

VIEW = RenderDestination.VIEW
PRINT = RenderDestination.PRINT
EXPORT = RenderDestination.EXPORT


def _usage(**states: str) -> COSDictionary:
    """``view="OFF"`` -> ``/View << /ViewState /OFF >>`` and so on."""
    usage = COSDictionary()
    for key, state in states.items():
        sub = COSDictionary()
        sub.set_item(_N(key.capitalize() + "State"), _N(state))
        usage.set_item(_N(key.capitalize()), sub)
    return usage


def _group(usage: COSDictionary | None) -> PDOptionalContentGroup:
    group = PDOptionalContentGroup("L")
    if usage is not None:
        group.get_cos_object().set_item(_N("Usage"), usage)
    return group


def _doc(
    group: PDOptionalContentGroup,
    enabled: bool,
    oc_object: COSDictionary | None = None,
    content: bytes = _BLUE_FILL,
) -> PDDocument:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, 20, 20))
    doc.add_page(page)
    ocp = PDOptionalContentProperties()
    ocp.add_group(group)
    ocp.set_group_enabled(group, enabled)
    doc.get_document_catalog().set_oc_properties(ocp)
    resources = PDResources()
    resources.put(
        _N("Properties"),
        _N("oc1"),
        oc_object if oc_object is not None else group.get_cos_object(),
    )
    page.set_resources(resources)
    stream = COSStream()
    stream.set_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    return doc


def _is_blue(img: Image.Image) -> bool:
    return img.convert("RGB").getpixel((10, 10)) == (0, 0, 255)


def _render(doc: PDDocument, destination: RenderDestination | None) -> bool:
    return _is_blue(PDFRenderer(doc).render_image(0, destination=destination))


# (usage, /OCProperties enabled, destination, expect painted)
_CASES = [
    # No usage: /OCProperties decides for every destination.
    (None, True, VIEW, True),
    (None, False, VIEW, False),
    (None, False, PRINT, False),
    # View OFF / Print ON, group enabled in the default config.
    ({"view": "OFF", "print": "ON"}, True, VIEW, False),
    ({"view": "OFF", "print": "ON"}, True, PRINT, True),
    # Usage ON overrides an OFF default config.
    ({"view": "OFF", "print": "ON"}, False, PRINT, True),
    ({"view": "ON"}, False, VIEW, True),
    # No /View or /Print entry: falls back to /Export.
    ({"export": "OFF"}, True, VIEW, False),
    ({"export": "OFF"}, True, PRINT, False),
    ({"export": "ON"}, False, EXPORT, True),
    # A /View entry is not consulted for PRINT or EXPORT.
    ({"view": "OFF"}, True, PRINT, True),
    ({"view": "OFF"}, True, EXPORT, True),
    ({"view": "ON"}, False, EXPORT, False),
    # The targeted entry wins over /Export.
    ({"print": "ON", "export": "OFF"}, True, PRINT, True),
    ({"print": "OFF", "export": "ON"}, True, PRINT, False),
]


@pytest.mark.parametrize(
    ("usage", "enabled", "destination", "painted"),
    _CASES,
    ids=[f"case{i}" for i in range(len(_CASES))],
)
def test_marked_content_uses_usage_state(
    usage: dict[str, str] | None,
    enabled: bool,
    destination: RenderDestination,
    painted: bool,
) -> None:
    group = _group(_usage(**usage) if usage is not None else None)
    doc = _doc(group, enabled)
    try:
        assert _render(doc, destination) is painted
    finally:
        doc.close()


def test_render_image_default_destination_is_export() -> None:
    group = _group(_usage(view="OFF", export="ON"))
    doc = _doc(group, True)
    try:
        renderer = PDFRenderer(doc)
        assert renderer.get_default_destination() is None
        # Default render resolves to EXPORT -> /ExportState ON paints.
        assert _is_blue(renderer.render_image(0)) is True
        renderer.set_default_destination(VIEW)
        assert _is_blue(renderer.render_image(0)) is False
    finally:
        doc.close()


def test_render_page_to_graphics_default_destination_is_view() -> None:
    group = _group(_usage(view="OFF", export="ON"))
    doc = _doc(group, True)
    try:
        renderer = PDFRenderer(doc)
        target = Image.new("RGB", (20, 20), (255, 255, 255))
        renderer.render_page_to_graphics(0, target)
        assert _is_blue(target) is False
        target = Image.new("RGB", (20, 20), (255, 255, 255))
        renderer.render_page_to_graphics(0, target, destination=EXPORT)
        assert _is_blue(target) is True
    finally:
        doc.close()


def test_ocmd_members_use_usage_state() -> None:
    group = _group(_usage(view="OFF", print="ON"))
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(group)
    doc = _doc(group, True, oc_object=ocmd.get_cos_object())
    try:
        assert _render(doc, VIEW) is False
        assert _render(doc, PRINT) is True
    finally:
        doc.close()


def test_ocmd_visibility_expression_uses_usage_state() -> None:
    group = _group(_usage(print="OFF"))
    ve = COSArray()
    ve.add(_N("And"))
    ve.add(group.get_cos_object())
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_expression(ve)
    doc = _doc(group, True, oc_object=ocmd.get_cos_object())
    try:
        assert _render(doc, PRINT) is False
        assert _render(doc, VIEW) is True
    finally:
        doc.close()


def test_form_xobject_oc_uses_usage_state() -> None:
    group = _group(_usage(view="OFF", print="ON"))
    form = COSStream()
    form.set_item(COSName.TYPE, _N("XObject"))
    form.set_item(COSName.SUBTYPE, _N("Form"))
    form.set_item(_N("BBox"), PDRectangle(0, 0, 20, 20).get_cos_array())
    form.set_item(_N("OC"), group.get_cos_object())
    form.set_data(b"0 0 1 rg 0 0 20 20 re f")
    doc = _doc(group, False, content=b"/Fm1 Do")
    try:
        page = doc.get_page(0)
        page.get_resources().put(_N("XObject"), _N("Fm1"), form)
        # Group is OFF in /OCProperties, but /PrintState ON shows it.
        assert _render(doc, PRINT) is True
        assert _render(doc, VIEW) is False
    finally:
        doc.close()


def test_page_drawer_is_hidden_ocg_uses_its_destination() -> None:
    group = _group(_usage(view="OFF", print="ON"))
    doc = _doc(group, True)
    try:
        renderer = PDFRenderer(doc)
        page = doc.get_page(0)

        def drawer(dest: RenderDestination | None) -> PageDrawer:
            return PageDrawer(
                PageDrawerParameters(
                    renderer=renderer,
                    page=page,
                    subsampling_allowed=False,
                    hinting_enabled=False,
                    destination=dest,
                    rendering_hints=None,
                    image_downscaling_optimization_threshold=0.5,
                )
            )

        assert drawer(VIEW).is_hidden_ocg(group) is True
        assert drawer(PRINT).is_hidden_ocg(group) is False
        # A null destination only consults /Export; none here, so the
        # enabled /OCProperties state decides.
        assert drawer(None).is_hidden_ocg(group) is False
        ocmd = PDOptionalContentMembershipDictionary()
        ocmd.add_ocg(group)
        assert drawer(VIEW).is_hidden_ocg(ocmd) is True
        assert drawer(PRINT).is_hidden_ocg(ocmd) is False
    finally:
        doc.close()
