from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AbstractStructuredType,
    ArrayProperty,
    Cardinality,
    DateType,
    TextType,
)


class _MyStruct(AbstractStructuredType):
    MYTEXT = "my-text"
    MYDATE = "my-date"

    _FIELD_TYPES = {
        MYTEXT: "Text",
        MYDATE: "Date",
    }

    def __init__(self, metadata: XMPMetadata, ns: str, prefix: str) -> None:
        super().__init__(metadata, ns, prefix, "structuredPN")


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def st(metadata: XMPMetadata) -> _MyStruct:
    return _MyStruct(metadata, "http://www.apache.org/test#", "test")


def test_namespace_and_prefix(st: _MyStruct) -> None:
    assert st.get_namespace() == "http://www.apache.org/test#"
    assert st.get_prefix() == "test"


def test_property_name(st: _MyStruct) -> None:
    assert st.get_property_name() == "structuredPN"


def test_non_existing_property_returns_none(st: _MyStruct) -> None:
    assert st.get_property("NOT_EXISTING") is None


def test_unset_property_returns_none(st: _MyStruct) -> None:
    assert st.get_property(_MyStruct.MYTEXT) is None


def test_add_simple_text_property(st: _MyStruct) -> None:
    st.add_simple_property(_MyStruct.MYTEXT, "my value")
    assert st.get_property_value_as_string(_MyStruct.MYTEXT) == "my value"
    assert st.get_property_value_as_string(_MyStruct.MYDATE) is None
    assert st.get_property(_MyStruct.MYTEXT) is not None


def test_add_simple_date_property(st: _MyStruct) -> None:
    when = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    st.add_simple_property(_MyStruct.MYDATE, when)
    assert st.get_date_property_as_calendar(_MyStruct.MYDATE) == when
    assert st.get_date_property_as_calendar(_MyStruct.MYTEXT) is None


def test_add_property_replaces_same_name(st: _MyStruct) -> None:
    st.add_simple_property(_MyStruct.MYTEXT, "first")
    st.add_simple_property(_MyStruct.MYTEXT, "second")
    assert st.get_property_value_as_string(_MyStruct.MYTEXT) == "second"
    assert len(st.get_all_properties()) == 1


def test_add_namespace_and_lookup(metadata: XMPMetadata) -> None:
    st = _MyStruct(metadata, "http://www.apache.org/test#", "test")
    st.add_namespace("http://example.com/", "ex")
    assert st.get_namespace_prefix("http://example.com/") == "ex"
    assert "http://example.com/" in st.get_all_namespaces_with_prefix()


def test_remove_property(st: _MyStruct) -> None:
    st.add_simple_property(_MyStruct.MYTEXT, "v")
    prop = st.get_property(_MyStruct.MYTEXT)
    assert prop is not None
    st.remove_property(prop)
    assert st.get_property(_MyStruct.MYTEXT) is None


def test_create_text_type(st: _MyStruct) -> None:
    text = st.create_text_type("foo", "bar")
    assert isinstance(text, TextType)
    assert text.get_string_value() == "bar"
    assert text.get_property_name() == "foo"
    assert text.get_namespace() == "http://www.apache.org/test#"


def test_create_array_property(st: _MyStruct) -> None:
    arr = st.create_array_property("things", Cardinality.Bag)
    assert isinstance(arr, ArrayProperty)
    assert arr.get_array_type() is Cardinality.Bag
    assert arr.get_property_name() == "things"


def test_first_equivalent_property_filters_by_type(st: _MyStruct) -> None:
    when = datetime(2024, 1, 2, tzinfo=UTC)
    st.add_simple_property(_MyStruct.MYDATE, when)
    found = st.get_first_equivalent_property(_MyStruct.MYDATE, DateType)
    assert isinstance(found, DateType)


def test_namespace_required_when_no_class_default(metadata: XMPMetadata) -> None:
    class _Bare(AbstractStructuredType):
        def __init__(self, m: XMPMetadata) -> None:
            super().__init__(m, None, None, None)

    with pytest.raises(ValueError):
        _Bare(metadata)


def test_structure_array_name_class_constant() -> None:
    # Upstream defines `protected static final String STRUCTURE_ARRAY_NAME = "li"`
    # on AbstractStructuredType itself; expose it as a class attribute so
    # downstream subclasses can reach it via the class.
    assert AbstractStructuredType.STRUCTURE_ARRAY_NAME == "li"


def test_structure_array_name_inherited_by_subclass(metadata: XMPMetadata) -> None:
    st = _MyStruct(metadata, "http://www.apache.org/test#", "test")
    assert type(st).STRUCTURE_ARRAY_NAME == "li"
    assert st.STRUCTURE_ARRAY_NAME == "li"
