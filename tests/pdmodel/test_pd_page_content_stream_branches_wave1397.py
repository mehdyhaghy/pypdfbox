"""Wave 1397 branch-coverage tests for the resource-key helpers on
``PDPageContentStream``.

Closes False-branch arrows in the lookup loops that walk an existing
resource sub-dictionary searching for a matching COS object:

* ``_resource_key_for_color_space`` 1813->1816, 1814->1813 — sub-dict
  populated but no entry matches → allocate a new slot
* ``_resource_key_for_property_list`` 1827->1830, 1828->1827 — same shape
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_PROPERTIES: COSName = COSName.get_pdf_name("Properties")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")


def _make_doc_and_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return doc, page


def test_resource_key_for_color_space_walks_populated_dict_no_match() -> None:
    """Closes 1813->1816, 1814->1813 — pre-populate /Resources/ColorSpace
    with an unrelated entry so the lookup loop iterates but never
    matches, forcing the ``add`` fallback to allocate a new slot."""
    doc, page = _make_doc_and_page()
    # Pre-populate /Resources/ColorSpace with a dummy entry that does
    # NOT match the cos we'll search for. PDPage.get_resources() returns
    # None when /Resources is absent (wave 1491 strict-null contract), so
    # we use get_or_create_resources() to materialise + back-write the bag.
    res = page.get_or_create_resources()
    cs_dict = COSDictionary()
    other_cos = COSDictionary()
    cs_dict.set_item(COSName.get_pdf_name("CsExisting"), other_cos)
    res.get_cos_object().set_item(_COLOR_SPACE, cs_dict)
    page.set_resources(res)

    with PDPageContentStream(doc, page) as cs:
        # Build a DeviceN color space (non-device, has cos_object) — its
        # cos differs from ``other_cos`` so the loop walks every entry
        # without matching, then ``_resources.add`` allocates a new slot.
        device_n = PDDeviceN()
        key = cs._resource_key_for_color_space(device_n)  # noqa: SLF001
    # Newly allocated key — distinct from the pre-existing CsExisting.
    assert isinstance(key, COSName)
    assert key.get_name() != "CsExisting"


def test_resource_key_for_property_list_walks_populated_dict_no_match() -> None:
    """Closes 1827->1830, 1828->1827 — pre-populate /Resources/Properties
    with an unrelated entry so the loop iterates and fails to match."""
    doc, page = _make_doc_and_page()
    res = page.get_or_create_resources()
    props_dict = COSDictionary()
    other_prop_cos = COSDictionary()
    props_dict.set_item(COSName.get_pdf_name("MCExisting"), other_prop_cos)
    res.get_cos_object().set_item(_PROPERTIES, props_dict)
    # get_or_create_resources() already back-wrote the bag onto the page, so
    # the PDPageContentStream constructor sees our injected entries (wave 1491
    # replaced PDPage's empty-bag fallback with the strict-null contract).
    page.set_resources(res)

    with PDPageContentStream(doc, page) as cs:
        # A brand new PDPropertyList with its own COS — distinct from
        # the pre-populated entry.
        new_prop = PDPropertyList()
        key = cs._resource_key_for_property_list(new_prop)  # noqa: SLF001
    assert isinstance(key, COSName)
    assert key.get_name() != "MCExisting"


