"""PDFBOX-6175 (wave 1603): CIDFont / FontDescriptor resource-cache wiring.

Covers the consumer side of the cache API in
``pypdfbox/pdmodel/pd_resource_cache.py``:

- ``PDType0Font`` reuses a cached descendant ``PDCIDFont`` when a cache is
  supplied (and the descendant's indirect ``/FontDescriptor`` wrapper is
  pooled too);
- no cache -> historical build-per-call behavior is unchanged;
- ``PDPage.remove_resources`` evicts the descendant CIDFont / FontDescriptor
  entries along with the composite font itself.

Perf/memory-only: with and without a cache the observable font surface
(subtype, base font, descendant identity of the underlying COS dicts) is
identical.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_FONT = COSName.get_pdf_name("Font")
_RESOURCES = COSName.get_pdf_name("Resources")


def _build_type0_graph() -> tuple[COSDictionary, COSObject, COSObject, COSObject]:
    """Build a minimal /Type0 font graph with indirect descendant and
    indirect descriptor.

    Returns ``(type0_dict, font_ref, descendant_ref, descriptor_ref)``.
    """
    descriptor_dict = COSDictionary()
    descriptor_dict.set_name(COSName.get_pdf_name("Type"), "FontDescriptor")
    descriptor_dict.set_name(COSName.get_pdf_name("FontName"), "Test-CID")
    descriptor_ref = COSObject(21, 0, resolved=descriptor_dict)

    descendant_dict = COSDictionary()
    descendant_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant_dict.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    descendant_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-CID")
    descendant_dict.set_item(_FONT_DESCRIPTOR, descriptor_ref)
    descendant_ref = COSObject(11, 0, resolved=descendant_dict)

    descendants = COSArray()
    descendants.add(descendant_ref)

    type0_dict = COSDictionary()
    type0_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    type0_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    type0_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-CID")
    type0_dict.set_name(COSName.get_pdf_name("Encoding"), "Identity-H")
    type0_dict.set_item(_DESCENDANT_FONTS, descendants)
    font_ref = COSObject(5, 0, resolved=type0_dict)
    return type0_dict, font_ref, descendant_ref, descriptor_ref


# ---------- descendant reuse through PDType0Font ----------


def test_descendant_reused_when_cache_supplied():
    type0_dict, _, descendant_ref, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    font = PDType0Font(type0_dict, cache)

    first = font.get_descendant_font()
    second = font.get_descendant_font()
    assert first is not None
    assert first is second
    # The wrapper is registered in the cache under the indirect ref.
    assert cache.get_cid_font(descendant_ref) is first


def test_descendant_shared_across_wrappers_via_cache():
    type0_dict, _, _, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    font_a = PDFontFactory.create_font(type0_dict, cache)
    font_b = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font_a, PDType0Font)
    assert isinstance(font_b, PDType0Font)
    assert font_a is not font_b

    descendant_a = font_a.get_descendant_font()
    descendant_b = font_b.get_descendant_font()
    assert descendant_a is not None
    assert descendant_a is descendant_b


def test_factory_forwards_cache_on_type0_arm():
    type0_dict, _, descendant_ref, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    font = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font, PDType0Font)
    descendant = font.get_descendant_font()
    assert descendant is not None
    assert cache.get_cid_font(descendant_ref) is descendant


def test_descriptor_pooled_through_cache():
    type0_dict, _, _, descriptor_ref = _build_type0_graph()
    cache = DefaultResourceCache()
    font = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font, PDType0Font)
    descendant = font.get_descendant_font()
    assert descendant is not None

    fd_first = descendant.get_font_descriptor()
    fd_second = descendant.get_font_descriptor()
    assert fd_first is not None
    assert fd_first is fd_second
    assert cache.get_font_descriptor(descriptor_ref) is fd_first


# ---------- no cache -> unchanged behavior ----------


def test_no_cache_builds_fresh_wrapper_per_call():
    type0_dict, _, _, _ = _build_type0_graph()
    font = PDFontFactory.create_font(type0_dict)
    assert isinstance(font, PDType0Font)

    first = font.get_descendant_font()
    second = font.get_descendant_font()
    assert first is not None
    assert second is not None
    # Historical behavior: a fresh wrapper per call over the same dict.
    assert first is not second
    assert first.get_cos_object() is second.get_cos_object()

    fd_first = first.get_font_descriptor()
    fd_second = first.get_font_descriptor()
    assert fd_first is not None
    assert fd_second is not None
    assert fd_first is not fd_second
    assert fd_first.get_cos_object() is fd_second.get_cos_object()


def test_observable_surface_identical_with_and_without_cache():
    type0_dict, _, _, _ = _build_type0_graph()
    plain = PDType0Font(type0_dict)
    cached = PDType0Font(type0_dict, DefaultResourceCache())

    d_plain = plain.get_descendant_font()
    d_cached = cached.get_descendant_font()
    assert isinstance(d_plain, PDCIDFontType2)
    assert isinstance(d_cached, PDCIDFontType2)
    assert d_plain.get_cos_object() is d_cached.get_cos_object()
    assert d_plain.get_base_font() == d_cached.get_base_font()
    assert (
        plain.get_font_descriptor().get_cos_object()
        is cached.get_font_descriptor().get_cos_object()
    )


def test_direct_descendant_not_cached():
    # A *direct* (inline) descendant dict is never cached — mirrors the
    # indirect-only caching contract upstream.
    type0_dict, _, descendant_ref, _ = _build_type0_graph()
    descendants = COSArray()
    descendants.add(descendant_ref.get_object())  # inline the dict
    type0_dict.set_item(_DESCENDANT_FONTS, descendants)

    cache = DefaultResourceCache()
    font = PDType0Font(type0_dict, cache)
    first = font.get_descendant_font()
    second = font.get_descendant_font()
    assert first is not None
    assert first is not second
    assert cache.get_cid_font(descendant_ref) is None


# ---------- eviction via PDPage.remove_resources ----------


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


def test_remove_resources_evicts_descendant_entries():
    type0_dict, font_ref, descendant_ref, descriptor_ref = _build_type0_graph()
    cache = DefaultResourceCache()
    page, resources = _page_with_font_resource(font_ref, cache)

    font = PDFontFactory.create_font(type0_dict, cache)
    assert isinstance(font, PDType0Font)
    cache.put_font(font_ref, font)
    descendant = font.get_descendant_font()
    assert descendant is not None
    assert descendant.get_font_descriptor() is not None

    # All three entries are cached before the purge.
    assert cache.get_font(font_ref) is font
    assert cache.get_cid_font(descendant_ref) is descendant
    assert cache.get_font_descriptor(descriptor_ref) is not None

    page.remove_resources(resources)

    assert cache.get_font(font_ref) is None
    assert cache.get_cid_font(descendant_ref) is None
    assert cache.get_font_descriptor(descriptor_ref) is None


def test_remove_resources_uncached_font_keeps_descendant_entries():
    # Mirrors the upstream gating: descendant eviction only runs when the
    # composite font itself was removed from the cache. A descendant put
    # there through some other route survives when the parent font was
    # never cached.
    type0_dict, font_ref, descendant_ref, _ = _build_type0_graph()
    cache = DefaultResourceCache()
    page, resources = _page_with_font_resource(font_ref, cache)

    font = PDType0Font(type0_dict, cache)
    descendant = font.get_descendant_font()
    assert descendant is not None
    assert cache.get_cid_font(descendant_ref) is descendant
    # Note: the font itself is NOT put into the cache.

    page.remove_resources(resources)

    assert cache.get_cid_font(descendant_ref) is descendant


def test_remove_resources_without_cache_is_noop():
    type0_dict, font_ref, _, _ = _build_type0_graph()
    del type0_dict
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("F1"), font_ref)
    resources = COSDictionary()
    resources.set_item(_FONT, font_res)
    page = PDPage()
    # No cache attached: must not raise.
    page.remove_resources(resources)


def test_remove_resources_simple_font_has_no_descendant_eviction():
    # A non-composite cached font takes the removal path without touching
    # the descendant hooks (isinstance gate).
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
