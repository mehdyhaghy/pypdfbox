from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel import MissingResourceException, PDResources
from pypdfbox.pdmodel.graphics.color import PDCalRGB, PDDeviceGray, PDDeviceRGB
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState


def test_empty_resources_has_empty_name_lists() -> None:
    res = PDResources()
    assert res.get_xobject_names() == []
    assert res.get_font_names() == []
    assert res.get_color_space_names() == []
    assert res.get_pattern_names() == []
    assert res.get_shading_names() == []
    assert res.get_extgstate_names() == []
    assert res.get_property_list_names() == []


def test_get_cos_object_returns_underlying_dict() -> None:
    cos = COSDictionary()
    res = PDResources(cos)
    assert res.get_cos_object() is cos


def test_add_xobject_assigns_im0_im1() -> None:
    res = PDResources()
    s1 = COSStream()
    s2 = COSStream()
    name1 = res.add(COSName.get_pdf_name("XObject"), s1)
    name2 = res.add(COSName.get_pdf_name("XObject"), s2)
    assert name1.get_name() == "Im0"
    assert name2.get_name() == "Im1"
    assert sorted(n.get_name() for n in res.get_xobject_names()) == ["Im0", "Im1"]


def test_add_form_xobject_uses_form_prefix() -> None:
    # A Form XObject is a COSDictionary; PDResources.add should pick the
    # "Form" prefix instead of "Im".
    res = PDResources()
    form = COSDictionary()
    form.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    name = res.add(COSName.get_pdf_name("XObject"), form)
    assert name.get_name() == "Form0"


def test_add_font_assigns_f0() -> None:
    res = PDResources()
    font = COSDictionary()
    font.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    name = res.add(COSName.get_pdf_name("Font"), font)
    assert name.get_name() == "F0"
    assert [n.get_name() for n in res.get_font_names()] == ["F0"]


def test_get_xobject_resolves_indirect_ref() -> None:
    res = PDResources()
    s = COSStream()
    name = res.add(COSName.get_pdf_name("XObject"), s)
    assert res.get_xobject(name) is s


def test_get_font_returns_direct_dictionary() -> None:
    res = PDResources()
    font = COSDictionary()
    font.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    name = res.add(COSName.get_pdf_name("Font"), font)
    assert res.get_font(name) is font


def test_get_xobject_missing_returns_none() -> None:
    res = PDResources()
    assert res.get_xobject(COSName.get_pdf_name("NoSuchKey")) is None


def test_typed_accessors_return_none_when_missing() -> None:
    res = PDResources()
    # get_color_space follows upstream PDFBox: an unresolvable non-device
    # name raises MissingResourceException ("Missing color space: ...")
    # rather than returning None.
    with pytest.raises(MissingResourceException, match="Missing color space: CS0"):
        res.get_color_space(COSName.get_pdf_name("CS0"))
    assert res.get_pattern(COSName.get_pdf_name("P0")) is None
    assert res.get_shading(COSName.get_pdf_name("Sh0")) is None
    assert res.get_ext_gstate(COSName.get_pdf_name("GS0")) is None
    assert res.get_property_list(COSName.get_pdf_name("MC0")) is None


def test_put_places_value() -> None:
    res = PDResources()
    font = COSDictionary()
    res.put(COSName.get_pdf_name("Font"), COSName.get_pdf_name("MyFont"), font)
    assert res.get_font(COSName.get_pdf_name("MyFont")) is font


def test_get_x_object_dispatches_by_subtype() -> None:
    res = PDResources()
    form = COSStream()
    form.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    image = COSStream()
    image.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]

    form_name = res.add(COSName.get_pdf_name("XObject"), form)
    image_name = res.add(COSName.get_pdf_name("XObject"), image)

    assert isinstance(res.get_x_object(form_name), PDFormXObject)
    assert isinstance(res.get_x_object(image_name), PDImageXObject)


