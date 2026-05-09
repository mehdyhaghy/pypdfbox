from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox import (
    ArrayProperty,
    BooleanType,
    Cardinality,
    ColorantType,
    DateType,
    DublinCoreSchema,
    FontType,
    LangAlt,
    TextType,
    URIType,
    XMPageTextSchema,
    XMPBasicSchema,
    XMPMediaManagementSchema,
    XMPMetadata,
    XMPRightsManagementSchema,
)
from pypdfbox.xmpbox.type import ResourceEventType, ResourceRefType, VersionType


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave743_xmp_basic_remaining_date_and_clear_paths() -> None:
    metadata = _metadata()
    schema = XMPBasicSchema(metadata)
    when = datetime(2026, 5, 9, 12, 30, tzinfo=UTC)
    prop = DateType(
        metadata,
        XMPBasicSchema.NAMESPACE,
        XMPBasicSchema.PREFERRED_PREFIX,
        XMPBasicSchema.MODIFIER_DATE,
        when,
    )

    schema.set_property(XMPBasicSchema.CREATEDATE, object())
    assert schema.get_create_date_value() is None

    schema.set_advisory_property(None)
    assert schema.get_advisory_property() is None

    schema.set_modifier_date(when)
    assert schema.get_modifier_date() == "2026-05-09T12:30:00+00:00"
    schema.set_modifier_date_property(prop)
    assert schema.get_modifier_date_property() is prop
    assert schema.get_modifier_date_value() == when


def test_wave743_xmp_basic_date_properties_reject_invalid_string_storage() -> None:
    schema = XMPBasicSchema(_metadata())
    schema.set_property(XMPBasicSchema.MODIFYDATE, "not-a-date")
    schema.set_property(XMPBasicSchema.METADATADATE, "also-not-a-date")
    schema.set_property(XMPBasicSchema.MODIFIER_DATE, "still-not-a-date")

    assert schema.get_modify_date_property() is None
    assert schema.get_metadata_date_property() is None
    assert schema.get_modifier_date_property() is None
    assert schema.get_modifier_date_value() is None


def test_wave743_paged_text_primitive_and_singleton_storage_paths() -> None:
    metadata = _metadata()
    schema = XMPageTextSchema(metadata)
    colorant = ColorantType(metadata)
    font = FontType(metadata)

    schema.set_property(XMPageTextSchema.N_PAGES, 17)
    assert schema.get_n_pages() == 17
    assert XMPageTextSchema._coerce_boolean(True) is True

    schema.set_property(XMPageTextSchema.COLORANTS, colorant)
    assert schema.get_colorants() == [colorant]
    assert schema.get_colorant_properties() == [colorant]

    schema.set_property(XMPageTextSchema.FONTS, font)
    assert schema.get_fonts() == [font]
    assert schema.get_font_properties() == [font]


def test_wave743_paged_text_max_page_size_ignores_invalid_dimensions() -> None:
    schema = XMPageTextSchema(_metadata())
    schema.set_max_page_size({"w": "wide", "h": object(), "unit": 123})

    dimensions = schema.get_max_page_size_property()

    assert dimensions is not None
    assert dimensions.get_w() is None
    assert dimensions.get_h() is None
    assert dimensions.get_unit() == "123"


def test_wave743_dublin_core_lang_alt_skips_non_text_values() -> None:
    schema = DublinCoreSchema(_metadata())
    schema.set_property(
        DublinCoreSchema.TITLE,
        {"fr": object(), "x-default": "Default", "de": "Titel"},
    )

    prop = schema.get_title_property()

    assert isinstance(prop, LangAlt)
    assert prop.get_language_value(None) == "Default"
    assert prop.get_language_value("de") == "Titel"
    assert prop.get_language_value("fr") is None


def test_wave743_dublin_core_rejects_non_text_simple_property() -> None:
    schema = DublinCoreSchema(_metadata())

    try:
        schema.set_source_property(object())  # type: ignore[arg-type]
    except TypeError as exc:
        assert "expected TextType or str" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("set_source_property accepted a non-text object")


