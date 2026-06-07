from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject, COSStream
from pypdfbox.pdmodel import PDDocument, PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


def test_proc_set_presence_clear_and_invalid_entry_wave414() -> None:
    res = PDResources()

    assert not res.has_proc_set()
    res.set_proc_set(["PDF", COSName.get_pdf_name("Text")])
    assert res.has_proc_set()
    res.clear_proc_set()
    assert not res.has_proc_set()

    with pytest.raises(TypeError, match="COSName or str"):
        res.set_proc_set([COSInteger.get(1)])  # type: ignore[list-item]


def test_get_resource_cache_prefers_document_cache_wave414() -> None:
    doc = PDDocument()
    constructor_cache = DefaultResourceCache()
    document_cache = DefaultResourceCache()
    res = PDResources(resource_cache=constructor_cache, document=doc)

    doc.set_resource_cache(document_cache)

    assert res.get_resource_cache() is document_cache


def test_get_x_object_accepts_string_names_and_uses_cache_wave414() -> None:
    cache = DefaultResourceCache()
    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    indirect = COSObject(5, 0, resolved=image_stream)
    xobjects = COSDictionary()
    xobjects.set_item(COSName.get_pdf_name("Logo"), indirect)
    resources = COSDictionary()
    resources.set_item(PDResources.XOBJECT, xobjects)
    res = PDResources(resources, resource_cache=cache)

    first = res.get_x_object("Logo")
    second = res.get_x_object("Logo")

    assert isinstance(first, PDImageXObject)
    assert second is first


def test_get_x_object_rejects_malformed_and_unknown_subtype_wave414() -> None:
    res = PDResources()
    bad_name = COSName.get_pdf_name("Bad")
    unknown_name = COSName.get_pdf_name("Unknown")
    unknown = COSStream()
    unknown.set_name(COSName.SUBTYPE, "PostScript")  # type: ignore[attr-defined]

    res.put(PDResources.XOBJECT, bad_name, COSDictionary())
    res.put(PDResources.XOBJECT, unknown_name, unknown)

    with pytest.raises(TypeError, match="not a stream"):
        res.get_x_object(bad_name)
    with pytest.raises(OSError, match="Invalid XObject Subtype"):
        res.get_x_object(unknown_name)


def test_add_x_object_unknown_subclass_falls_back_to_subtype_wave414() -> None:
    class CustomXObject:
        def __init__(self, subtype: str) -> None:
            self.stream = COSStream()
            self.stream.set_name(COSName.SUBTYPE, subtype)  # type: ignore[attr-defined]

        def get_cos_object(self) -> COSStream:
            return self.stream

    res = PDResources()

    form_name = res.add_x_object(CustomXObject("Form"))  # type: ignore[arg-type]
    image_name = res.add_x_object(CustomXObject("Image"))  # type: ignore[arg-type]

    # Both land in /XObject; second add is seeded to size()==1 → index 2.
    assert form_name.get_name() == "Form1"
    assert image_name.get_name() == "Im2"


def test_get_font_returns_none_for_non_dictionary_entries_wave414() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("F0")

    res.put(PDResources.FONT, name, COSName.get_pdf_name("Helvetica"))

    assert res.get_font(name) is None


def test_clear_helpers_remove_entries_and_accept_string_names_wave414() -> None:
    res = PDResources()
    entries = [
        (PDResources.COLOR_SPACE, COSName.get_pdf_name("CS0"), COSName.get_pdf_name("DeviceRGB")),
        (PDResources.FONT, COSName.get_pdf_name("F0"), COSDictionary()),
        (PDResources.XOBJECT, COSName.get_pdf_name("Im0"), COSStream()),
        (PDResources.PATTERN, COSName.get_pdf_name("P0"), COSDictionary()),
        (PDResources.SHADING, COSName.get_pdf_name("Sh0"), COSDictionary()),
        (PDResources.EXT_G_STATE, COSName.get_pdf_name("GS0"), COSDictionary()),
        (PDResources.PROPERTIES, COSName.get_pdf_name("Prop0"), COSDictionary()),
    ]
    for category, name, value in entries:
        res.put(category, name, value)

    res.clear_color_space(COSName.get_pdf_name("CS0"))
    res.clear_font(COSName.get_pdf_name("F0"))
    res.clear_xobject(COSName.get_pdf_name("Im0"))
    res.clear_pattern("P0")
    res.clear_shading("Sh0")
    res.clear_ext_gstate(COSName.get_pdf_name("GS0"))
    res.clear_properties(COSName.get_pdf_name("Prop0"))

    assert not res.has_color_space(COSName.get_pdf_name("CS0"))
    assert not res.has_font(COSName.get_pdf_name("F0"))
    assert not res.has_x_object(COSName.get_pdf_name("Im0"))
    assert not res.has_pattern("P0")
    assert not res.has_shading("Sh0")
    assert not res.has_ext_gstate(COSName.get_pdf_name("GS0"))
    assert not res.has_properties(COSName.get_pdf_name("Prop0"))


def test_add_validates_category_value_and_infers_prefixes_wave414() -> None:
    res = PDResources()

    with pytest.raises(TypeError, match="explicit add category"):
        res.add("Font", COSDictionary())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unknown resource category"):
        res.add(COSName.get_pdf_name("Custom"), COSDictionary())

    assert res.add(PDResources.COLOR_SPACE, COSName.get_pdf_name("DeviceRGB")).get_name() == "cs1"
    assert res.add(PDResources.EXT_G_STATE, COSDictionary()).get_name() == "gs1"
    assert res.add(PDResources.SHADING, COSDictionary()).get_name() == "sh1"
    assert res.add(PDResources.PATTERN, COSDictionary()).get_name() == "p1"
    assert res.add(PDResources.PROPERTIES, COSDictionary()).get_name() == "Prop1"


def test_put_upstream_overload_validates_name_and_value_wave414() -> None:
    res = PDResources()

    with pytest.raises(TypeError, match="resource name must be COSName"):
        res.put("CS0", PDDeviceRGB.INSTANCE)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="not COS-backed"):
        res.put(PDResources.FONT, COSName.get_pdf_name("F0"), object())


def test_typed_ext_gstate_and_direct_xobject_paths_wave414() -> None:
    res = PDResources()
    ext_name = COSName.get_pdf_name("GS0")
    form_name = COSName.get_pdf_name("Form0")
    image_name = COSName.get_pdf_name("Im0")
    ext = PDExtendedGraphicsState()
    form = PDFormXObject(COSStream())
    image = PDImageXObject(COSStream())

    res.put(ext_name, ext)
    res.put(form_name, form)
    res.put(image_name, image)

    assert res.get_ext_gstate(ext_name).get_cos_object() is ext.get_cos_object()
    assert isinstance(res.get_x_object(form_name), PDFormXObject)
    assert isinstance(res.get_x_object(image_name), PDImageXObject)
