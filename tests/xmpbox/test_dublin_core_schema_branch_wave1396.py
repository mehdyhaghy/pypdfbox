"""Wave 1396 branch-coverage tests for ``DublinCoreSchema``.

Closes False-branch arrows where the schema iterates over an
underlying list/array and filters out items of the wrong type:

* 121->120 — ``_build_array_of_text`` skips non-string items
* 137->136 — ``_build_array_of_date`` skips items that aren't str|datetime
* 177->176 — ``_store_array_of_text_property`` skips non-TextType children
* 485->484 — ``get_dates`` skips non-str/datetime items
* 496->495 — ``set_dates_property`` skips non-DateType/TextType children
"""

from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DateType,
    DublinCoreSchema,
    IntegerType,
    TextType,
    XMPMetadata,
)


def _dc() -> DublinCoreSchema:
    return DublinCoreSchema(XMPMetadata.create_xmp_metadata())


def test_build_array_of_text_skips_non_string_items() -> None:
    """``_build_array_of_text`` skips non-string items.

    Closes False arm at line 121.
    """
    dc = _dc()
    # Stash a heterogeneous list directly on _properties so the array
    # builder iterates over mixed types.
    dc._properties["creator"] = ["Alice", 99, "Bob"]  # noqa: SLF001
    prop = dc.get_creators_property()
    assert prop is not None
    # The non-string was filtered out — only two text-typed children remain.
    assert len(prop.get_all_properties()) == 2


def test_build_array_of_date_skips_non_str_datetime_items() -> None:
    """``_build_array_of_date`` skips items that aren't str or datetime.

    Closes False arm at line 137.
    """
    dc = _dc()
    dc._properties["date"] = [datetime(2024, 1, 1, tzinfo=UTC), 12345]  # noqa: SLF001
    prop = dc.get_dates_property()
    assert prop is not None
    assert len(prop.get_all_properties()) == 1


def test_store_array_of_text_property_skips_non_text_children() -> None:
    """``_store_array_of_text_property`` skips non-TextType array children.

    Closes False arm at line 177.
    """
    dc = _dc()
    metadata = XMPMetadata.create_xmp_metadata()
    array = ArrayProperty(
        metadata, dc.get_namespace(), dc.get_prefix(), "creator", Cardinality.Seq,
    )
    array.add_property(
        TextType(metadata, dc.get_namespace(), dc.get_prefix(), "creator", "Alice"),
    )
    array.add_property(
        IntegerType(metadata, dc.get_namespace(), dc.get_prefix(), "creator", 42),
    )
    dc.set_creators_property(array)
    creators = dc.get_creators()
    assert creators == ["Alice"]


def test_get_dates_skips_non_string_datetime_items() -> None:
    """``get_dates`` skips items that aren't str or datetime.

    Closes False arm at line 485.
    """
    dc = _dc()
    dc._properties["date"] = ["2024-01-01T00:00:00Z", 99]  # noqa: SLF001
    dates = dc.get_dates()
    assert dates is not None
    assert len(dates) == 1


def test_set_dates_property_skips_non_text_or_date_children() -> None:
    """``set_dates_property`` skips children that aren't DateType/TextType.

    Closes False arm at line 496.
    """
    dc = _dc()
    metadata = XMPMetadata.create_xmp_metadata()
    array = ArrayProperty(
        metadata, dc.get_namespace(), dc.get_prefix(), "date", Cardinality.Seq,
    )
    array.add_property(
        DateType(
            metadata, dc.get_namespace(), dc.get_prefix(), "date",
            datetime(2024, 5, 1, tzinfo=UTC),
        ),
    )
    array.add_property(
        IntegerType(metadata, dc.get_namespace(), dc.get_prefix(), "date", 1),
    )
    dc.set_dates_property(array)
    dates = dc.get_dates()
    assert dates is not None
    assert len(dates) == 1