def test_add_x_object_uses_typed_prefixes() -> None:
    res = PDResources()
    form_name = res.add_x_object(PDFormXObject(COSStream()))
    image_name = res.add_x_object(PDImageXObject(COSStream()))

    assert form_name.get_name() == "Form0"
    assert image_name.get_name() == "Im0"


def test_add_x_object_accepts_custom_prefix() -> None:
    res = PDResources()

    name = res.add_x_object(PDImageXObject(COSStream()), "Logo")

    assert name.get_name() == "Logo0"
    assert [n.get_name() for n in res.get_xobject_names()] == ["Logo0"]


def test_add_x_object_reuses_existing_cos_object() -> None:
    res = PDResources()
    image = PDImageXObject(COSStream())

    first = res.add_x_object(image, "Logo")
    second = res.add_x_object(image, "Other")

    assert second == first
    assert [n.get_name() for n in res.get_xobject_names()] == ["Logo0"]


def test_add_x_object_reuses_existing_indirect_cos_object() -> None:
    res = PDResources()
    image = PDImageXObject(COSStream())
    existing_name = COSName.get_pdf_name("ImExisting")
    xobjects = COSDictionary()
    xobjects.set_item(existing_name, COSObject(7, 0, resolved=image.get_cos_object()))
    res.get_cos_object().set_item(COSName.get_pdf_name("XObject"), xobjects)

    added_name = res.add_x_object(image, "Other")

    assert added_name == existing_name
    assert [n.get_name() for n in res.get_xobject_names()] == ["ImExisting"]


def test_upstream_name_aliases_return_cos_names() -> None:
    res = PDResources()
    image = COSStream()
    image.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    res.add(COSName.get_pdf_name("XObject"), image)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        COSDictionary(),
    )
    res.put(
        COSName.get_pdf_name("Properties"),
        COSName.get_pdf_name("Prop0"),
        COSDictionary(),
    )

    assert [name.get_name() for name in res.get_x_object_names()] == ["Im0"]
    assert [name.get_name() for name in res.get_ext_g_state_names()] == ["GS0"]
    assert [name.get_name() for name in res.get_properties_names()] == ["Prop0"]


def test_get_names_returns_keys_for_arbitrary_category() -> None:
    """Upstream ``getNames(COSName)`` (private) is exposed as
    ``get_names`` and must dispatch to the right sub-dictionary."""
    res = PDResources()
    entries = [
        ("XObject", "Im0", COSStream()),
        ("Font", "F0", COSDictionary()),
        ("ColorSpace", "CS0", COSName.get_pdf_name("DeviceRGB")),
        ("Pattern", "P0", COSDictionary()),
        ("Shading", "Sh0", COSDictionary()),
        ("ExtGState", "GS0", COSDictionary()),
        ("Properties", "Prop0", COSDictionary()),
    ]
    for category, name, value in entries:
        res.put(COSName.get_pdf_name(category), COSName.get_pdf_name(name), value)

    assert [n.get_name() for n in res.get_names(PDResources.XOBJECT)] == ["Im0"]
    assert [n.get_name() for n in res.get_names(PDResources.FONT)] == ["F0"]
    assert [n.get_name() for n in res.get_names(PDResources.COLOR_SPACE)] == ["CS0"]
    assert [n.get_name() for n in res.get_names(PDResources.PATTERN)] == ["P0"]
    assert [n.get_name() for n in res.get_names(PDResources.SHADING)] == ["Sh0"]
    assert [n.get_name() for n in res.get_names(PDResources.EXT_G_STATE)] == ["GS0"]
    assert [n.get_name() for n in res.get_names(PDResources.PROPERTIES)] == ["Prop0"]


def test_get_names_missing_category_returns_empty_list() -> None:
    """``get_names`` on an empty resources should return ``[]`` rather than
    raising, mirroring upstream's ``Collections.emptySet()`` fallback."""
    res = PDResources()
    assert res.get_names(PDResources.XOBJECT) == []
    assert res.get_names(COSName.get_pdf_name("Pattern")) == []


