"""PDFBOX-6175 on upstream trunk (4.0.0-SNAPSHOT): shared CIDFonts.

Upstream trunk extended ``ResourceCache`` so that ``PDCIDFont`` and
``PDFontDescriptor`` instances can be shared when they are referenced more
than once (``b0715897``), made that safe by removing the parent Type 0 font
from ``PDCIDFont`` (``51111f06`` / ``7ee9ce66``), and enabled caching of the
FontDescriptor of a Type 0 font (``bf37c60d``). The 3.0 branch reverted the
extension instead (``cab99713``); pypdfbox follows trunk.

This file pins:

- the six cache methods on ``PDResourceCache`` / ``DefaultResourceCache``;
- the ``resource_cache`` constructor argument on the font classes;
- a descendant ``PDCIDFont`` holds no parent reference;
- two Type 0 fonts sharing one indirect descendant and one font descriptor
  get the same cached ``PDCIDFont``, and both still extract and render
  exactly like two fonts with private descendants;
- ``PDPage.remove_resources`` evicts the descendant and its descriptor.
"""

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache, PDResourceCache
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_FONT = COSName.get_pdf_name("Font")
_RESOURCES = COSName.get_pdf_name("Resources")
_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

_CACHE_METHODS = (
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


def _type0_dict(descendant: COSObject | COSDictionary) -> COSDictionary:
    descendants = COSArray()
    descendants.add(descendant)
    type0_dict = COSDictionary()
    type0_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    type0_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    type0_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-CID")
    type0_dict.set_name(COSName.get_pdf_name("Encoding"), "Identity-H")
    type0_dict.set_item(_DESCENDANT_FONTS, descendants)
    return type0_dict


def _page_with_fonts(
    cache: DefaultResourceCache, *font_refs: COSObject
) -> tuple[PDPage, COSDictionary]:
    font_res = COSDictionary()
    for index, font_ref in enumerate(font_refs, start=1):
        font_res.set_item(COSName.get_pdf_name(f"F{index}"), font_ref)
    resources = COSDictionary()
    resources.set_item(_FONT, font_res)
    page_dict = COSDictionary()
    page_dict.set_name(COSName.get_pdf_name("Type"), "Page")
    page_dict.set_item(_RESOURCES, resources)
    return PDPage(page_dict, cache), resources


# ---------- API surface ----------


def test_resource_cache_exposes_cid_font_and_descriptor_methods() -> None:
    cache = DefaultResourceCache()
    for name in _CACHE_METHODS:
        assert hasattr(PDResourceCache, name)
        assert callable(getattr(cache, name))


def test_font_constructors_accept_a_resource_cache() -> None:
    for cls in (
        PDFont,
        PDType0Font,
        PDType1Font,
        PDType1CFont,
        PDTrueTypeFont,
        PDType3Font,
        PDCIDFont,
    ):
        code = cls.__init__.__code__
        params = code.co_varnames[: code.co_argcount]
        assert "resource_cache" in params, cls.__name__


def test_descendant_has_no_parent_reference() -> None:
    font = PDType0Font(_type0_dict(_descendant_ref(_descriptor_ref())))
    descendant = font.get_descendant_font()
    assert isinstance(descendant, PDCIDFontType2)
    assert not isinstance(descendant, PDFont)
    assert not hasattr(descendant, "get_parent")
    assert not hasattr(descendant, "_parent")
    assert not hasattr(descendant, "get_name")
    assert all(value is not font for value in vars(descendant).values())


def test_descendant_constructor_rejects_a_parent_font() -> None:
    font = PDType0Font(_type0_dict(_descendant_ref(_descriptor_ref())))
    descendant_dict = _descendant_ref(_descriptor_ref()).get_object()
    with pytest.raises(TypeError):
        PDCIDFontType2(descendant_dict, font)
    with pytest.raises(TypeError):
        PDFontFactory.create_descendant_font(descendant_dict, font)


def test_descendant_is_built_once_per_parent_without_cache() -> None:
    font = PDType0Font(_type0_dict(_descendant_ref(_descriptor_ref())))
    first = font.get_descendant_font()
    assert first is not None
    assert font.get_descendant_font() is first


# ---------- sharing through the cache ----------


def test_type0_fonts_sharing_a_descendant_share_one_cid_font() -> None:
    descriptor_ref = _descriptor_ref()
    descendant_ref = _descendant_ref(descriptor_ref)
    cache = DefaultResourceCache()
    font_a = PDFontFactory.create_font(_type0_dict(descendant_ref), cache)
    font_b = PDFontFactory.create_font(_type0_dict(descendant_ref), cache)
    assert isinstance(font_a, PDType0Font)
    assert isinstance(font_b, PDType0Font)
    assert font_a is not font_b

    descendant_a = font_a.get_descendant_font()
    descendant_b = font_b.get_descendant_font()
    assert descendant_a is not None
    assert descendant_a is descendant_b
    assert cache.get_cid_font(descendant_ref) is descendant_a

    # the descendant's indirect /FontDescriptor is shared as well (bf37c60d)
    fd = descendant_a.get_font_descriptor()
    assert fd is not None
    assert cache.get_font_descriptor(descriptor_ref) is fd
    assert descendant_b.get_font_descriptor() is fd
    assert font_a.get_font_descriptor() is fd
    assert font_b.get_font_descriptor() is fd


def test_direct_descendant_is_not_cached() -> None:
    descendant_dict = _descendant_ref(_descriptor_ref()).get_object()
    cache = DefaultResourceCache()
    font = PDFontFactory.create_font(_type0_dict(descendant_dict), cache)
    assert isinstance(font, PDType0Font)
    assert font.get_descendant_font() is not None
    assert cache._cid_fonts == {}


def test_without_cache_each_parent_builds_its_own_descendant() -> None:
    descendant_ref = _descendant_ref(_descriptor_ref())
    font_a = PDType0Font(_type0_dict(descendant_ref))
    font_b = PDType0Font(_type0_dict(descendant_ref))
    assert font_a.get_descendant_font() is not font_b.get_descendant_font()


def test_simple_font_descriptor_is_shared_through_the_cache() -> None:
    descriptor_ref = _descriptor_ref(41)
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.SUBTYPE, "TrueType")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-TT")
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor_ref)
    cache = DefaultResourceCache()
    font = PDFontFactory.create_font(font_dict, cache)
    assert font is not None
    fd = font.get_font_descriptor()
    assert fd is not None
    assert cache.get_font_descriptor(descriptor_ref) is fd
    assert font.get_font_descriptor() is fd


