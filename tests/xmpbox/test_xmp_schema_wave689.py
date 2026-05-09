from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DublinCoreSchema,
    ResourceEventType,
    ResourceRefType,
    TextType,
    VersionType,
    XMPMediaManagementSchema,
    XMPMetadata,
    XMPRightsManagementSchema,
    XMPSchema,
)


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave689_xmp_schema_reads_dict_and_scalar_array_shapes() -> None:
    schema = XMPSchema(_metadata(), namespace_uri="urn:test", prefix="t")

    schema.set_property("title", {"fr": "Bonjour", "x-default": "Default"})
    assert schema.get_unqualified_text_property_value("title") == "Default"

    schema.set_property("title", {"bad": object(), "fr": "Bonjour"})
    assert schema.get_unqualified_text_property_value("title") == "Bonjour"

    schema.set_property("keywords", "solo")
    assert schema.get_unqualified_bag_value_list("keywords") == ["solo"]

    values = {"fr": "Bonjour"}
    XMPSchema._reorganize_alt_order(values)  # noqa: SLF001
    assert values == {"fr": "Bonjour"}


def test_wave689_media_management_singleton_structured_lists_and_save_id_shapes() -> None:
    metadata = _metadata()
    schema = XMPMediaManagementSchema(metadata)
    event = ResourceEventType(metadata)
    version = VersionType(metadata)
    ref = ResourceRefType(metadata)

    schema.set_property(XMPMediaManagementSchema.HISTORY, event)
    schema.set_property(XMPMediaManagementSchema.VERSIONS, version)
    schema.set_property(XMPMediaManagementSchema.MANIFEST, ref)
    schema.set_property(XMPMediaManagementSchema.INGREDIENTS, ref)

    assert schema.get_history() == [event]
    assert schema.get_versions() == [version]
    assert schema.get_manifest() == [ref]
    assert schema.get_ingredients() == [ref]

    schema.set_property(XMPMediaManagementSchema.SAVE_ID, True)
    assert schema.get_save_id() == 1

    schema.set_property(XMPMediaManagementSchema.SAVE_ID, 42)
    assert schema.get_save_id() == 42

    schema.set_property(XMPMediaManagementSchema.SAVE_ID, " not-an-int ")
    assert schema.get_save_id() is None


def test_wave689_dublin_core_private_helpers_and_date_validation() -> None:
    metadata = _metadata()
    schema = DublinCoreSchema(metadata)

    assert DublinCoreSchema._extract_text_value("raw text") == "raw text"  # noqa: SLF001
    with pytest.raises(TypeError, match="expected TextType or str"):
        DublinCoreSchema._extract_text_value(object())  # type: ignore[arg-type]  # noqa: SLF001

    lang_alt = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        DublinCoreSchema.DESCRIPTION,
        Cardinality.Alt,
    )
    lang_alt.add_property(
        ArrayProperty(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            "nested",
            Cardinality.Bag,
        )
    )
    lang_alt.add_property(
        TextType(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            DublinCoreSchema.DESCRIPTION,
            "Default",
        )
    )

    schema.set_description_property(lang_alt)
    assert schema.get_description() == "Default"

    schema.add_subject("old")
    schema.remove_subject("old")
    assert schema.get_subjects() == []

    schema.add_date("2024-05-08")
    schema.add_date(datetime(2024, 5, 9, tzinfo=UTC))
    assert [value.date().isoformat() for value in schema.get_dates() or []] == [
        "2024-05-08",
        "2024-05-09",
    ]

    with pytest.raises(TypeError, match="add_date expects datetime or str"):
        schema.add_date(object())  # type: ignore[arg-type]


def test_wave689_rights_management_absent_and_array_defensive_paths() -> None:
    metadata = _metadata()
    schema = XMPRightsManagementSchema(metadata)

    assert schema.get_certificate_property() is None
    assert schema.get_owners_property() is None

    schema.set_property(XMPRightsManagementSchema.MARKED, object())
    assert schema.get_marked() is None

    owners = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.OWNER,
        Cardinality.Bag,
    )
    nested = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        "nested",
        Cardinality.Seq,
    )
    owners.add_property(nested)
    owners.add_property(
        TextType(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            XMPRightsManagementSchema.OWNER,
            "Alice",
        )
    )
    schema.set_property(XMPRightsManagementSchema.OWNER, owners)

    schema.remove_owner("Alice")
    kept = schema.get_property(XMPRightsManagementSchema.OWNER)
    assert isinstance(kept, ArrayProperty)
    assert kept.get_all_properties() == [nested]

    schema.set_owners(["Bob"])
    schema.set_owners_property(None)
    assert schema.get_owners() is None

    schema.add_usage_terms("fr", "Bonjour")
    assert schema.get_usage_terms("fr") == "Bonjour"
