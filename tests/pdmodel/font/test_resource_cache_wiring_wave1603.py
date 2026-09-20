"""PDFBOX-6175 revert (upstream cab99713, shipped in PDFBox 3.0.8).

Wave 1603 forward-ported the PDFBOX-6175 ``ResourceCache`` extension that
pooled ``PDCIDFont`` and ``PDFontDescriptor`` wrappers. Upstream reverted
that extension before 3.0.8 shipped — *"a descendant font refers to its
parent font, so that it can't be shared or cached"*. Sharing one
``PDCIDFont`` between two ``PDType0Font`` parents hands the second parent a
descendant whose ``get_parent()`` still points at the first, which corrupts
every parent-mediated lookup (``/W`` widths, ``/Encoding``, ``to_unicode``).

This file locks the revert in. It asserts:

- the six cache methods are **absent** from both ``PDResourceCache`` and
  ``DefaultResourceCache``;
- the ``resource_cache`` constructor parameter is gone from ``PDFont`` /
  ``PDType0Font``;
- descendant fonts are **not** shared — two ``PDType0Font`` wrappers over
  the same indirect ``/DescendantFonts`` entry get distinct ``PDCIDFont``
  instances, each bound to its own parent, even when a resource cache is
  attached to the page / document;
- ``PDPage.remove_resources`` still evicts the composite font itself and
  carries no descendant-eviction machinery.
"""

import inspect

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache, PDResourceCache
from pypdfbox.pdmodel.pd_resources import PDResources

_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_FONT = COSName.get_pdf_name("Font")
_RESOURCES = COSName.get_pdf_name("Resources")

#: The method surface PDFBOX-6175 added and cab99713 removed again.
_REMOVED_CACHE_METHODS = (
    "get_cid_font",
    "put_cid_font",
    "remove_cid_font",
    "get_font_descriptor",
    "put_font_descriptor",
    "remove_font_descriptor",
)


def _descriptor_ref(number: int = 21) -> COSObject:
    descriptor_dict = COSDictionary()
    descriptor_dict.set_name(COSName.get_pdf_name("Type"), "FontDescriptor")
    descriptor_dict.set_name(COSName.get_pdf_name("FontName"), "Test-CID")
    return COSObject(number, 0, resolved=descriptor_dict)


def _descendant_ref(descriptor_ref: COSObject, number: int = 11) -> COSObject:
    descendant_dict = COSDictionary()
    descendant_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant_dict.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    descendant_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-CID")
    descendant_dict.set_item(_FONT_DESCRIPTOR, descriptor_ref)
    return COSObject(number, 0, resolved=descendant_dict)


def _type0_dict(descendant_ref: COSObject) -> COSDictionary:
    descendants = COSArray()
    descendants.add(descendant_ref)
    type0_dict = COSDictionary()
    type0_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    type0_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    type0_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-CID")
    type0_dict.set_name(COSName.get_pdf_name("Encoding"), "Identity-H")
    type0_dict.set_item(_DESCENDANT_FONTS, descendants)
    return type0_dict


def _build_type0_graph() -> tuple[COSDictionary, COSObject, COSObject, COSObject]:
    """Build a minimal /Type0 font graph with indirect descendant and
    indirect descriptor.

    Returns ``(type0_dict, font_ref, descendant_ref, descriptor_ref)``.
    """
    descriptor_ref = _descriptor_ref()
    descendant_ref = _descendant_ref(descriptor_ref)
    type0_dict = _type0_dict(descendant_ref)
    font_ref = COSObject(5, 0, resolved=type0_dict)
    return type0_dict, font_ref, descendant_ref, descriptor_ref


# ---------- the removed API surface is gone ----------


def test_resource_cache_has_no_cid_font_or_descriptor_methods():
    for name in _REMOVED_CACHE_METHODS:
        assert not hasattr(PDResourceCache, name), (
            f"PDResourceCache.{name} was removed upstream in cab99713"
        )
        assert not hasattr(DefaultResourceCache, name), (
            f"DefaultResourceCache.{name} was removed upstream in cab99713"
        )


def test_default_resource_cache_instance_exposes_no_removed_methods():
    cache = DefaultResourceCache()
    for name in _REMOVED_CACHE_METHODS:
        assert not hasattr(cache, name)
    # The backing maps are gone too — no private residue.
    assert not hasattr(cache, "_cid_fonts")
    assert not hasattr(cache, "_font_descriptors")


def test_default_resource_cache_clear_does_not_touch_removed_maps():
    # ``clear()`` must not reference the deleted dicts.
    DefaultResourceCache().clear()


def test_font_constructors_take_no_resource_cache_argument():
    for cls in (PDFont, PDType0Font):
        params = list(inspect.signature(cls.__init__).parameters)
        assert "resource_cache" not in params, (
            f"{cls.__name__}.__init__ still accepts resource_cache"
        )
    font = PDType0Font(_type0_dict(_descendant_ref(_descriptor_ref())))
    assert not hasattr(font, "_resource_cache")


def test_page_has_no_descendant_eviction_helper():
    assert not hasattr(PDPage, "_remove_descendant_font_entries")


def test_put_routes_cid_font_to_the_single_font_slot():
    """``DefaultResourceCache.put`` no longer has a CID-font overload; a
    ``PDCIDFont`` (a ``PDFont`` subclass in pypdfbox) lands in the one font
    slot, matching upstream's single ``put(COSObject, PDFont)``."""
    _, _, descendant_ref, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    cid_font = PDCIDFontType2(descendant_ref.get_object())
    cache.put(descendant_ref, cid_font)
    assert cache.get_font(descendant_ref) is cid_font