# ---------- shared descendant: text extraction and rendering ----------


def _build_two_font_pdf(*, share_descendant: bool) -> bytes:
    """One page, two Type 0 fonts. With ``share_descendant`` both parents
    reference the same /DescendantFonts entry (one indirect CIDFont and one
    FontDescriptor after saving); otherwise the second parent gets a deep
    copy of the descendant."""
    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    font_a = PDType0Font.load(doc, str(_TTF), False)
    font_dict_b = COSDictionary()
    for key, value in font_a.get_cos_object().entry_set():
        font_dict_b.set_item(key, value)
    if not share_descendant:
        descendant_copy = COSDictionary()
        descendant = font_a.get_descendant_font()
        assert descendant is not None
        for key, value in descendant.get_cos_object().entry_set():
            descendant_copy.set_item(key, value)
        own = COSArray()
        own.add(descendant_copy)
        font_dict_b.set_item(_DESCENDANT_FONTS, own)
    font_b = PDType0Font(font_dict_b)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font_a, 24)
        cs.new_line_at_offset(50, 700)
        cs.show_text("Hello")
        cs.end_text()
        cs.begin_text()
        cs.set_font(font_b, 18)
        cs.new_line_at_offset(50, 650)
        cs.show_text("World")
        cs.end_text()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _type0_fonts(doc: PDDocument) -> list[PDType0Font]:
    resources = doc.get_page(0).get_resources()
    assert resources is not None
    fonts = [resources.get_font(name) for name in resources.get_font_names()]
    assert len(fonts) == 2
    assert all(isinstance(font, PDType0Font) for font in fonts)
    return fonts  # type: ignore[return-value]


