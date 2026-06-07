from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern
from pypdfbox.pdmodel.graphics.shading import PDShading
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


def test_wave537_create_key_seeds_from_size_not_lowest_gap() -> None:
    # Upstream createKey seeds the counter to keySet().size() and walks
    # upward — it does NOT fill the lowest free gap. A /Font dict holding
    # {F0, F2} (size 2) therefore yields F3, leaving F1 unused.
    res = PDResources()
    existing = COSDictionary()
    existing.set_item(COSName.get_pdf_name("F0"), COSDictionary())
    existing.set_item(COSName.get_pdf_name("F2"), COSDictionary())
    res.get_cos_object().set_item(PDResources.FONT, existing)

    name = res.add(PDResources.FONT, COSDictionary())

    assert name.get_name() == "F3"
    assert [n.get_name() for n in res.get_font_names()] == ["F0", "F2", "F3"]


def test_wave537_general_add_accepts_custom_prefix() -> None:
    res = PDResources()

    name = res.add(PDResources.COLOR_SPACE, COSName.get_pdf_name("DeviceRGB"), prefix="CS")

    assert name.get_name() == "CS1"
    assert res.get_color_space(name) is PDDeviceRGB.INSTANCE


def test_wave537_named_color_space_self_reference_stops_recursion() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("Loop")
    res.put(PDResources.COLOR_SPACE, name, name)

    assert res.get_color_space(name) is None


def test_wave537_typed_resource_cache_is_used_before_wrapping() -> None:
    cache = DefaultResourceCache()
    res = PDResources(resource_cache=cache)
    indirect_ext = COSObject(21, 0, resolved=COSDictionary())
    indirect_props = COSObject(22, 0, resolved=COSDictionary())
    ext_name = COSName.get_pdf_name("GS0")
    prop_name = COSName.get_pdf_name("Prop0")
    sentinel_ext = object()
    sentinel_props = object()

    extgstates = COSDictionary()
    extgstates.set_item(ext_name, indirect_ext)
    properties = COSDictionary()
    properties.set_item(prop_name, indirect_props)
    res.get_cos_object().set_item(PDResources.EXT_G_STATE, extgstates)
    res.get_cos_object().set_item(PDResources.PROPERTIES, properties)
    cache.put_ext_g_state(indirect_ext, sentinel_ext)  # type: ignore[arg-type]
    cache.put_property_list(indirect_props, sentinel_props)  # type: ignore[arg-type]

    assert res.get_ext_gstate(ext_name) is sentinel_ext
    assert res.get_property_list(prop_name) is sentinel_props


def test_wave537_pattern_and_shading_string_names_use_cache_and_validate() -> None:
    cache = DefaultResourceCache()
    res = PDResources(resource_cache=cache)
    pattern_dict = COSDictionary()
    pattern_dict.set_int(COSName.get_pdf_name("PatternType"), PDAbstractPattern.TYPE_TILING_PATTERN)
    shading_dict = COSDictionary()
    shading_dict.set_int(COSName.get_pdf_name("ShadingType"), PDShading.SHADING_TYPE2)
    pattern_ref = COSObject(31, 0, resolved=pattern_dict)
    shading_ref = COSObject(32, 0, resolved=shading_dict)
    pattern_sentinel = object()
    shading_sentinel = object()

    patterns = COSDictionary()
    patterns.set_item(COSName.get_pdf_name("P0"), pattern_ref)
    shadings = COSDictionary()
    shadings.set_item(COSName.get_pdf_name("Sh0"), shading_ref)
    res.get_cos_object().set_item(PDResources.PATTERN, patterns)
    res.get_cos_object().set_item(PDResources.SHADING, shadings)
    cache.put_pattern(pattern_ref, pattern_sentinel)  # type: ignore[arg-type]
    cache.put_shading(shading_ref, shading_sentinel)  # type: ignore[arg-type]

    assert res.get_pattern("P0") is pattern_sentinel
    assert res.get_shading("Sh0") is shading_sentinel


def test_wave537_malformed_typed_resources_return_none() -> None:
    res = PDResources()
    res.put(PDResources.PATTERN, COSName.get_pdf_name("P0"), COSName.get_pdf_name("Bad"))
    res.put(PDResources.SHADING, COSName.get_pdf_name("Sh0"), COSName.get_pdf_name("Bad"))
    res.put(PDResources.EXT_G_STATE, COSName.get_pdf_name("GS0"), COSName.get_pdf_name("Bad"))
    res.put(PDResources.PROPERTIES, COSName.get_pdf_name("Prop0"), COSName.get_pdf_name("Bad"))

    assert res.get_pattern("P0") is None
    assert res.get_shading("Sh0") is None
    assert res.get_ext_gstate(COSName.get_pdf_name("GS0")) is None
    assert res.get_properties(COSName.get_pdf_name("Prop0")) is None


def test_wave537_unknown_typed_resource_cannot_infer_category() -> None:
    res = PDResources()

    with pytest.raises(TypeError, match="cannot infer PDResources category"):
        res.add(object())

    with pytest.raises(TypeError, match="cannot infer PDResources category"):
        res.put(COSName.get_pdf_name("R0"), object())


def test_wave537_raw_xobject_resolves_only_cosobject_entries() -> None:
    res = PDResources()
    stream = COSStream()
    name = COSName.get_pdf_name("Im0")
    xobjects = COSDictionary()
    xobjects.set_item(name, COSObject(41, 0, resolved=stream))
    res.get_cos_object().set_item(PDResources.XOBJECT, xobjects)

    assert res.get_xobject(name) is stream