# ---------- descendant fonts are not shared ----------


def test_descendant_font_is_rebuilt_per_call():
    type0_dict, _, _, _ = _build_type0_graph()
    font = PDType0Font(type0_dict)
    first = font.get_descendant_font()
    second = font.get_descendant_font()
    assert isinstance(first, PDCIDFontType2)
    assert isinstance(second, PDCIDFontType2)
    assert first is not second
    assert first.get_cos_object() is second.get_cos_object()


def test_descendant_not_shared_between_two_type0_parents():
    """The reason for the revert: one descendant dict referenced by two
    composite fonts must yield two wrappers, each bound to its own parent."""
    descriptor_ref = _descriptor_ref()
    descendant_ref = _descendant_ref(descriptor_ref)
    parent_a = PDType0Font(_type0_dict(descendant_ref))
    parent_b = PDType0Font(_type0_dict(descendant_ref))

    descendant_a = parent_a.get_descendant_font()
    descendant_b = parent_b.get_descendant_font()
    assert descendant_a is not None
    assert descendant_b is not None
    assert descendant_a is not descendant_b
    assert descendant_a.get_parent() is parent_a
    assert descendant_b.get_parent() is parent_b


def test_factory_does_not_pool_descendants_through_the_cache():
    type0_dict, _, _, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    font_a = PDFontFactory.create_font(type0_dict, cache)
    font_b = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font_a, PDType0Font)
    assert isinstance(font_b, PDType0Font)

    descendant_a = font_a.get_descendant_font()
    descendant_b = font_b.get_descendant_font()
    assert descendant_a is not None
    assert descendant_b is not None
    assert descendant_a is not descendant_b
    assert descendant_a.get_parent() is font_a
    assert descendant_b.get_parent() is font_b


def test_font_descriptor_wrapper_is_rebuilt_per_call():
    type0_dict, _, _, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    font = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font, PDType0Font)
    descendant = font.get_descendant_font()
    assert descendant is not None

    fd_first = descendant.get_font_descriptor()
    fd_second = descendant.get_font_descriptor()
    assert fd_first is not None
    assert fd_second is not None
    assert fd_first is not fd_second
    assert fd_first.get_cos_object() is fd_second.get_cos_object()


def test_two_pages_sharing_a_descendant_get_distinct_cid_fonts():
    """Two pages, one shared document-level cache, two composite fonts that
    reference the **same** indirect descendant: each page's descendant must
    be its own instance bound to its own parent font."""
    descriptor_ref = _descriptor_ref()
    descendant_ref = _descendant_ref(descriptor_ref)
    font_ref_a = COSObject(5, 0, resolved=_type0_dict(descendant_ref))
    font_ref_b = COSObject(6, 0, resolved=_type0_dict(descendant_ref))

    cache = DefaultResourceCache()
    page_a, _ = _page_with_font_resource(font_ref_a, cache)
    page_b, _ = _page_with_font_resource(font_ref_b, cache)

    name = COSName.get_pdf_name("F1")
    font_a = _page_resources(page_a, cache).get_font(name)
    font_b = _page_resources(page_b, cache).get_font(name)
    assert isinstance(font_a, PDType0Font)
    assert isinstance(font_b, PDType0Font)
    assert font_a is not font_b

    descendant_a = font_a.get_descendant_font()
    descendant_b = font_b.get_descendant_font()
    assert descendant_a is not None
    assert descendant_b is not None
    assert descendant_a is not descendant_b
    assert descendant_a.get_cos_object() is descendant_b.get_cos_object()
    assert descendant_a.get_parent() is font_a
    assert descendant_b.get_parent() is font_b


# ---------- PDPage.remove_resources ----------


def _page_with_font_resource(
    font_ref: COSObject, cache: DefaultResourceCache
) -> tuple[PDPage, COSDictionary]:
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("F1"), font_ref)
    resources = COSDictionary()
    resources.set_item(_FONT, font_res)
    page_dict = COSDictionary()
    page_dict.set_name(COSName.get_pdf_name("Type"), "Page")
    page_dict.set_item(_RESOURCES, resources)
    page = PDPage(page_dict, cache)
    return page, resources


def _page_resources(page: PDPage, cache: DefaultResourceCache) -> PDResources:
    raw = page.get_cos_object().get_dictionary_object(_RESOURCES)
    assert isinstance(raw, COSDictionary)
    return PDResources(raw, resource_cache=cache)


def test_remove_resources_evicts_only_the_composite_font():
    type0_dict, font_ref, _, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    page, resources = _page_with_font_resource(font_ref, cache)

    font = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font, PDType0Font)
    cache.put_font(font_ref, font)
    assert cache.get_font(font_ref) is font

    page.remove_resources(resources)
    assert cache.get_font(font_ref) is None


def test_remove_resources_without_cache_is_noop():
    _, font_ref, _, _ = _build_type0_graph()
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("F1"), font_ref)
    resources = COSDictionary()
    resources.set_item(_FONT, font_res)
    page = PDPage()
    # No cache attached: must not raise.
    page.remove_resources(resources)


def test_remove_resources_handles_simple_fonts():
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font_ref = COSObject(31, 0, resolved=font_dict)

    cache = DefaultResourceCache()
    page, resources = _page_with_font_resource(font_ref, cache)
    font = PDFontFactory.create_font(font_dict, cache)
    assert font is not None
    cache.put_font(font_ref, font)

    page.remove_resources(resources)
    assert cache.get_font(font_ref) is None
