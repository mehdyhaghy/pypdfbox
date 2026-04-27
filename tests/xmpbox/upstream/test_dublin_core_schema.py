"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/DublinCoreTest.java

The upstream test is parametric (``initializeParameters`` enumerates each
``(field, type, cardinality)`` triple and feeds them into ``SchemaTester``).
This port lifts the same parameter table and exercises the equivalent
behaviour on :class:`DublinCoreSchema`:

* ``test_initialized_to_null`` — every property starts ``None``.
* ``test_setting_value`` — string-form setter writes round-trip via the
  string-form getter.
* ``test_setting_value_in_array`` — bag/seq/lang-alt setters accumulate.
* ``test_property_setter_simple`` — typed setter (``setXxxProperty``) with
  a freshly constructed wrapper round-trips via the typed getter.
* ``test_property_setter_in_array`` — typed setter for array/lang-alt
  properties round-trips via the typed getter.

Upstream's ``Locale`` type maps to Python ``str`` in this port (no
typed Locale wrapper); the ``language`` field is therefore exercised as a
``Bag<Text>``. ``ProperName`` is a ``TextType`` subclass so the bag/seq
fields backed by ``ProperName`` accept either wrapper.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DateType,
    DublinCoreSchema,
    LangAlt,
    MIMEType,
    ProperNameType,
    TextType,
    XMPMetadata,
)


# ---------------------------------------------------------------------------
# Parameter table — direct lift of upstream ``initializeParameters``.
# ``cardinality_token`` matches upstream ``Cardinality`` ("Simple"/"Bag"/...).
# ``type_token`` is the upstream ``Types`` enum tag, used to pick the typed
# wrapper to construct in the property-setter tests.
# ---------------------------------------------------------------------------

_PARAMS = [
    ("contributor", "ProperName", "Bag"),
    ("coverage", "Text", "Simple"),
    ("creator", "ProperName", "Seq"),
    ("date", "Date", "Seq"),
    ("format", "MIMEType", "Simple"),
    ("identifier", "Text", "Simple"),
    ("language", "Text", "Bag"),
    ("publisher", "ProperName", "Bag"),
    ("relation", "Text", "Bag"),
    ("source", "Text", "Simple"),
    ("subject", "Text", "Bag"),
    ("type", "Text", "Bag"),
]


def _sample_value(type_token: str) -> Any:
    if type_token == "Date":
        return datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    return "sample-value"


def _alt_sample_value(type_token: str) -> Any:
    if type_token == "Date":
        return datetime(2030, 7, 8, 9, 10, 11, tzinfo=UTC)
    return "alt-value"


def _stringify(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _typed_simple_factory(type_token: str):
    if type_token == "MIMEType":
        return MIMEType
    if type_token == "ProperName":
        return ProperNameType
    if type_token == "Date":
        return DateType
    return TextType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> DublinCoreSchema:
    return DublinCoreSchema(metadata)


def _typed_getter_for(field: str) -> str:
    """Map upstream local name to the schema's typed getter method."""
    return {
        "contributor": "get_contributors_property",
        "coverage": "get_coverage_property",
        "creator": "get_creators_property",
        "date": "get_dates_property",
        "format": "get_format_property",
        "identifier": "get_identifier_property",
        "language": "get_languages_property",
        "publisher": "get_publishers_property",
        "relation": "get_relations_property",
        "source": "get_source_property",
        "subject": "get_subjects_property",
        "type": "get_types_property",
    }[field]


def _typed_setter_for(field: str) -> str:
    return {
        "contributor": "set_contributors_property",
        "coverage": "set_coverage_property",
        "creator": "set_creators_property",
        "date": "set_dates_property",
        "format": "set_format_property",
        "identifier": "set_identifier_property",
        "language": "set_languages_property",
        "publisher": "set_publishers_property",
        "relation": "set_relations_property",
        "source": "set_source_property",
        "subject": "set_subjects_property",
        "type": "set_types_property",
    }[field]


def _string_getter_for(field: str) -> str:
    """String-form getter that returns the raw stored value(s)."""
    return {
        "contributor": "get_contributors",
        "coverage": "get_coverage",
        "creator": "get_creators",
        "date": "get_dates",
        "format": "get_format",
        "identifier": "get_identifier",
        "language": "get_languages",
        "publisher": "get_publishers",
        "relation": "get_relations",
        "source": "get_source",
        "subject": "get_subjects",
        "type": "get_types",
    }[field]


# ---------------------------------------------------------------------------
# initializedToNull — every property starts None / empty.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("field", "_type_token", "_card"), _PARAMS)
def test_initialized_to_null(
    schema: DublinCoreSchema, field: str, _type_token: str, _card: str
) -> None:
    typed_getter = getattr(schema, _typed_getter_for(field))
    string_getter = getattr(schema, _string_getter_for(field))
    assert typed_getter() is None
    assert string_getter() is None


# ---------------------------------------------------------------------------
# settingValue — string-form scalar writes round-trip through string-form get.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("field", "type_token", "card"), _PARAMS)
def test_setting_value(
    schema: DublinCoreSchema, field: str, type_token: str, card: str
) -> None:
    value = _sample_value(type_token)
    if card == "Simple":
        if type_token == "MIMEType":
            schema.set_format(_stringify(value))
        elif field == "coverage":
            schema.set_coverage(_stringify(value))
        elif field == "identifier":
            schema.set_identifier(_stringify(value))
        elif field == "source":
            schema.set_source(_stringify(value))
        else:
            schema.set_text_property_value(field, _stringify(value))
        assert getattr(schema, _string_getter_for(field))() == _stringify(value)
    elif card == "Bag":
        schema.add_qualified_bag_value(field, _stringify(value))
        assert getattr(schema, _string_getter_for(field))() == [_stringify(value)]
    elif card == "Seq":
        if type_token == "Date":
            schema.add_date(value)
            assert getattr(schema, _string_getter_for(field))() == [value]
        else:
            schema.add_unqualified_sequence_value(field, _stringify(value))
            assert getattr(schema, _string_getter_for(field))() == [
                _stringify(value)
            ]


# ---------------------------------------------------------------------------
# settingValueInArray — multi-value bag/seq writes preserve order/contents.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "type_token", "card"),
    [(f, t, c) for (f, t, c) in _PARAMS if c in ("Bag", "Seq")],
)
def test_setting_value_in_array(
    schema: DublinCoreSchema, field: str, type_token: str, card: str
) -> None:
    first = _sample_value(type_token)
    second = _alt_sample_value(type_token)
    if card == "Bag":
        schema.add_qualified_bag_value(field, _stringify(first))
        schema.add_qualified_bag_value(field, _stringify(second))
        assert getattr(schema, _string_getter_for(field))() == [
            _stringify(first),
            _stringify(second),
        ]
    elif card == "Seq":
        if type_token == "Date":
            schema.add_date(first)
            schema.add_date(second)
            assert getattr(schema, _string_getter_for(field))() == [first, second]
        else:
            schema.add_unqualified_sequence_value(field, _stringify(first))
            schema.add_unqualified_sequence_value(field, _stringify(second))
            assert getattr(schema, _string_getter_for(field))() == [
                _stringify(first),
                _stringify(second),
            ]


