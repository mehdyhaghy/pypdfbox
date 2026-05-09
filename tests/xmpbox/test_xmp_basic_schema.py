from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DateType,
    IntegerType,
    TextType,
    ThumbnailType,
    XMPBasicSchema,
    XMPMetadata,
    XPathType,
)


def _basic() -> XMPBasicSchema:
    return XMPBasicSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix() -> None:
    b = _basic()
    assert b.get_namespace() == "http://ns.adobe.com/xap/1.0/"
    assert b.get_prefix() == "xmp"


def test_creator_tool() -> None:
    b = _basic()
    b.set_creator_tool("pypdfbox 0.0.1")
    assert b.get_creator_tool() == "pypdfbox 0.0.1"


def test_dates_are_iso_strings_in_cluster_one() -> None:
    b = _basic()
    b.set_create_date("2026-04-25T12:00:00Z")
    b.set_modify_date("2026-04-26T08:30:00Z")
    b.set_metadata_date("2026-04-26T08:30:00Z")
    assert b.get_create_date() == "2026-04-25T12:00:00Z"
    assert b.get_modify_date() == "2026-04-26T08:30:00Z"
    assert b.get_metadata_date() == "2026-04-26T08:30:00Z"


def test_label_nickname_baseurl() -> None:
    b = _basic()
    b.set_label("draft")
    b.set_nickname("doc1")
    b.set_base_url("https://example.com/")
    assert b.get_label() == "draft"
    assert b.get_nickname() == "doc1"
    assert b.get_base_url() == "https://example.com/"


def test_identifier_bag() -> None:
    b = _basic()
    b.add_identifier("id-a")
    b.add_identifier("id-b")
    assert b.get_identifiers() == ["id-a", "id-b"]


def test_remove_identifier() -> None:
    b = _basic()
    b.add_identifier("id-a")
    b.add_identifier("id-b")
    b.remove_identifier("id-a")
    assert b.get_identifiers() == ["id-b"]


# --- typed-property accessors -----------------------------------------


def test_creator_tool_property_round_trip() -> None:
    b = _basic()
    b.set_creator_tool("pypdfbox 0.0.1")
    prop = b.get_creator_tool_property()
    assert isinstance(prop, TextType)
    assert prop.get_value() == "pypdfbox 0.0.1"
    assert prop.get_property_name() == "CreatorTool"
    assert prop.get_namespace() == "http://ns.adobe.com/xap/1.0/"
    assert prop.get_prefix() == "xmp"


def test_creator_tool_property_setter_visible_to_string_getter() -> None:
    b = _basic()
    metadata = b.get_metadata()
    prop = TextType(
        metadata,
        "http://ns.adobe.com/xap/1.0/",
        "xmp",
        "CreatorTool",
        "Adobe Acrobat 9.0",
    )
    b.set_creator_tool_property(prop)
    assert b.get_creator_tool() == "Adobe Acrobat 9.0"
    assert b.get_creator_tool_property() is prop


def test_label_property_round_trip() -> None:
    b = _basic()
    b.set_label("draft")
    prop = b.get_label_property()
    assert isinstance(prop, TextType)
    assert prop.get_value() == "draft"


def test_nickname_property_round_trip() -> None:
    b = _basic()
    b.set_nickname("doc1")
    prop = b.get_nickname_property()
    assert isinstance(prop, TextType)
    assert prop.get_value() == "doc1"


def test_base_url_property_round_trip() -> None:
    b = _basic()
    b.set_base_url("https://example.com/")
    prop = b.get_base_url_property()
    assert isinstance(prop, TextType)
    assert prop.get_value() == "https://example.com/"


def test_typed_props_default_to_none() -> None:
    b = _basic()
    assert b.get_creator_tool_property() is None
    assert b.get_label_property() is None
    assert b.get_nickname_property() is None
    assert b.get_base_url_property() is None
    assert b.get_create_date_property() is None
    assert b.get_modify_date_property() is None
    assert b.get_metadata_date_property() is None
    assert b.get_modifier_date_property() is None
    assert b.get_rating_property() is None
    assert b.get_thumbnails_property() is None
    assert b.get_thumbnails() is None


# --- Date typed accessors --------------------------------------------


def test_create_date_typed_round_trip_with_datetime() -> None:
    b = _basic()
    moment = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    b.set_create_date(moment)
    prop = b.get_create_date_property()
    assert isinstance(prop, DateType)
    assert prop.get_value() == moment
    # String getter still returns an ISO-8601 form.
    assert b.get_create_date().startswith("2026-04-25T12:00:00")
    assert b.get_create_date_value() == moment


def test_modify_date_typed_round_trip_with_datetime() -> None:
    b = _basic()
    moment = datetime(2026, 4, 26, 8, 30, 0, tzinfo=UTC)
    b.set_modify_date(moment)
    prop = b.get_modify_date_property()
    assert isinstance(prop, DateType)
    assert prop.get_value() == moment


def test_metadata_date_typed_round_trip_with_datetime() -> None:
    b = _basic()
    moment = datetime(2026, 4, 26, 8, 30, 0, tzinfo=UTC)
    b.set_metadata_date(moment)
    prop = b.get_metadata_date_property()
    assert isinstance(prop, DateType)
    assert prop.get_value() == moment


def test_modifier_date_typed_round_trip_with_datetime() -> None:
    b = _basic()
    moment = datetime(2026, 4, 27, 1, 0, 0, tzinfo=UTC)
    b.set_modifier_date(moment)
    prop = b.get_modifier_date_property()
    assert isinstance(prop, DateType)
    assert prop.get_value() == moment


