from __future__ import annotations

from pypdfbox.xmpbox import IntegerType, XMPBasicSchema, XMPMetadata


def test_rating_setter_none_clears_existing_integer() -> None:
    schema = XMPBasicSchema(XMPMetadata.create_xmp_metadata())
    schema.set_rating(5)

    schema.set_rating(None)

    assert schema.get_rating() is None
    assert schema.get_rating_property() is None
    assert not schema.has_property(XMPBasicSchema.RATING)


def test_rating_property_setter_none_clears_existing_integer_type() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    schema.set_rating_property(
        IntegerType(
            metadata,
            XMPBasicSchema.NAMESPACE,
            XMPBasicSchema.PREFERRED_PREFIX,
            XMPBasicSchema.RATING,
            3,
        )
    )

    schema.set_rating_property(None)

    assert schema.get_rating() is None
    assert schema.get_rating_property() is None
    assert not schema.has_property(XMPBasicSchema.RATING)
