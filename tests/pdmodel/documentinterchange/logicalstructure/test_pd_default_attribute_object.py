from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDDefaultAttributeObject,
)


def test_default_constructor_creates_empty_dictionary() -> None:
    obj = PDDefaultAttributeObject()
    assert isinstance(obj.get_cos_object(), COSDictionary)
    assert obj.get_cos_object().size() == 0


def test_constructor_with_dictionary_uses_underlying() -> None:
    cos = COSDictionary()
    cos.set_name(COSName.get_pdf_name("O"), "MyOwner")
    obj = PDDefaultAttributeObject(cos)
    assert obj.get_cos_object() is cos
    assert obj.get_owner() == "MyOwner"


def test_inherits_from_pd_attribute_object() -> None:
    obj = PDDefaultAttributeObject()
    assert isinstance(obj, PDAttributeObject)


def test_get_attribute_names_excludes_owner() -> None:
    cos = COSDictionary()
    cos.set_name(COSName.get_pdf_name("O"), "Layout")
    cos.set_int(COSName.get_pdf_name("BlockAlign"), 0)
    cos.set_string(COSName.get_pdf_name("Placement"), "Block")
    obj = PDDefaultAttributeObject(cos)
    names = obj.get_attribute_names()
    assert "O" not in names
    assert set(names) == {"BlockAlign", "Placement"}


def test_get_attribute_names_empty_when_only_owner() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Foo")
    assert obj.get_attribute_names() == []


def test_get_attribute_value_returns_resolved_value() -> None:
    obj = PDDefaultAttributeObject()
    val = COSInteger.get(42)
    obj.get_cos_object().set_item(COSName.get_pdf_name("Width"), val)
    assert obj.get_attribute_value("Width") is val


def test_get_attribute_value_returns_default_when_missing() -> None:
    obj = PDDefaultAttributeObject()
    assert obj.get_attribute_value("Nope") is None
    sentinel = COSString("sentinel")
    assert obj.get_attribute_value("Nope", sentinel) is sentinel


def test_set_attribute_writes_value() -> None:
    obj = PDDefaultAttributeObject()
    val = COSString("hello")
    obj.set_attribute("Custom", val)
    assert obj.get_attribute_value("Custom") is val
    assert "Custom" in obj.get_attribute_names()


def test_set_attribute_overwrites_existing() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_attribute("X", COSInteger.get(1))
    obj.set_attribute("X", COSInteger.get(2))
    new_val = obj.get_attribute_value("X")
    assert isinstance(new_val, COSInteger)
    assert new_val.value == 2


def test_repr_includes_owner_and_attributes() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("MyOwner")
    obj.set_attribute("Foo", COSString("bar"))
    text = repr(obj)
    assert "MyOwner" in text
    assert "Foo" in text


def test_set_attribute_does_not_clobber_owner() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    obj.set_attribute("Placement", COSString("Block"))
    assert obj.get_owner() == "Layout"
    assert "O" not in obj.get_attribute_names()
