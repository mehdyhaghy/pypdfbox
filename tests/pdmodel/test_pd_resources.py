from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
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
    assert res.get_color_space(COSName.get_pdf_name("CS0")) is None
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


def test_get_resource_cache_returns_constructor_cache() -> None:
    cache = object()
    res = PDResources(resource_cache=cache)  # type: ignore[arg-type]
    assert res.get_resource_cache() is cache


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
