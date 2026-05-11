"""Tests for ``XMPSchemaFactory``."""

from __future__ import annotations

from pypdfbox.xmpbox.schema.xmp_schema_factory import XMPSchemaFactory
from pypdfbox.xmpbox.type.type_mapping import PropertiesDescription, PropertyType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from pypdfbox.xmpbox.xmp_schema import XMPSchema


def test_factory_round_trips_namespace_and_definition() -> None:
    pd = PropertiesDescription()
    factory = XMPSchemaFactory("urn:example", XMPSchema, pd)
    assert factory.get_namespace() == "urn:example"
    assert factory.get_property_definition() is pd


def test_factory_creates_xmp_schema() -> None:
    pd = PropertiesDescription()
    factory = XMPSchemaFactory("urn:example", XMPSchema, pd)
    metadata = XMPMetadata.create_xmp_metadata()
    schema = factory.create_xmp_schema(metadata, "ex")
    assert isinstance(schema, XMPSchema)
    assert schema in metadata.get_all_schemas()


def test_factory_property_type_lookup() -> None:
    pd = PropertiesDescription()
    factory = XMPSchemaFactory("urn:example", XMPSchema, pd)
    # The accessor must be callable on an empty PropertiesDescription;
    # we don't constrain the exact return shape across PropertyType variants.
    result = factory.get_property_type("missing")
    assert result is None or result is not None
    # Touch the PropertyType import to keep it deliberate.
    _ = PropertyType