def test_get_resource_cache_returns_constructor_cache() -> None:
    cache = object()
    res = PDResources(resource_cache=cache)  # type: ignore[arg-type]
    assert res.get_resource_cache() is cache


def test_proc_set_round_trips_as_cos_names() -> None:
    res = PDResources()

    res.set_proc_set(["PDF", COSName.get_pdf_name("Text")])

    assert [name.get_name() for name in res.get_proc_set()] == ["PDF", "Text"]
    raw = res.get_cos_object().get_dictionary_object(COSName.get_pdf_name("ProcSet"))
    assert isinstance(raw, COSArray)
    assert raw.to_cos_name_string_list() == ["PDF", "Text"]


def test_proc_set_missing_and_none_are_empty() -> None:
    res = PDResources()
    assert res.get_proc_set() == []

    res.set_proc_set(["PDF"])
    res.set_proc_set(None)

    assert res.get_proc_set() == []
    assert not res.get_cos_object().contains_key(COSName.get_pdf_name("ProcSet"))


def test_get_proc_set_ignores_non_name_entries() -> None:
    res = PDResources()
    proc_set = COSArray(
        [
            COSName.get_pdf_name("PDF"),
            COSInteger.get(7),
            COSName.get_pdf_name("ImageB"),
        ]
    )
    res.get_cos_object().set_item(COSName.get_pdf_name("ProcSet"), proc_set)

    assert [name.get_name() for name in res.get_proc_set()] == ["PDF", "ImageB"]


def test_has_color_space_checks_entry_presence() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("CS0")
    assert not res.has_color_space(name)
    res.put(COSName.get_pdf_name("ColorSpace"), name, COSName.get_pdf_name("DeviceRGB"))
    assert res.has_color_space(name)


def test_is_image_x_object_checks_subtype_without_wrapping() -> None:
    res = PDResources()
    image = COSStream()
    image.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    form = COSStream()
    form.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]

    image_name = res.add(COSName.get_pdf_name("XObject"), image)
    form_name = res.add(COSName.get_pdf_name("XObject"), form)

    assert res.is_image_x_object(image_name)
    assert not res.is_image_x_object(form_name)
    assert not res.is_image_x_object(COSName.get_pdf_name("Missing"))


def test_get_properties_alias_returns_property_list() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("MC0")
    prop = COSDictionary()
    res.put(COSName.get_pdf_name("Properties"), name, prop)

    fetched = res.get_properties(name)

    assert isinstance(fetched, PDPropertyList)
    assert fetched.get_cos_object() is prop


def test_get_ext_g_state_alias_returns_ext_gstate() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("GS0")
    ext = COSDictionary()
    res.put(COSName.get_pdf_name("ExtGState"), name, ext)

    fetched = res.get_ext_g_state(name)

    assert isinstance(fetched, PDExtendedGraphicsState)
    assert fetched.get_cos_object() is ext


def test_typed_add_reuses_existing_cos_object() -> None:
    res = PDResources()
    ext = PDExtendedGraphicsState()

    first = res.add(ext)
    second = res.add(ext)

    assert first == second
    assert [name.get_name() for name in res.get_extgstate_names()] == ["gs0"]


def test_typed_add_xobject_uses_upstream_prefixes() -> None:
    res = PDResources()

    form_name = res.add(PDFormXObject(COSStream()))
    image_name = res.add(PDImageXObject(COSStream()))

    assert form_name.get_name() == "Form0"
    assert image_name.get_name() == "Im0"


def test_typed_put_infers_category() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("CS0")

    res.put(name, PDDeviceRGB.INSTANCE)

    assert res.has_color_space(name)
    assert res.get_color_space(name) is PDDeviceRGB.INSTANCE


