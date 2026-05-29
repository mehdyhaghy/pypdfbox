from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import MissingResourceException, PDResources


def test_malformed_category_entries_are_treated_as_absent() -> None:
    res = PDResources()
    key = COSName.get_pdf_name("R0")
    for category in (
        PDResources.XOBJECT,
        PDResources.FONT,
        PDResources.COLOR_SPACE,
        PDResources.EXT_G_STATE,
        PDResources.SHADING,
        PDResources.PATTERN,
        PDResources.PROPERTIES,
    ):
        res.get_cos_object().set_item(category, COSArray())

    assert res.get_xobject_names() == []
    assert res.get_font_names() == []
    assert res.get_color_space_names() == []
    assert res.get_extgstate_names() == []
    assert res.get_shading_names() == []
    assert res.get_pattern_names() == []
    assert res.get_property_list_names() == []
    assert not res.has_x_object(key)
    assert not res.has_font(key)
    assert not res.has_color_space(key)
    assert not res.has_ext_g_state(key)
    assert not res.has_shading(key)
    assert not res.has_pattern(key)
    assert not res.has_property_list(key)
    assert res.get_xobject(key) is None
    assert res.get_font(key) is None
    # A malformed (non-dict) /ColorSpace category leaves the entry
    # unresolvable, so get_color_space follows upstream PDFBox and raises
    # MissingResourceException for the bare non-device name.
    with pytest.raises(MissingResourceException, match="Missing color space: R0"):
        res.get_color_space(key)
    assert res.get_ext_gstate(key) is None
    assert res.get_shading(key) is None
    assert res.get_pattern(key) is None
    assert res.get_property_list(key) is None


def test_clear_helpers_remove_named_resource_entries() -> None:
    res = PDResources()
    entries = (
        (PDResources.XOBJECT, COSName.get_pdf_name("Im0"), COSStream(), res.clear_x_object),
        (PDResources.FONT, COSName.get_pdf_name("F0"), COSDictionary(), res.clear_font),
        (
            PDResources.COLOR_SPACE,
            COSName.get_pdf_name("CS0"),
            COSName.get_pdf_name("DeviceRGB"),
            res.clear_color_space,
        ),
        (
            PDResources.EXT_G_STATE,
            COSName.get_pdf_name("GS0"),
            COSDictionary(),
            res.clear_ext_g_state,
        ),
        (PDResources.SHADING, COSName.get_pdf_name("Sh0"), COSDictionary(), res.clear_shading),
        (PDResources.PATTERN, COSName.get_pdf_name("P0"), COSDictionary(), res.clear_pattern),
        (
            PDResources.PROPERTIES,
            COSName.get_pdf_name("Prop0"),
            COSDictionary(),
            res.clear_property_list,
        ),
    )
    for category, name, value, clear in entries:
        res.put(category, name, value)
        assert res._has(category, name)
        clear(name)
        assert not res._has(category, name)


def test_clear_aliases_remove_named_resource_entries() -> None:
    res = PDResources()
    image_name = COSName.get_pdf_name("Im0")
    ext_name = COSName.get_pdf_name("GS0")
    props_name = COSName.get_pdf_name("Prop0")
    res.put(PDResources.XOBJECT, image_name, COSStream())
    res.put(PDResources.EXT_G_STATE, ext_name, COSDictionary())
    res.put(PDResources.PROPERTIES, props_name, COSDictionary())

    res.clear_xobject(image_name)
    res.clear_ext_gstate(ext_name)
    res.clear_properties(props_name)

    assert not res.has_x_object(image_name)
    assert not res.has_ext_g_state(ext_name)
    assert not res.has_property_list(props_name)


def test_clear_helper_noops_when_category_is_malformed() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("F0")
    malformed = COSArray()
    res.get_cos_object().set_item(PDResources.FONT, malformed)

    res.clear_font(name)

    assert res.get_cos_object().get_dictionary_object(PDResources.FONT) is malformed


def test_proc_set_has_and_clear_helpers() -> None:
    res = PDResources()

    assert not res.has_proc_set()
    res.set_proc_set(["PDF", COSName.get_pdf_name("Text")])
    assert res.has_proc_set()
    assert [name.get_name() for name in res.get_proc_set()] == ["PDF", "Text"]

    res.clear_proc_set()

    assert not res.has_proc_set()
    assert res.get_proc_set() == []
    assert not res.get_cos_object().contains_key(PDResources.PROC_SET)


def test_proc_set_has_false_for_malformed_non_array() -> None:
    res = PDResources()
    res.get_cos_object().set_item(PDResources.PROC_SET, COSInteger.get(7))

    assert not res.has_proc_set()
    assert res.get_proc_set() == []


def test_typed_xobject_reports_malformed_non_stream_entry() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("BadX")
    res.put(PDResources.XOBJECT, name, COSDictionary())

    with pytest.raises(TypeError, match="/XObject entry /BadX is not a stream"):
        res.get_x_object(name)
