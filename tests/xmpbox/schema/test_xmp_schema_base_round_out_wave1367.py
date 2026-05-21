"""Branch-coverage round-out (wave 1367) for ``XMPSchema`` base class.

Pins the shared LangAlt / Bag / Seq accessor branches across cardinality
classes:

* x-default sentinel + reorganization
* property removal that empties /Description (i.e. ``_properties`` key drop)
* generic ``get_property_as`` type-safety
* boolean vs integer disambiguation
* date Seq round-trip and removal
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from pypdfbox.xmpbox.xmp_schema import X_DEFAULT, XMPSchema


@pytest.fixture()
def schema() -> XMPSchema:
    return XMPSchema(
        XMPMetadata.create_xmp_metadata(),
        namespace_uri="http://example.org/test/",
        prefix="test",
    )


def test_set_unqualified_language_default_to_x_default(schema: XMPSchema) -> None:
    schema.set_unqualified_language_property_value("title", None, "Default")
    assert schema.get_unqualified_language_property_value("title") == "Default"
    assert schema.get_unqualified_language_property_value("title", X_DEFAULT) == "Default"


def test_lang_alt_reorganize_keeps_x_default_first(schema: XMPSchema) -> None:
    schema.set_unqualified_language_property_value("title", "fr", "Titre")
    schema.set_unqualified_language_property_value("title", "es", "Titulo")
    schema.set_unqualified_language_property_value("title", X_DEFAULT, "Default")
    langs = schema.get_unqualified_language_property_languages_value("title")
    assert langs is not None
    # x-default first, then the others in insertion order.
    assert langs[0] == X_DEFAULT


def test_lang_alt_value_none_removes_language(schema: XMPSchema) -> None:
    schema.set_unqualified_language_property_value("title", "fr", "Titre")
    schema.set_unqualified_language_property_value("title", X_DEFAULT, "Default")
    schema.set_unqualified_language_property_value("title", "fr", None)
    langs = schema.get_unqualified_language_property_languages_value("title")
    assert langs is not None
    assert "fr" not in langs


def test_lang_alt_remove_unqualified_language_value(schema: XMPSchema) -> None:
    schema.set_unqualified_language_property_value("rights", X_DEFAULT, "A")
    schema.set_unqualified_language_property_value("rights", "de", "B")
    schema.remove_unqualified_language_property_value("rights", "de")
    langs = schema.get_unqualified_language_property_languages_value("rights")
    assert langs is not None
    assert "de" not in langs


def test_remove_unqualified_bag_value_clears_all_matches(schema: XMPSchema) -> None:
    for value in ("a", "b", "a", "c", "a"):
        schema.add_qualified_bag_value("tags", value)
    schema.remove_unqualified_bag_value("tags", "a")
    assert schema.get_unqualified_bag_value_list("tags") == ["b", "c"]


def test_remove_unqualified_array_value_delegates(schema: XMPSchema) -> None:
    schema.add_unqualified_sequence_value("history", "x")
    schema.add_unqualified_sequence_value("history", "y")
    schema.remove_unqualified_array_value("history", "x")
    assert schema.get_unqualified_sequence_value_list("history") == ["y"]


def test_property_removal_drops_from_description(schema: XMPSchema) -> None:
    schema.set_text_property_value("name", "value")
    assert "name" in schema.get_all_properties()
    schema.remove_property("name")
    assert "name" not in schema.get_all_properties()


def test_set_text_property_value_none_removes(schema: XMPSchema) -> None:
    schema.set_text_property_value("name", "value")
    schema.set_text_property_value("name", None)
    assert schema.get_unqualified_text_property_value("name") is None


def test_get_property_as_type_safety(schema: XMPSchema) -> None:
    schema.set_text_property_value("name", "value")
    assert schema.get_property_as("name", str) == "value"
    # Wrong type request returns None.
    assert schema.get_property_as("name", list) is None
    assert schema.get_property_as("missing", str) is None


def test_get_property_as_distinguishes_bool_from_int(schema: XMPSchema) -> None:
    schema.set_boolean_property_value("flag", True)
    # Boolean retrieval works.
    assert schema.get_property_as("flag", bool) is True
    # Int retrieval is rejected even though bool subclasses int in Python.
    assert schema.get_property_as("flag", int) is None


def test_set_integer_rejects_bool(schema: XMPSchema) -> None:
    with pytest.raises(TypeError):
        schema.set_integer_property_value("count", True)


def test_set_date_rejects_non_datetime(schema: XMPSchema) -> None:
    with pytest.raises(TypeError):
        schema.set_date_property_value("when", "2024-01-01")  # type: ignore[arg-type]


def test_sequence_date_round_trip_and_remove(schema: XMPSchema) -> None:
    a = datetime(2024, 1, 1, tzinfo=UTC)
    b = datetime(2024, 6, 15, tzinfo=UTC)
    schema.add_unqualified_sequence_date_value("history", a)
    schema.add_unqualified_sequence_date_value("history", b)
    out = schema.get_unqualified_sequence_date_value_list("history")
    assert out == [a, b]
    schema.remove_unqualified_sequence_date_value("history", a)
    assert schema.get_unqualified_sequence_date_value_list("history") == [b]


def test_get_unqualified_text_falls_back_to_x_default_dict(
    schema: XMPSchema,
) -> None:
    schema.set_unqualified_language_property_value("title", X_DEFAULT, "Default")
    # Text getter on a LangAlt-stored value surfaces the x-default entry.
    assert schema.get_unqualified_text_property_value("title") == "Default"


def test_clear_drops_all_properties_and_typed_cache(schema: XMPSchema) -> None:
    schema.set_text_property_value("a", "1")
    schema.set_text_property_value("b", "2")
    schema.clear()
    assert schema.get_all_properties() == {}