def test_string_date_setter_is_visible_to_typed_getter() -> None:
    """ISO-8601 string set via string-form is parsed lazily into DateType."""
    b = _basic()
    b.set_create_date("2026-04-25T12:00:00Z")
    prop = b.get_create_date_property()
    assert isinstance(prop, DateType)
    assert prop.get_value().year == 2026
    assert prop.get_value().month == 4
    assert prop.get_value().day == 25
    # Same path for the typed value getter.
    typed = b.get_create_date_value()
    assert isinstance(typed, datetime)
    assert typed.year == 2026


def test_typed_date_setter_is_visible_to_string_getter() -> None:
    b = _basic()
    metadata = b.get_metadata()
    prop = DateType(
        metadata,
        "http://ns.adobe.com/xap/1.0/",
        "xmp",
        "CreateDate",
        datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC),
    )
    b.set_create_date_property(prop)
    s = b.get_create_date()
    assert s is not None
    assert s.startswith("2026-04-25T12:00:00")


# --- Rating (Integer) -------------------------------------------------


def test_rating_round_trip_int() -> None:
    b = _basic()
    b.set_rating(7)
    assert b.get_rating() == 7
    prop = b.get_rating_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 7


def test_rating_round_trip_string() -> None:
    b = _basic()
    b.set_rating("3")
    assert b.get_rating() == 3
    prop = b.get_rating_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 3


def test_rating_property_setter() -> None:
    b = _basic()
    metadata = b.get_metadata()
    prop = IntegerType(
        metadata, "http://ns.adobe.com/xap/1.0/", "xmp", "Rating", 5
    )
    b.set_rating_property(prop)
    assert b.get_rating() == 5
    assert b.get_rating_property() is prop


# --- Advisory (Bag) ---------------------------------------------------


def test_advisory_bag() -> None:
    b = _basic()
    b.add_advisory("/path/to/x")
    b.add_advisory("/path/to/y")
    assert b.get_advisory() == ["/path/to/x", "/path/to/y"]
    b.remove_advisory("/path/to/x")
    assert b.get_advisory() == ["/path/to/y"]


# --- Thumbnails (Alt of ThumbnailType) -------------------------------


def _make_thumbnail(metadata: XMPMetadata, width: int, height: int) -> ThumbnailType:
    thumbnail = ThumbnailType(metadata)
    thumbnail.set_width(width)
    thumbnail.set_height(height)
    thumbnail.set_format("JPEG")
    thumbnail.set_image("base64-data")
    return thumbnail


def test_add_thumbnails_appends_to_alt() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    b = XMPBasicSchema(metadata)
    first = _make_thumbnail(metadata, 160, 120)
    second = _make_thumbnail(metadata, 320, 240)

    b.add_thumbnails(first)
    b.add_thumbnail(second)

    thumbnails = b.get_thumbnails()
    assert thumbnails == [first, second]
    prop = b.get_thumbnails_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Alt


def test_set_thumbnails_replaces_and_clears() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    b = XMPBasicSchema(metadata)
    thumbnail = _make_thumbnail(metadata, 64, 64)

    b.set_thumbnails([thumbnail])
    assert b.get_thumbnails() == [thumbnail]
    b.set_thumbnails(None)

    assert b.get_thumbnails() is None
    assert b.get_thumbnails_property() is None


def test_thumbnails_property_round_trip_via_array_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    b = XMPBasicSchema(metadata)
    alt = ArrayProperty(
        metadata,
        XMPBasicSchema.NAMESPACE,
        XMPBasicSchema.PREFERRED_PREFIX,
        XMPBasicSchema.THUMBNAILS,
        Cardinality.Alt,
    )
    thumbnail = _make_thumbnail(metadata, 100, 75)
    alt.add_property(thumbnail)

    b.set_thumbnails_property(alt)

    assert b.get_thumbnails_property() is alt
    assert b.get_property(XMPBasicSchema.THUMBNAILS) is alt
    assert b.get_thumbnails() == [thumbnail]


def test_set_thumbnails_property_none_clears() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    b = XMPBasicSchema(metadata)
    b.add_thumbnails(_make_thumbnail(metadata, 100, 75))

    b.set_thumbnails_property(None)

    assert b.get_thumbnails_property() is None
    assert b.get_thumbnails() is None


def test_get_advisory_property_returns_array_wrapper() -> None:
    b = _basic()
    assert b.get_advisory_property() is None
    b.add_advisory("/x:foo")
    b.add_advisory("/x:bar")

    prop = b.get_advisory_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() == Cardinality.Bag
    assert prop.get_property_name() == XMPBasicSchema.ADVISORY
    assert all(isinstance(child, XPathType) for child in prop.get_all_properties())
    # the cluster-1 string getter still mirrors the entries
    assert b.get_advisory() == ["/x:foo", "/x:bar"]


def test_get_identifiers_property_returns_array_wrapper() -> None:
    b = _basic()
    assert b.get_identifiers_property() is None
    b.add_identifier("urn:isbn:0451524934")
    b.add_identifier("urn:isbn:0140177396")

    prop = b.get_identifiers_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() == Cardinality.Bag
    assert prop.get_property_name() == XMPBasicSchema.IDENTIFIER
    assert all(isinstance(child, TextType) for child in prop.get_all_properties())
    assert not any(isinstance(child, XPathType) for child in prop.get_all_properties())
    assert b.get_identifiers() == [
        "urn:isbn:0451524934",
        "urn:isbn:0140177396",
    ]
