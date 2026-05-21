"""Branch-coverage round-out (wave 1367) for ``XMPMediaManagementSchema``.

Pins typed-instance / string-form interop on the URI / Text / URL /
Integer properties, structured ResourceRef round-trips for DerivedFrom
and ManagedFrom, the Versions Seq and Ingredients Bag string accessors,
and the SaveID typed/string fallback paths.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.resource_event_type import ResourceEventType
from pypdfbox.xmpbox.type.resource_ref_type import ResourceRefType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.type.url_type import URLType
from pypdfbox.xmpbox.type.version_type import VersionType
from pypdfbox.xmpbox.xmp_media_management_schema import XMPMediaManagementSchema
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> XMPMediaManagementSchema:
    return XMPMediaManagementSchema(XMPMetadata.create_xmp_metadata())


def _text(schema: XMPMediaManagementSchema, name: str, value: str) -> TextType:
    return TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        name,
        value,
    )


def test_document_id_typed_setter_round_trip(
    schema: XMPMediaManagementSchema,
) -> None:
    schema.set_document_id_property(
        _text(schema, XMPMediaManagementSchema.DOCUMENT_ID, "urn:uuid:1")
    )
    assert schema.get_document_id() == "urn:uuid:1"
    typed = schema.get_document_id_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "urn:uuid:1"


def test_set_document_id_with_none_removes(
    schema: XMPMediaManagementSchema,
) -> None:
    schema.set_document_id("urn:uuid:tmp")
    schema.set_document_id(None)
    assert schema.get_document_id() is None
    assert schema.get_document_id_property() is None


def test_typed_setter_for_property_then_string_getter(
    schema: XMPMediaManagementSchema,
) -> None:
    schema.set_instance_id_property(
        _text(schema, XMPMediaManagementSchema.INSTANCE_ID, "urn:uuid:inst")
    )
    assert schema.get_instance_id() == "urn:uuid:inst"


def test_derived_from_round_trip(schema: XMPMediaManagementSchema) -> None:
    ref = ResourceRefType(schema.get_metadata())
    ref.set_document_id("urn:uuid:src")
    ref.set_instance_id("urn:uuid:src-inst")
    schema.set_derived_from(ref)
    out = schema.get_derived_from()
    assert out is ref
    # Deprecated accessor returns the same object.
    assert schema.get_resource_ref_property() is ref


def test_derived_from_clear_with_none(
    schema: XMPMediaManagementSchema,
) -> None:
    ref = ResourceRefType(schema.get_metadata())
    schema.set_derived_from(ref)
    schema.set_derived_from(None)
    assert schema.get_derived_from() is None


def test_managed_from_round_trip(schema: XMPMediaManagementSchema) -> None:
    ref = ResourceRefType(schema.get_metadata())
    ref.set_document_id("urn:uuid:managed")
    schema.set_managed_from_property(ref)
    assert schema.get_managed_from_property() is ref
    schema.set_managed_from(None)
    assert schema.get_managed_from() is None


def test_history_string_path(schema: XMPMediaManagementSchema) -> None:
    schema.add_history("action=save when=2023-01-01")
    schema.add_history("action=publish when=2023-02-01")
    # String-list path used by upstream's deprecated getHistory().
    strs = schema.get_history_string_list()
    assert strs is not None
    assert len(strs) == 2
    # Typed list path only returns ResourceEventType instances; pure strings filter out.
    assert schema.get_history() == []


def test_history_typed_path(schema: XMPMediaManagementSchema) -> None:
    event = ResourceEventType(schema.get_metadata())
    event.set_action("saved")
    schema.add_history(event)
    typed = schema.get_history()
    assert typed is not None and len(typed) == 1
    assert typed[0] is event


def test_versions_typed_round_trip(schema: XMPMediaManagementSchema) -> None:
    version = VersionType(schema.get_metadata())
    version.set_version("1.0")
    schema.add_version(version)
    listed = schema.get_versions()
    assert listed is not None and len(listed) == 1
    assert listed[0].get_version() == "1.0"


def test_versions_string_path(schema: XMPMediaManagementSchema) -> None:
    schema.add_versions("v-a")
    schema.add_versions("v-b")
    assert schema.get_versions_string_list() == ["v-a", "v-b"]


def test_save_id_typed_round_trip(schema: XMPMediaManagementSchema) -> None:
    schema.set_save_id(42)
    assert schema.get_save_id() == 42
    typed = schema.get_save_id_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 42


def test_save_id_string_form_parses(schema: XMPMediaManagementSchema) -> None:
    schema.set_property(XMPMediaManagementSchema.SAVE_ID, "100")
    assert schema.get_save_id() == 100


def test_save_id_invalid_string_returns_none(
    schema: XMPMediaManagementSchema,
) -> None:
    schema.set_property(XMPMediaManagementSchema.SAVE_ID, "not-an-int")
    assert schema.get_save_id() is None


def test_last_url_typed_property_round_trip(
    schema: XMPMediaManagementSchema,
) -> None:
    url = URLType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPMediaManagementSchema.LAST_URL,
        "http://example.org/last",
    )
    schema.set_last_url_property(url)
    assert schema.get_last_url() == "http://example.org/last"
    typed = schema.get_last_url_property()
    assert isinstance(typed, URLType)


def test_ingredients_typed_and_string_paths(
    schema: XMPMediaManagementSchema,
) -> None:
    # String path
    schema.add_ingredients("part-A")
    schema.add_ingredients("part-B")
    assert schema.get_ingredients_string_list() == ["part-A", "part-B"]
    # Typed path on a separate schema instance to avoid mixing storage shapes.
    other = XMPMediaManagementSchema(XMPMetadata.create_xmp_metadata())
    ref = ResourceRefType(other.get_metadata())
    other.add_ingredient(ref)
    listed = other.get_ingredients()
    assert listed is not None and listed[0] is ref


def test_rendition_class_typed_via_text(
    schema: XMPMediaManagementSchema,
) -> None:
    schema.set_rendition_class("default")
    typed = schema.get_rendition_class_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "default"


def test_namespaces_pre_registered_on_construct(
    schema: XMPMediaManagementSchema,
) -> None:
    namespaces = schema.get_namespaces()
    assert ResourceRefType.PREFERRED_PREFIX in namespaces
    assert ResourceEventType.PREFERRED_PREFIX in namespaces
    assert VersionType.PREFERRED_PREFIX in namespaces