def test_get_color_space_device_name_falls_back_to_builtin_singleton() -> None:
    res = PDResources()

    assert res.get_color_space(COSName.get_pdf_name("DeviceRGB")) is PDDeviceRGB.INSTANCE
    assert res.get_color_space(COSName.get_pdf_name("DeviceGray")) is PDDeviceGray.INSTANCE


def test_get_color_space_uses_default_device_override() -> None:
    res = PDResources()
    cal_rgb = PDCalRGB()
    res.put(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DefaultRGB"), cal_rgb)

    assert isinstance(res.get_color_space(COSName.get_pdf_name("DeviceRGB")), PDCalRGB)
    assert res.get_color_space(COSName.get_pdf_name("DeviceRGB"), was_default=True) is (
        PDDeviceRGB.INSTANCE
    )


def test_typed_add_optional_content_group_uses_oc_prefix() -> None:
    """Upstream ``PDResources.add(PDPropertyList)`` routes
    ``PDOptionalContentGroup`` instances to the ``"oc"`` prefix while keeping
    the bare ``PDPropertyList`` flavour on ``"Prop"``."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )

    res = PDResources()
    ocg = PDOptionalContentGroup("Layer 1")
    plain = PDPropertyList(COSDictionary())

    ocg_name = res.add(ocg)
    plain_name = res.add(plain)

    assert ocg_name.get_name() == "oc0"
    assert plain_name.get_name() == "Prop0"
    assert sorted(n.get_name() for n in res.get_property_list_names()) == [
        "Prop0",
        "oc0",
    ]


def test_class_constants_match_resource_dictionary_keys() -> None:
    """``PDResources.XOBJECT`` etc. should be the canonical interned
    ``COSName`` instances. Storing a value under those constants must be
    findable via the listing accessors and via the same constant on lookup."""
    assert PDResources.XOBJECT is COSName.get_pdf_name("XObject")
    assert PDResources.FONT is COSName.get_pdf_name("Font")
    assert PDResources.COLOR_SPACE is COSName.get_pdf_name("ColorSpace")
    assert PDResources.EXT_G_STATE is COSName.get_pdf_name("ExtGState")
    assert PDResources.SHADING is COSName.get_pdf_name("Shading")
    assert PDResources.PATTERN is COSName.get_pdf_name("Pattern")
    assert PDResources.PROPERTIES is COSName.get_pdf_name("Properties")
    assert PDResources.PROC_SET is COSName.get_pdf_name("ProcSet")


def test_put_accepts_class_constant_categories() -> None:
    """Round-trip via the new class-level COSName constants — they should be
    interchangeable with ``COSName.get_pdf_name(...)`` calls in user code."""
    res = PDResources()
    font = COSDictionary()
    res.put(PDResources.FONT, COSName.get_pdf_name("F0"), font)
    assert res.get_font(COSName.get_pdf_name("F0")) is font
    assert [n.get_name() for n in res.get_font_names()] == ["F0"]


def test_has_font_true_after_put() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("F0")
    assert not res.has_font(name)
    res.put(PDResources.FONT, name, COSDictionary())
    assert res.has_font(name)


def test_has_x_object_true_after_put() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("Im0")
    assert not res.has_x_object(name)
    res.put(PDResources.XOBJECT, name, COSStream())
    assert res.has_x_object(name)


def test_has_pattern_true_after_put() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("P0")
    assert not res.has_pattern(name)
    res.put(PDResources.PATTERN, name, COSDictionary())
    assert res.has_pattern(name)


def test_has_shading_true_after_put() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("Sh0")
    assert not res.has_shading(name)
    res.put(PDResources.SHADING, name, COSDictionary())
    assert res.has_shading(name)


def test_has_ext_g_state_true_after_put() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("GS0")
    assert not res.has_ext_g_state(name)
    assert not res.has_ext_gstate(name)
    res.put(PDResources.EXT_G_STATE, name, COSDictionary())
    assert res.has_ext_g_state(name)
    assert res.has_ext_gstate(name)


def test_has_property_list_true_after_put() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("MC0")
    assert not res.has_property_list(name)
    assert not res.has_properties(name)
    res.put(PDResources.PROPERTIES, name, COSDictionary())
    assert res.has_property_list(name)
    assert res.has_properties(name)


def test_has_predicates_with_missing_category_subdict_return_false() -> None:
    """When the category sub-dictionary itself is absent (the default for an
    empty ``PDResources``), every ``has_*`` predicate must return ``False``
    rather than raising."""
    res = PDResources()
    name = COSName.get_pdf_name("Anything")
    assert not res.has_color_space(name)
    assert not res.has_font(name)
    assert not res.has_x_object(name)
    assert not res.has_pattern(name)
    assert not res.has_shading(name)
    assert not res.has_ext_g_state(name)
    assert not res.has_property_list(name)


def test_has_predicates_ignore_unrelated_categories() -> None:
    """Storing a font under ``/Font`` must not register as a hit under any
    other category — the predicates are scoped to their sub-dictionary."""
    res = PDResources()
    name = COSName.get_pdf_name("F0")
    res.put(PDResources.FONT, name, COSDictionary())
    assert res.has_font(name)
    assert not res.has_color_space(name)
    assert not res.has_x_object(name)
    assert not res.has_pattern(name)
    assert not res.has_shading(name)
    assert not res.has_ext_g_state(name)
    assert not res.has_property_list(name)


def test_is_form_x_object_true_for_form_entry() -> None:
    res = PDResources()
    form = COSStream()
    form.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    image = COSStream()
    image.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]

    form_name = res.add(PDResources.XOBJECT, form)
    image_name = res.add(PDResources.XOBJECT, image)

    assert res.is_form_x_object(form_name)
    assert not res.is_form_x_object(image_name)
    assert not res.is_form_x_object(COSName.get_pdf_name("Missing"))


def test_is_form_x_object_resolves_indirect_reference() -> None:
    """Indirect /XObject entries should still report Form/Image correctly."""
    res = PDResources()
    form = COSStream()
    form.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    name = COSName.get_pdf_name("Form0")
    xobjects = COSDictionary()
    xobjects.set_item(name, COSObject(11, 0, resolved=form))
    res.get_cos_object().set_item(PDResources.XOBJECT, xobjects)

    assert res.is_form_x_object(name)
    assert not res.is_image_x_object(name)


def test_is_image_x_object_resolves_indirect_reference() -> None:
    """Symmetric to ``test_is_form_x_object_resolves_indirect_reference`` —
    the existing helper must also see through ``COSObject`` indirection."""
    res = PDResources()
    image = COSStream()
    image.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    name = COSName.get_pdf_name("Im0")
    xobjects = COSDictionary()
    xobjects.set_item(name, COSObject(12, 0, resolved=image))
    res.get_cos_object().set_item(PDResources.XOBJECT, xobjects)

    assert res.is_image_x_object(name)
    assert not res.is_form_x_object(name)


def test_class_constants_drive_listing_accessors() -> None:
    """The class constants and the listing accessors must agree on which
    sub-dictionary they refer to — a regression here would mean ``add`` and
    ``get_*_names`` could disagree on the storage location."""
    res = PDResources()
    res.put(PDResources.SHADING, COSName.get_pdf_name("Sh0"), COSDictionary())
    res.put(PDResources.PATTERN, COSName.get_pdf_name("P0"), COSDictionary())

    assert [n.get_name() for n in res.get_shading_names()] == ["Sh0"]
    assert [n.get_name() for n in res.get_pattern_names()] == ["P0"]
    # Sanity: the sub-dictionaries live where the constants point.
    assert res.get_cos_object().contains_key(PDResources.SHADING)
    assert res.get_cos_object().contains_key(PDResources.PATTERN)