class _CachedPage(PDPage):
    """Page-tree page that carries a document resource cache, as upstream
    ``PDPageTree`` does (``new PDPage(dict, document.getResourceCache())``).
    pypdfbox's page tree builds cache-less pages, so without this the
    renderer and the text stripper would never reach the shared cache."""

    current_cache: DefaultResourceCache | None = None

    def __init__(self, page=None, resource_cache=None):  # type: ignore[no-untyped-def]
        super().__init__(page, resource_cache or _CachedPage.current_cache)


def test_shared_descendant_extracts_and_renders_like_private_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel import pd_page_tree

    monkeypatch.setattr(pd_page_tree, "PDPage", _CachedPage)
    page_class = _CachedPage
    shared_doc = PDDocument.load(_build_two_font_pdf(share_descendant=True))
    private_doc = PDDocument.load(_build_two_font_pdf(share_descendant=False))
    try:
        page_class.current_cache = shared_doc.get_resource_cache()
        shared_a, shared_b = _type0_fonts(shared_doc)
        descendant = shared_a.get_descendant_font()
        assert descendant is not None
        # one indirect descendant + one indirect FontDescriptor in the file
        raw = shared_a.get_cos_object().get_dictionary_object(_DESCENDANT_FONTS).get(0)
        assert isinstance(raw, COSObject)
        assert isinstance(descendant.get_cos_object().get_item(_FONT_DESCRIPTOR), COSObject)
        # ... shared by both parents through the document cache
        assert shared_b.get_descendant_font() is descendant
        assert shared_doc.get_resource_cache().get_cid_font(raw) is descendant
        assert shared_b.get_font_descriptor() is shared_a.get_font_descriptor()
        shared_text = PDFTextStripper().get_text(shared_doc)
        shared_image = PDFRenderer(shared_doc).render_image(0)

        page_class.current_cache = private_doc.get_resource_cache()
        private_a, private_b = _type0_fonts(private_doc)
        assert private_a.get_descendant_font() is not private_b.get_descendant_font()

        # both parents resolve glyphs through the shared descendant
        for code in (0x2B, 0x48, 0x5A):
            assert shared_a.get_width(code) == private_a.get_width(code)
            assert shared_b.get_width(code) == private_b.get_width(code)
            assert shared_a.get_path(code) == private_b.get_path(code)
            assert shared_b.to_unicode(code) == private_b.to_unicode(code)

        assert shared_text == PDFTextStripper().get_text(private_doc)
        assert "Hello" in shared_text
        assert "World" in shared_text

        private_image = PDFRenderer(private_doc).render_image(0)
        assert shared_image.tobytes() == private_image.tobytes()
        assert shared_image.convert("L").getextrema()[0] < 128  # text was drawn
    finally:
        shared_doc.close()
        private_doc.close()


# ---------- PDPage.remove_resources ----------


def test_remove_resources_evicts_descendant_and_its_descriptor() -> None:
    descriptor_ref = _descriptor_ref()
    descendant_ref = _descendant_ref(descriptor_ref)
    font_ref = COSObject(5, 0, resolved=_type0_dict(descendant_ref))
    cache = DefaultResourceCache()
    page, resources = _page_with_fonts(cache, font_ref)

    font = PDResources(resources, resource_cache=cache).get_font(
        COSName.get_pdf_name("F1")
    )
    assert isinstance(font, PDType0Font)
    descendant = font.get_descendant_font()
    assert descendant is not None
    assert descendant.get_font_descriptor() is not None
    assert cache.get_font(font_ref) is font
    assert cache.get_cid_font(descendant_ref) is descendant
    assert cache.get_font_descriptor(descriptor_ref) is not None

    page.remove_resources(resources)
    assert cache.get_font(font_ref) is None
    assert cache.get_cid_font(descendant_ref) is None
    assert cache.get_font_descriptor(descriptor_ref) is None


