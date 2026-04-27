from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject


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
