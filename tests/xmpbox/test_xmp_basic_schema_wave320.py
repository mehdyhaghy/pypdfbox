from __future__ import annotations

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    TextType,
    XMPBasicSchema,
    XMPMetadata,
)


def _text_bag(
    metadata: XMPMetadata, local_name: str, values: list[str]
) -> ArrayProperty:
    bag = ArrayProperty(
        metadata,
        XMPBasicSchema.NAMESPACE,
        XMPBasicSchema.PREFERRED_PREFIX,
        local_name,
        Cardinality.Bag,
    )
    for value in values:
        bag.add_property(
            TextType(
                metadata,
                XMPBasicSchema.NAMESPACE,
                XMPBasicSchema.PREFERRED_PREFIX,
                "li",
                value,
            )
        )
    return bag


def test_wave320_advisory_property_setter_interops_with_string_helpers() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    advisory = _text_bag(
        metadata, XMPBasicSchema.ADVISORY, ["/xmp:CreatorTool", "/dc:title"]
    )

    schema.set_advisory_property(advisory)

    assert schema.get_advisory_property() is advisory
    assert schema.get_advisory() == ["/xmp:CreatorTool", "/dc:title"]

    schema.remove_advisory("/xmp:CreatorTool")
    schema.add_advisory("/pdf:Producer")

    assert schema.get_advisory_property() is advisory
    assert schema.get_advisory() == ["/dc:title", "/pdf:Producer"]
    assert advisory.get_elements_as_string() == ["/dc:title", "/pdf:Producer"]


def test_wave320_identifiers_property_setter_round_trips_and_clears() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    identifiers = _text_bag(
        metadata, XMPBasicSchema.IDENTIFIER, ["urn:uuid:one", "urn:uuid:two"]
    )

    schema.set_identifiers_property(identifiers)

    assert schema.get_identifiers_property() is identifiers
    assert schema.get_identifiers() == ["urn:uuid:one", "urn:uuid:two"]

    schema.set_identifiers_property(None)

    assert schema.get_identifiers_property() is None
    assert schema.get_identifiers() is None