def test_remove_resources_evicts_simple_font_descriptor() -> None:
    descriptor_ref = _descriptor_ref(42)
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.SUBTYPE, "TrueType")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test-TT")
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor_ref)
    font_ref = COSObject(31, 0, resolved=font_dict)
    cache = DefaultResourceCache()
    page, resources = _page_with_fonts(cache, font_ref)
    font = PDResources(resources, resource_cache=cache).get_font(
        COSName.get_pdf_name("F1")
    )
    assert font is not None
    assert font.get_font_descriptor() is not None
    assert cache.get_font_descriptor(descriptor_ref) is not None

    page.remove_resources(resources)
    assert cache.get_font(font_ref) is None
    assert cache.get_font_descriptor(descriptor_ref) is None


def test_remove_resources_keeps_internals_of_a_stable_font() -> None:
    """Upstream skips the descendant eviction when ``removeFont`` returns
    ``null`` — which the stable-cache guard does after ``MAX_REMOVALS``."""
    descriptor_ref = _descriptor_ref()
    descendant_ref = _descendant_ref(descriptor_ref)
    font_ref = COSObject(5, 0, resolved=_type0_dict(descendant_ref))
    cache = DefaultResourceCache()
    page, resources = _page_with_fonts(cache, font_ref)
    name = COSName.get_pdf_name("F1")
    for _ in range(DefaultResourceCache.MAX_REMOVALS - 1):
        font = PDResources(resources, resource_cache=cache).get_font(name)
        assert font is not None
        font.get_descendant_font()
        page.remove_resources(resources)
    font = PDResources(resources, resource_cache=cache).get_font(name)
    assert isinstance(font, PDType0Font)
    descendant = font.get_descendant_font()
    page.remove_resources(resources)  # stable now: nothing is evicted
    assert cache.get_font(font_ref) is font
    assert cache.get_cid_font(descendant_ref) is descendant


def test_remove_resources_without_cache_is_noop() -> None:
    font_ref = COSObject(5, 0, resolved=_type0_dict(_descendant_ref(_descriptor_ref())))
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("F1"), font_ref)
    resources = COSDictionary()
    resources.set_item(_FONT, font_res)
    PDPage().remove_resources(resources)


def test_shared_descendant_resolves_codes_through_each_parents_cmap() -> None:
    """A shared descendant answers per-glyph questions through the parent it
    is handed, so parents with different encodings never see each other's
    code -> CID results (pypdfbox keeps no per-code memo on the shared
    descendant for that reason)."""
    from pypdfbox.cos import COSInteger, COSStream

    descendant_ref = _descendant_ref(_descriptor_ref())
    widths = COSArray()
    for value in (1, 1, 100, 5, 5, 500):
        widths.add(COSInteger.get(value))
    descendant_ref.get_object().set_item(COSName.get_pdf_name("W"), widths)

    cmap_stream = COSStream()
    cmap_stream.set_raw_data(
        b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        b"/CMapName /Test-Remap def /CMapType 1 def\n"
        b"1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
        b"1 begincidrange <0001> <0001> 5 endcidrange\n"
        b"endcmap CMapName currentdict /CMap defineresource pop end end\n"
    )
    remapped = _type0_dict(descendant_ref)
    remapped.set_item(COSName.get_pdf_name("Encoding"), cmap_stream)

    cache = DefaultResourceCache()
    identity = PDFontFactory.create_font(_type0_dict(descendant_ref), cache)
    remap = PDFontFactory.create_font(remapped, cache)
    assert isinstance(identity, PDType0Font)
    assert isinstance(remap, PDType0Font)
    assert identity.get_descendant_font() is remap.get_descendant_font()

    assert identity.get_width(1) == 100.0
    assert remap.get_width(1) == 500.0
    assert identity.get_width(1) == 100.0
    assert identity.code_to_cid(1) == 1
    assert remap.code_to_cid(1) == 5
    assert identity.has_explicit_width(5)
    assert remap.has_explicit_width(1)
    assert not remap.has_explicit_width(2)
