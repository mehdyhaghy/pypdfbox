"""Branch-coverage round-out (wave 1367) for ``XMPBasicSchema``.

Pins date round-trip semantics (ISO 8601, timezone preservation), the
Advisory ``ArrayProperty`` storage path, rating integer typed/string
interop, and thumbnail Alt cardinality enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox.type import (
    ArrayProperty,
    Cardinality,
    DateType,
    IntegerType,
    TextType,
    ThumbnailType,
    XPathType,
)
from pypdfbox.xmpbox.xmp_basic_schema import XMPBasicSchema
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> XMPBasicSchema:
    return XMPBasicSchema(XMPMetadata.create_xmp_metadata())


def test_create_date_typed_setter_round_trip(schema: XMPBasicSchema) -> None:
    when = datetime(2023, 6, 1, 9, 30, 0, tzinfo=UTC)
    date = DateType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPBasicSchema.CREATEDATE,
        when,
    )
    schema.set_create_date_property(date)
    assert schema.get_create_date_value() == when
    # The string-form getter sees the typed instance via ``_read_date_string``.
    assert schema.get_create_date() is not None


def test_create_date_string_setter_parsed_lazily(schema: XMPBasicSchema) -> None:
    schema.set_create_date("2024-01-02T03:04:05Z")
    parsed = schema.get_create_date_value()
    assert parsed is not None
    assert parsed.year == 2024 and parsed.month == 1
    # String getter returns the original string.
    assert schema.get_create_date() == "2024-01-02T03:04:05Z"


def test_invalid_create_date_string_returns_none_for_value(
    schema: XMPBasicSchema,
) -> None:
    schema.set_create_date("not a date")
    assert schema.get_create_date_value() is None
    # The string form is still readable.
    assert schema.get_create_date() == "not a date"


def test_advisory_array_property_path(schema: XMPBasicSchema) -> None:
    # Install an ArrayProperty directly so add_advisory routes through the
    # typed branch rather than the legacy list branch.
    array = ArrayProperty(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPBasicSchema.ADVISORY,
        Cardinality.Bag,
    )
    schema.set_advisory_property(array)
    schema.add_advisory("/Root/SomePath")
    schema.add_advisory("/Root/Another")
    advisory = schema.get_advisory_property()
    assert isinstance(advisory, ArrayProperty)
    assert len(advisory.get_all_properties()) == 2


def test_advisory_legacy_list_then_typed_getter(schema: XMPBasicSchema) -> None:
    # Without explicit ArrayProperty install, add_advisory falls back to legacy
    # list storage; the typed getter must lift it into XPathType children.
    schema.add_advisory("/Path1")
    schema.add_advisory("/Path2")
    array = schema.get_advisory_property()
    assert isinstance(array, ArrayProperty)
    children = array.get_all_properties()
    assert all(isinstance(c, XPathType) for c in children)


def test_set_advisory_property_to_none_removes(schema: XMPBasicSchema) -> None:
    schema.add_advisory("/X")
    schema.set_advisory_property(None)
    assert schema.get_advisory() is None


def test_rating_typed_setter_round_trip(schema: XMPBasicSchema) -> None:
    integer = IntegerType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPBasicSchema.RATING,
        5,
    )
    schema.set_rating_property(integer)
    assert schema.get_rating() == 5
    typed = schema.get_rating_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 5


def test_rating_string_setter_returns_int(schema: XMPBasicSchema) -> None:
    schema.set_rating("3")
    assert schema.get_rating() == 3
    typed = schema.get_rating_property()
    assert typed is not None
    assert typed.get_value() == 3


def test_rating_invalid_string_returns_none(schema: XMPBasicSchema) -> None:
    # Bypass set_rating's validation by direct-storing a bad string.
    schema.set_property(XMPBasicSchema.RATING, "not-a-number")
    assert schema.get_rating() is None
    assert schema.get_rating_property() is None


def test_thumbnails_alt_cardinality(schema: XMPBasicSchema) -> None:
    thumb = ThumbnailType(schema.get_metadata())
    thumb.set_format("image/jpeg")
    thumb.set_width(128)
    thumb.set_height(96)
    schema.add_thumbnails(thumb)
    array = schema.get_thumbnails_property()
    assert isinstance(array, ArrayProperty)
    assert array.get_array_type() == Cardinality.Alt
    listed = schema.get_thumbnails()
    assert listed is not None and len(listed) == 1


def test_identifiers_bag_set_and_remove(schema: XMPBasicSchema) -> None:
    schema.add_identifier("id-1")
    schema.add_identifier("id-2")
    schema.add_identifier("id-3")
    schema.remove_identifier("id-2")
    assert schema.get_identifiers() == ["id-1", "id-3"]


def test_label_typed_setter_returns_same_instance(schema: XMPBasicSchema) -> None:
    text = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPBasicSchema.LABEL,
        "Public",
    )
    schema.set_label_property(text)
    assert schema.get_label() == "Public"
    same = schema.get_label_property()
    assert same is text


def test_modify_date_local_tz_round_trip(schema: XMPBasicSchema) -> None:
    tz_plus_2 = timezone(timedelta(hours=2))
    when = datetime(2025, 3, 1, 14, 0, 0, tzinfo=tz_plus_2)
    schema.set_modify_date(when)
    parsed = schema.get_modify_date_value()
    assert parsed is not None
    # Same instant (allow tz normalisation by comparing UTC offset-aware).
    assert parsed == when
