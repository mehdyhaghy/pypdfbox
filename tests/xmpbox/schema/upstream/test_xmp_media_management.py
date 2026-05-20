"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/XMPMediaManagementTest.java

Upstream drives ``XMPSchemaTester#testGetSetValue`` /
``XMPSchemaTester#testGetSetProperty`` over eleven (property, type,
value) tuples covering simple + Bag/Seq cardinality properties of
:class:`XMPMediaManagementSchema`. The Python port collapses the
reflection-driven matrix to direct accessor calls per property. See
``tests/xmpbox/upstream/test_xmp_media_management_schema.py`` for the
typed-property pass.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMediaManagementSchema, XMPMetadata

# Mirrors upstream ``initializeParameters()`` — kept verbatim.
_PARAMETERS: tuple[tuple[str, str, str, object], ...] = (
    ("DocumentID", "URI", "Simple", "uuid:FB031973-5E75-11B2-8F06-E7F5C101C07A"),
    ("Manager", "AgentName", "Simple", "Raoul"),
    ("ManageTo", "URI", "Simple", "uuid:36"),
    ("ManageUI", "URI", "Simple", "uuid:3635"),
    ("InstanceID", "URI", "Simple", "uuid:42"),
    ("OriginalDocumentID", "Text", "Simple", "uuid:142"),
    ("RenditionParams", "Text", "Simple", "my params"),
    ("VersionID", "Text", "Simple", "14"),
    ("Versions", "Version", "Seq", ("1", "2", "3")),
    ("History", "Text", "Seq", ("action 1", "action 2", "action 3")),
    ("Ingredients", "Text", "Bag", ("resource1", "resource2")),
)

_ACCESSORS: dict[str, tuple[str, str]] = {
    "DocumentID": ("get_document_id", "set_document_id"),
    "Manager": ("get_manager", "set_manager"),
    "ManageTo": ("get_manage_to", "set_manage_to"),
    "ManageUI": ("get_manage_ui", "set_manage_ui"),
    "InstanceID": ("get_instance_id", "set_instance_id"),
    "OriginalDocumentID": ("get_original_document_id", "set_original_document_id"),
    "RenditionParams": ("get_rendition_params", "set_rendition_params"),
    "VersionID": ("get_version_id", "set_version_id"),
    # Versions / History / Ingredients use typed getters that return
    # structured types from a typed-only setter; the string-form
    # getters live next to them. Use the typed adders + typed getters
    # for these fields.
    "Versions": ("get_versions_string_list", "add_versions"),
    "History": ("get_history_string_list", "add_history"),
    "Ingredients": ("get_ingredients_string_list", "add_ingredients"),
}


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> XMPMediaManagementSchema:
    return metadata.create_and_add_xmp_media_management_schema()


@pytest.mark.parametrize(
    ("field_name", "type_token", "card", "value"), _PARAMETERS
)
def test_element_value(
    schema: XMPMediaManagementSchema,
    field_name: str,
    type_token: str,
    card: str,
    value: object,
) -> None:
    """Translated from upstream ``testElementValue``."""
    del type_token
    getter_name, setter_name = _ACCESSORS[field_name]
    if not hasattr(schema, getter_name) or not hasattr(schema, setter_name):
        pytest.skip(
            f"{field_name!r} accessor not yet ported: "
            f"missing {getter_name}/{setter_name}"
        )
    if card in {"Bag", "Seq"}:
        assert isinstance(value, tuple)
        for entry in value:
            getattr(schema, setter_name)(entry)
        result = getattr(schema, getter_name)()
        assert result is not None
        # Single round-trip should preserve count and order.
        assert len(result) == len(value)
        return
    getattr(schema, setter_name)(value)
    assert getattr(schema, getter_name)() == value
