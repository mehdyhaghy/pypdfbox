"""
Ported from upstream
``xmpbox/src/test/java/org/apache/xmpbox/type/TestAbstractStructuredType.java``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import AbstractStructuredType

MY_NS = "http://www.apache.org/test#"
MY_PREFIX = "test"


class _MyStructuredType(AbstractStructuredType):
    MYTEXT = "my-text"
    MYDATE = "my-date"

    _FIELD_TYPES = {
        MYTEXT: "Text",
        MYDATE: "Date",
    }

    def __init__(self, metadata: XMPMetadata, ns: str, prefix: str) -> None:
        super().__init__(metadata, ns, prefix, "structuredPN")


@pytest.fixture
def st() -> _MyStructuredType:
    xmp = XMPMetadata.create_xmp_metadata()
    return _MyStructuredType(xmp, MY_NS, MY_PREFIX)


def test_validate(st: _MyStructuredType) -> None:
    assert st.get_namespace() == MY_NS
    assert st.get_prefix() == MY_PREFIX
    assert st.get_prefix() == MY_PREFIX


def test_non_existing_property(st: _MyStructuredType) -> None:
    assert st.get_property("NOT_EXISTING") is None


def test_not_valuated_property(st: _MyStructuredType) -> None:
    assert st.get_property(_MyStructuredType.MYTEXT) is None


def test_valuated_text_property(st: _MyStructuredType) -> None:
    s = "my value"
    st.add_simple_property(_MyStructuredType.MYTEXT, s)
    assert st.get_property_value_as_string(_MyStructuredType.MYTEXT) == s
    assert st.get_property_value_as_string(_MyStructuredType.MYDATE) is None
    assert st.get_property(_MyStructuredType.MYTEXT) is not None


def test_valuated_date_property(st: _MyStructuredType) -> None:
    c = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
    st.add_simple_property(_MyStructuredType.MYDATE, c)
    assert st.get_date_property_as_calendar(_MyStructuredType.MYDATE) == c
    assert st.get_date_property_as_calendar(_MyStructuredType.MYTEXT) is None
    assert st.get_property(_MyStructuredType.MYDATE) is not None
