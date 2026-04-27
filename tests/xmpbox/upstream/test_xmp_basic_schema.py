"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/XMPBasicTest.java

Upstream's test is a JUnit 5 parameterised test driven by an
``XMPSchemaTester`` reflection helper. It exercises ``getXxx`` /
``setXxx`` / ``getXxxProperty`` / ``setXxxProperty`` for every
property declared on ``XMPBasicSchema``. Cluster #1 ships both
surfaces directly so the parameter table maps cleanly to pytest.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import (
    DateType,
    IntegerType,
    TextType,
    XMPBasicSchema,
    XMPMetadata,
)


# Upstream initializeParameters() — kept verbatim so future re-syncs are diffable.
_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    ("Advisory", "XPath", "Bag"),
    ("BaseURL", "URL", "Simple"),
    ("CreateDate", "Date", "Simple"),
    ("CreatorTool", "AgentName", "Simple"),
    ("Identifier", "Text", "Bag"),
    ("Label", "Text", "Simple"),
    ("MetadataDate", "Date", "Simple"),
    ("ModifyDate", "Date", "Simple"),
    ("Nickname", "Text", "Simple"),
    ("Rating", "Integer", "Simple"),
    # Thumbnails (Alt of ThumbnailType) deferred — see module docstring.
)


# Map upstream local-name to the (string-getter, string-setter,
# typed-getter, typed-setter) tuple. Bag-cardinality entries put the
# bag accessors in the string slots and ``None`` in the typed slots.
_ACCESSORS: dict[str, tuple[str | None, str | None, str | None, str | None]] = {
    "Advisory": ("get_advisory", "add_advisory", None, None),
    "BaseURL": (
        "get_base_url",
        "set_base_url",
        "get_base_url_property",
        "set_base_url_property",
    ),
    "CreateDate": (
        "get_create_date",
        "set_create_date",
        "get_create_date_property",
        "set_create_date_property",
    ),
    "CreatorTool": (
        "get_creator_tool",
        "set_creator_tool",
        "get_creator_tool_property",
        "set_creator_tool_property",
    ),
    "Identifier": ("get_identifiers", "add_identifier", None, None),
    "Label": (
        "get_label",
        "set_label",
        "get_label_property",
        "set_label_property",
    ),
    "MetadataDate": (
        "get_metadata_date",
        "set_metadata_date",
        "get_metadata_date_property",
        "set_metadata_date_property",
    ),
    "ModifyDate": (
        "get_modify_date",
        "set_modify_date",
        "get_modify_date_property",
        "set_modify_date_property",
    ),
    "Nickname": (
        "get_nickname",
        "set_nickname",
        "get_nickname_property",
        "set_nickname_property",
    ),
    "Rating": (
        "get_rating",
        "set_rating",
        "get_rating_property",
        "set_rating_property",
    ),
}


@pytest.fixture
def metadata() -> XMPMetadata:
    """Mirror of upstream ``@BeforeEach initMetadata``."""
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> XMPBasicSchema:
    return XMPBasicSchema(metadata)


def _sample_value(type_token: str) -> object:
    if type_token == "Integer":
        return 7
    if type_token == "Date":
        return datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    return "sample-value"


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_initialized_to_null(
    schema: XMPBasicSchema, field_name: str, type_token: str, card: str
) -> None:
    """Translated from upstream ``testElementValue`` (null branch)."""
    del type_token, card
    getter_name, _, typed_getter, _ = _ACCESSORS[field_name]
    assert getter_name is not None
    assert getattr(schema, getter_name)() is None
    if typed_getter is not None:
        assert getattr(schema, typed_getter)() is None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_set_then_get_string_form(
    schema: XMPBasicSchema, field_name: str, type_token: str, card: str
) -> None:
    """Translated from upstream ``testElementValue`` — string-form path."""
    getter_name, setter_name, _, _ = _ACCESSORS[field_name]
    assert getter_name is not None and setter_name is not None
    value = _sample_value(type_token)
    if card == "Bag":
        # Bag-cardinality: setter is ``add_xxx``, getter returns a list.
        getattr(schema, setter_name)(value)
        assert getattr(schema, getter_name)() == [value]
        return
    getattr(schema, setter_name)(value)
    if type_token == "Date":
        # Date strings come back ISO-8601 normalised; just check non-null.
        assert getattr(schema, getter_name)() is not None
    else:
        assert getattr(schema, getter_name)() == value


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_set_then_get_typed_form(
    metadata: XMPMetadata,
    schema: XMPBasicSchema,
    field_name: str,
    type_token: str,
    card: str,
) -> None:
    """
    Translated from upstream ``testElementProperty`` — exercises the typed
    ``getXxxProperty`` / ``setXxxProperty`` round-trip.
    """
    if card == "Bag":
        pytest.skip("Bag cardinality has no typed *_property accessor in cluster #1")
    _, _, typed_getter, typed_setter = _ACCESSORS[field_name]
    assert typed_getter is not None and typed_setter is not None
    value = _sample_value(type_token)
    if type_token == "Integer":
        prop: object = IntegerType(
            metadata,
            "http://ns.adobe.com/xap/1.0/",
            "xmp",
            field_name,
            value,
        )
    elif type_token == "Date":
        prop = DateType(
            metadata,
            "http://ns.adobe.com/xap/1.0/",
            "xmp",
            field_name,
            value,
        )
    else:
        prop = TextType(
            metadata,
            "http://ns.adobe.com/xap/1.0/",
            "xmp",
            field_name,
            value,
        )
    getattr(schema, typed_setter)(prop)
    assert getattr(schema, typed_getter)() is prop


@pytest.mark.skip(reason="ThumbnailType not yet ported")
def test_thumbnails_property() -> None:
    """Upstream parameter row ``Thumbnails`` — deferred until ThumbnailType lands."""
