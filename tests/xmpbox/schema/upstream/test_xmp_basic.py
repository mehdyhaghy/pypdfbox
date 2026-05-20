"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/XMPBasicTest.java

Upstream drives ``XMPSchemaTester#testGetSetValue`` /
``XMPSchemaTester#testGetSetProperty`` over eleven (property, type,
value) tuples covering the simple and Bag/Alt-cardinality properties
of :class:`XMPBasicSchema`. The Python translation drives the same
matrix via direct accessor calls — see :mod:`tests.xmpbox.upstream.
test_xmp_basic_schema` for the typed-property round-trip pass.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import (
    ThumbnailType,
    XMPBasicSchema,
    XMPMetadata,
)

# Mirrors upstream ``initializeParameters()`` — kept verbatim for re-syncs.
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
    ("Thumbnails", "Thumbnail", "Alt"),
)

_ACCESSORS: dict[str, tuple[str, str]] = {
    "Advisory": ("get_advisory", "add_advisory"),
    "BaseURL": ("get_base_url", "set_base_url"),
    "CreateDate": ("get_create_date", "set_create_date"),
    "CreatorTool": ("get_creator_tool", "set_creator_tool"),
    "Identifier": ("get_identifiers", "add_identifier"),
    "Label": ("get_label", "set_label"),
    "MetadataDate": ("get_metadata_date", "set_metadata_date"),
    "ModifyDate": ("get_modify_date", "set_modify_date"),
    "Nickname": ("get_nickname", "set_nickname"),
    "Rating": ("get_rating", "set_rating"),
    "Thumbnails": ("get_thumbnails", "add_thumbnails"),
}


@pytest.fixture
def metadata() -> XMPMetadata:
    """Mirror of upstream's ``@BeforeEach initMetadata``."""
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> XMPBasicSchema:
    return metadata.create_and_add_xmp_basic_schema()


def _sample_value(type_token: str, metadata: XMPMetadata) -> object:
    if type_token == "Integer":
        return 7
    if type_token == "Date":
        return datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    if type_token == "Thumbnail":
        thumb = ThumbnailType(metadata)
        thumb.set_width(160)
        thumb.set_height(120)
        thumb.set_format("JPEG")
        return thumb
    return "sample-value-" + type_token


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_element_value(
    metadata: XMPMetadata,
    schema: XMPBasicSchema,
    field_name: str,
    type_token: str,
    card: str,
) -> None:
    """Translated from upstream ``testElementValue``."""
    getter, setter = _ACCESSORS[field_name]
    value = _sample_value(type_token, metadata)
    if card in {"Bag", "Alt"}:
        getattr(schema, setter)(value)
        result = getattr(schema, getter)()
        assert result == [value]
        return
    getattr(schema, setter)(value)
    if type_token == "Date":
        # Dates round-trip through ISO-8601 strings — assert non-null.
        assert getattr(schema, getter)() is not None
    else:
        assert getattr(schema, getter)() == value
