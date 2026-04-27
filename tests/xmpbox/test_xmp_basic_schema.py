from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox import DateType, IntegerType, TextType, XMPBasicSchema, XMPMetadata


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