# ---------------------------------------------------------------------------
# propertySetterSimple — typed setter on simple TextType-shaped fields.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "type_token", "_card"),
    [(f, t, c) for (f, t, c) in _PARAMS if c == "Simple"],
)
def test_property_setter_simple(
    metadata: XMPMetadata,
    schema: DublinCoreSchema,
    field: str,
    type_token: str,
    _card: str,
) -> None:
    cls = _typed_simple_factory(type_token)
    value = _sample_value(type_token)
    prop = cls(
        metadata,
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.PREFERRED_PREFIX,
        field,
        value,
    )
    getattr(schema, _typed_setter_for(field))(prop)
    fetched = getattr(schema, _typed_getter_for(field))()
    assert fetched is not None
    if isinstance(fetched, TextType):
        assert fetched.get_string_value() == _stringify(value)
    else:  # MIMEType, etc — also a TextType subclass
        assert fetched.get_string_value() == _stringify(value)


# ---------------------------------------------------------------------------
# propertySetterInArray — typed setter on Bag / Seq array fields.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "type_token", "card"),
    [(f, t, c) for (f, t, c) in _PARAMS if c in ("Bag", "Seq")],
)
def test_property_setter_in_array(
    metadata: XMPMetadata,
    schema: DublinCoreSchema,
    field: str,
    type_token: str,
    card: str,
) -> None:
    cardinality = Cardinality.Bag if card == "Bag" else Cardinality.Seq
    array = ArrayProperty(
        metadata,
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.PREFERRED_PREFIX,
        field,
        cardinality,
    )
    cls = _typed_simple_factory(type_token)
    value = _sample_value(type_token)
    array.add_property(
        cls(
            metadata,
            DublinCoreSchema.NAMESPACE,
            DublinCoreSchema.PREFERRED_PREFIX,
            field,
            value,
        )
    )
    other = _alt_sample_value(type_token)
    array.add_property(
        cls(
            metadata,
            DublinCoreSchema.NAMESPACE,
            DublinCoreSchema.PREFERRED_PREFIX,
            field,
            other,
        )
    )
    getattr(schema, _typed_setter_for(field))(array)
    fetched = getattr(schema, _typed_getter_for(field))()
    assert isinstance(fetched, ArrayProperty)
    assert fetched.get_array_type() is cardinality
    children = fetched.get_all_properties()
    assert len(children) == 2
    serialized = [c.get_string_value() for c in children]
    assert serialized == [_stringify(value), _stringify(other)]


# ---------------------------------------------------------------------------
# LangAlt-typed properties (title / description / rights) — upstream
# ``DublinCoreTest`` exercises these through the LangAlt setters above by
# virtue of the ``Simple`` cardinality on a ``LangAlt`` type. Cover them
# explicitly here because the helper above doesn't speak LangAlt.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("local_name", "typed_getter", "typed_setter"),
    [
        ("title", "get_title_property", "set_title_property"),
        ("description", "get_description_property", "set_description_property"),
        ("rights", "get_rights_property", "set_rights_property"),
    ],
)
def test_lang_alt_property_round_trip(
    metadata: XMPMetadata,
    schema: DublinCoreSchema,
    local_name: str,
    typed_getter: str,
    typed_setter: str,
) -> None:
    la = LangAlt(
        metadata,
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.PREFERRED_PREFIX,
        local_name,
    )
    la.set_language_value(None, "default-text")
    la.set_language_value("en", "english-text")
    getattr(schema, typed_setter)(la)
    fetched = getattr(schema, typed_getter)()
    assert isinstance(fetched, LangAlt)
    assert fetched.get_language_value(None) == "default-text"
    assert fetched.get_language_value("en") == "english-text"
    assert "x-default" in fetched.get_languages()
    assert "en" in fetched.get_languages()
