from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDUserAttributeObject,
    PDUserProperty,
)


def test_get_property_projects_absent_cos_name_and_raw_cos_values() -> None:
    obj = PDUserAttributeObject()

    none_value_entry = COSDictionary()
    none_value_entry.set_string("N", "missing")

    name_value_entry = COSDictionary()
    name_value_entry.set_string("N", "named")
    name_value_entry.set_item("V", COSName.get_pdf_name("Decorative"))

    raw_value = COSArray()
    raw_value.add(COSString("kept"))
    raw_value_entry = COSDictionary()
    raw_value_entry.set_string("N", "raw")
    raw_value_entry.set_item("V", raw_value)

    p_array = COSArray()
    p_array.add(COSString("ignored"))
    p_array.add(none_value_entry)
    p_array.add(name_value_entry)
    p_array.add(raw_value_entry)
    obj.get_cos_object().set_item("P", p_array)

    props = obj.get_property()

    assert props[0]["N"] == "missing"
    assert props[0]["V"] is None
    assert props[1]["N"] == "named"
    assert props[1]["V"] == "Decorative"
    assert props[2]["N"] == "raw"
    assert props[2]["V"] is raw_value


def test_set_owner_properties_accepts_existing_cos_values() -> None:
    obj = PDUserAttributeObject()
    value = COSInteger.get(7)

    obj.set_owner_properties([{"N": "cos", "V": value}])

    p_array = obj.get_cos_object().get_dictionary_object("P")
    assert isinstance(p_array, COSArray)
    entry = p_array.get_object(0)
    assert isinstance(entry, COSDictionary)
    assert entry.get_dictionary_object("V") is value
    assert obj.get_owner_properties() == [{"N": "cos", "V": 7, "F": None, "H": False}]


def test_remove_owner_property_skips_malformed_entries() -> None:
    obj = PDUserAttributeObject()
    p_array = COSArray()
    p_array.add(COSString("ignored"))
    obj.get_cos_object().set_item("P", p_array)
    obj.add_owner_property("target", "value")

    assert obj.remove_owner_property("target") is True
    assert obj.get_owner_properties() == []


def test_get_owner_user_properties_skips_malformed_entries() -> None:
    obj = PDUserAttributeObject()
    p_array = COSArray()
    p_array.add(COSString("ignored"))
    obj.get_cos_object().set_item("P", p_array)
    obj.add_owner_property("target", "value")

    props = obj.get_owner_user_properties()

    assert len(props) == 1
    assert props[0].get_name() == "target"


def test_add_user_property_reuses_existing_p_array() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("existing", 1)
    prop = PDUserProperty(obj)
    prop.set_name("typed")
    prop.set_value(COSString("value"))

    obj.add_user_property(prop)

    assert [entry["N"] for entry in obj.get_owner_properties()] == [
        "existing",
        "typed",
    ]


def test_base_user_property_changed_is_noop_and_repr_counts_properties() -> None:
    obj = PDUserAttributeObject()
    prop = PDUserProperty(obj)
    prop.set_name("tracked")

    obj.user_property_changed(prop)

    assert repr(obj) == "PDUserAttributeObject(O=UserProperties, properties=0)"
