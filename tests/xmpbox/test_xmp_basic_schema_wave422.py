from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    TextType,
    ThumbnailType,
    XMPBasicSchema,
    XMPMetadata,
)


def _schema() -> XMPBasicSchema:
    return XMPBasicSchema(XMPMetadata.create_xmp_metadata())


def _thumbnail(metadata: XMPMetadata, width: int = 32) -> ThumbnailType:
    thumbnail = ThumbnailType(metadata)
    thumbnail.set_width(width)
    thumbnail.set_height(width)
    thumbnail.set_format("JPEG")
    thumbnail.set_image("encoded")
    return thumbnail


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (True, 1),
        (False, 0),
        (12, 12),
        ("  -7  ", -7),
    ],
)
def test_wave422_rating_getter_accepts_legacy_primitive_storage(
    raw_value: object, expected: int
) -> None:
    schema = _schema()
    schema.set_property(XMPBasicSchema.RATING, raw_value)

    assert schema.get_rating() == expected


@pytest.mark.parametrize("raw_value", ["not-an-int", object()])
def test_wave422_rating_getters_ignore_invalid_legacy_storage(raw_value: object) -> None:
    schema = _schema()
    schema.set_property(XMPBasicSchema.RATING, raw_value)

    assert schema.get_rating() is None
    assert schema.get_rating_property() is None


@pytest.mark.parametrize("raw_value", [True, False, 4, "+9", "-2"])
def test_wave422_rating_property_lifts_valid_legacy_storage(raw_value: object) -> None:
    schema = _schema()
    schema.set_property(XMPBasicSchema.RATING, raw_value)

    prop = schema.get_rating_property()
    assert prop is not None
    assert prop.get_property_name() == XMPBasicSchema.RATING
    assert prop.get_value() == int(raw_value)


def test_wave422_array_property_for_bag_stringifies_legacy_entries() -> None:
    schema = _schema()
    schema.set_property(XMPBasicSchema.ADVISORY, ["/xmp:CreateDate", 17, None])

    prop = schema.get_advisory_property()

    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag
    assert prop.get_elements_as_string() == ["/xmp:CreateDate", "17", "None"]
    assert schema.get_advisory() == ["/xmp:CreateDate", 17, None]


def test_wave422_array_property_setters_normalize_property_names() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    advisory = ArrayProperty(
        metadata,
        XMPBasicSchema.NAMESPACE,
        XMPBasicSchema.PREFERRED_PREFIX,
        "WrongName",
        Cardinality.Bag,
    )
    advisory.add_property(
        TextType(
            metadata,
            XMPBasicSchema.NAMESPACE,
            XMPBasicSchema.PREFERRED_PREFIX,
            "li",
            "/pdf:Producer",
        )
    )

    schema.set_advisory_property(advisory)

    assert advisory.get_property_name() == XMPBasicSchema.ADVISORY
    assert schema.get_advisory_property() is advisory
    assert schema.get_advisory() == ["/pdf:Producer"]


def test_wave422_add_thumbnails_replaces_non_array_storage_with_alt() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    thumbnail = _thumbnail(metadata)
    schema.set_property(XMPBasicSchema.THUMBNAILS, "legacy")

    schema.add_thumbnails(thumbnail)

    prop = schema.get_thumbnails_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Alt
    assert schema.get_thumbnails() == [thumbnail]


def test_wave422_get_thumbnails_filters_non_thumbnail_children() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    thumbnail = _thumbnail(metadata, 64)
    alt = ArrayProperty(
        metadata,
        XMPBasicSchema.NAMESPACE,
        XMPBasicSchema.PREFERRED_PREFIX,
        XMPBasicSchema.THUMBNAILS,
        Cardinality.Alt,
    )
    alt.add_property(
        TextType(
            metadata,
            XMPBasicSchema.NAMESPACE,
            XMPBasicSchema.PREFERRED_PREFIX,
            "li",
            "not-a-thumbnail",
        )
    )
    alt.add_property(thumbnail)

    schema.set_thumbnails_property(alt)

    assert schema.get_thumbnails() == [thumbnail]


def test_wave422_set_thumbnails_replaces_existing_alt() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicSchema(metadata)
    first = _thumbnail(metadata, 16)
    second = _thumbnail(metadata, 128)
    schema.add_thumbnails(first)

    schema.set_thumbnails([second])

    assert schema.get_thumbnails() == [second]
