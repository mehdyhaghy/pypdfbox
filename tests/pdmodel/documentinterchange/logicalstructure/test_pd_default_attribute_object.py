from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDDefaultAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
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


# ---------- get_attribute_value default-value semantics ----------


def test_get_attribute_value_default_ignored_when_value_present() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_attribute("Width", COSInteger.get(10))
    sentinel = COSString("never")
    # Default value is only returned when the key is missing — present keys
    # always return the stored value.
    val = obj.get_attribute_value("Width", sentinel)
    assert isinstance(val, COSInteger)
    assert val.value == 10
    assert val is not sentinel


# ---------- is_specified ----------


def test_is_specified_true_after_set_attribute() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_attribute("Width", COSInteger.get(10))
    assert obj.is_specified("Width") is True


def test_is_specified_false_when_unset() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    assert obj.is_specified("Width") is False


def test_is_specified_false_for_owner_key() -> None:
    # /O is the owner marker, never an "attribute" — is_specified must skip it
    # to match get_attribute_names exclusion.
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    assert obj.is_specified("O") is False


# ---------- remove_attribute ----------


def test_remove_attribute_removes_present_key() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_attribute("Width", COSInteger.get(10))
    assert obj.is_specified("Width")
    obj.remove_attribute("Width")
    assert not obj.is_specified("Width")
    assert obj.get_attribute_value("Width") is None


def test_remove_attribute_missing_key_silent_no_op() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    snapshot = dict(obj.get_cos_object().entry_set())
    obj.remove_attribute("Nope")
    # No mutation, no exception.
    assert dict(obj.get_cos_object().entry_set()) == snapshot


def test_remove_attribute_owner_key_rejected() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    with pytest.raises(ValueError):
        obj.remove_attribute("O")
    # Owner intact after the failed call.
    assert obj.get_owner() == "Layout"


def test_remove_attribute_fires_revision_bump_when_bound() -> None:
    elem = PDStructureElement(structure_type="P")
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    obj.set_attribute("Width", COSInteger.get(10))
    elem.add_attribute(obj)
    elem.set_revision_number(4)

    obj.remove_attribute("Width")
    # The revision slot for this attribute object must reflect the
    # element's current revision number after a real mutation.
    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_revision_number_at(0) == 4


# ---------- __str__ upstream parity ----------


def test_str_matches_upstream_to_string_format() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("MyOwner")
    text = str(obj)
    # Upstream PDFBox toString() = "O=" + owner + ", attributes={...}"
    assert text.startswith("O=MyOwner")
    assert ", attributes={" in text
    assert text.endswith("}")


def test_str_renders_attributes_in_dict_order() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    obj.set_attribute("BlockAlign", COSName.get_pdf_name("Before"))
    obj.set_attribute("Placement", COSName.get_pdf_name("Block"))
    text = str(obj)
    # Both attrs present, /O is excluded, format mirrors Java toString.
    assert "BlockAlign=" in text
    assert "Placement=" in text
    assert "O=Layout" in text
    # Insertion order preserved (BlockAlign was set first).
    assert text.index("BlockAlign=") < text.index("Placement=")


def test_str_no_attributes_renders_empty_braces() -> None:
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    # Only /O present — attributes={} (empty inner segment).
    assert str(obj) == "O=Layout, attributes={}"


def test_str_uses_str_of_value_not_repr() -> None:
    # Upstream Java string concatenation calls toString() on the COSBase;
    # our Python __str__ must mirror that — i.e. no quoting of strings,
    # no leading/trailing single quotes that __repr__ would add.
    obj = PDDefaultAttributeObject()
    obj.set_owner("Layout")
    obj.set_attribute("Tag", COSString("Value"))
    text = str(obj)
    # str(COSString) renders without Python string quotes; repr() would
    # wrap in Python quote markers.
    assert "Tag='Value'" not in text
    assert "Tag=" in text


# ---------- default constructor (no /O) ----------


def test_default_constructor_owner_is_none() -> None:
    obj = PDDefaultAttributeObject()
    # Upstream PDDefaultAttributeObject() calls super() with no args, leaving
    # /O unset until set_owner is called. is_empty() should remain False
    # because the size==1 + owner!=None invariant is broken (size==0).
    assert obj.get_owner() is None
    assert obj.is_empty() is False
    assert obj.get_cos_object().size() == 0