def test_wave743_media_management_singletons_and_mixed_arrays() -> None:
    metadata = _metadata()
    schema = XMPMediaManagementSchema(metadata)
    event = ResourceEventType(metadata)
    version = VersionType(metadata)
    ref = ResourceRefType(metadata)

    schema.set_property(XMPMediaManagementSchema.HISTORY, event)
    assert schema.get_history() == [event]
    schema.set_property(
        XMPMediaManagementSchema.HISTORY,
        ["legacy", event, version],
    )
    assert schema.get_history() == [event]

    schema.set_property(XMPMediaManagementSchema.VERSIONS, version)
    assert schema.get_versions() == [version]

    schema.set_property(XMPMediaManagementSchema.MANIFEST, ref)
    assert schema.get_manifest() == [ref]
    schema.set_property(
        XMPMediaManagementSchema.INGREDIENTS,
        ["legacy", ref, event],
    )
    assert schema.get_ingredients() == [ref]


def test_wave743_media_management_adders_replace_non_list_storage() -> None:
    metadata = _metadata()
    schema = XMPMediaManagementSchema(metadata)
    event = ResourceEventType(metadata)
    version = VersionType(metadata)
    ref = ResourceRefType(metadata)

    schema.set_property(XMPMediaManagementSchema.HISTORY, "legacy")
    schema.add_history(event)
    assert schema.get_history() == [event]

    schema.set_property(XMPMediaManagementSchema.VERSIONS, "legacy")
    schema.add_version(version)
    assert schema.get_versions() == [version]

    schema.set_property(XMPMediaManagementSchema.MANIFEST, "legacy")
    schema.add_manifest(ref)
    assert schema.get_manifest() == [ref]

    schema.set_property(XMPMediaManagementSchema.INGREDIENTS, "legacy")
    schema.add_ingredient(ref)
    assert schema.get_ingredients() == [ref]


def test_wave743_rights_typed_getters_wrap_cross_type_storage() -> None:
    metadata = _metadata()
    schema = XMPRightsManagementSchema(metadata)
    raw_url = TextType(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.CERTIFICATE,
        "https://example.com/cert",
    )
    marked_text = TextType(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.MARKED,
        "true",
    )

    schema.set_property(XMPRightsManagementSchema.CERTIFICATE, raw_url)
    schema.set_property(XMPRightsManagementSchema.MARKED, marked_text)

    cert = schema.get_certificate_property()
    marked = schema.get_marked_property()
    assert isinstance(cert, URIType)
    assert cert.get_string_value() == "https://example.com/cert"
    assert schema.get_certificate() == "https://example.com/cert"
    assert isinstance(marked, BooleanType)
    assert marked.get_value() is True
    assert schema.get_marked() is True


def test_wave743_rights_owner_and_usage_terms_array_edge_cases() -> None:
    metadata = _metadata()
    schema = XMPRightsManagementSchema(metadata)
    nested = ArrayProperty(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        "Nested",
        Cardinality.Bag,
    )
    owners = ArrayProperty(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.OWNER,
        Cardinality.Bag,
    )
    owners.add_property(nested)
    owners.add_property(
        TextType(
            metadata,
            XMPRightsManagementSchema.NAMESPACE,
            XMPRightsManagementSchema.PREFERRED_PREFIX,
            XMPRightsManagementSchema.OWNER,
            "Alice",
        )
    )

    schema.set_owners_property(owners)
    assert schema.get_owners() == ["Alice"]

    usage = ArrayProperty(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.USAGE_TERMS,
        Cardinality.Alt,
    )
    usage.add_property(nested)
    usage.add_property(
        TextType(
            metadata,
            XMPRightsManagementSchema.NAMESPACE,
            XMPRightsManagementSchema.PREFERRED_PREFIX,
            XMPRightsManagementSchema.USAGE_TERMS,
            "Default terms",
        )
    )

    schema.set_usage_terms_property(usage)
    assert schema.get_usage_terms() == "Default terms"
