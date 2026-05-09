from __future__ import annotations

from pypdfbox.xmpbox import (
    ArrayProperty,
    Attribute,
    BooleanType,
    Cardinality,
    LangAlt,
    ProperNameType,
    TextType,
    URIType,
    XMPMetadata,
    XMPRightsManagementSchema,
)
from pypdfbox.xmpbox.type.lang_alt import LANG_ATTR_NAME, XML_NS_URI


def _rights() -> XMPRightsManagementSchema:
    return XMPRightsManagementSchema(XMPMetadata.create_xmp_metadata())


def test_wave365_typed_simple_setters_pin_property_names_and_clear() -> None:
    schema = _rights()
    metadata = schema.get_metadata()
    certificate = URIType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "urn:cert")
    marked = BooleanType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", True)
    web = URIType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "https://rights")

    schema.set_certificate_property(certificate)
    schema.set_marked_property(marked)
    schema.set_web_statement_property(web)

    assert certificate.get_property_name() == XMPRightsManagementSchema.CERTIFICATE
    assert marked.get_property_name() == XMPRightsManagementSchema.MARKED
    assert web.get_property_name() == XMPRightsManagementSchema.WEB_STATEMENT
    assert schema.get_certificate_property() is certificate
    assert schema.get_marked_property() is marked
    assert schema.get_web_statement_property() is web
    assert schema.get_certificate() == "urn:cert"
    assert schema.get_marked() is True
    assert schema.get_web_statement() == "https://rights"

    schema.set_certificate_property(None)
    schema.set_marked_property(None)
    schema.set_web_statement_property(None)

    assert schema.get_certificate() is None
    assert schema.get_marked() is None
    assert schema.get_web_statement() is None


def test_wave365_typed_getters_materialize_from_simple_storage() -> None:
    schema = _rights()
    schema.set_certificate("urn:raw-cert")
    schema.set_text_property_value(XMPRightsManagementSchema.MARKED, " false ")
    schema.set_web_statement("https://example.test/rights")

    cert = schema.get_certificate_property()
    marked = schema.get_marked_property()
    web = schema.get_web_statement_property()

    assert isinstance(cert, URIType)
    assert cert.get_property_name() == XMPRightsManagementSchema.CERTIFICATE
    assert cert.get_string_value() == "urn:raw-cert"
    assert isinstance(marked, BooleanType)
    assert marked.get_property_name() == XMPRightsManagementSchema.MARKED
    assert marked.get_value() is False
    assert schema.get_marked() is False
    assert isinstance(web, URIType)
    assert web.get_property_name() == XMPRightsManagementSchema.WEB_STATEMENT
    assert web.get_string_value() == "https://example.test/rights"


def test_wave365_marked_reads_bool_and_simple_property_storage() -> None:
    schema = _rights()
    metadata = schema.get_metadata()

    schema.set_property(XMPRightsManagementSchema.MARKED, False)
    assert schema.get_marked() is False

    raw_text = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.MARKED,
        "True",
    )
    schema.set_property(XMPRightsManagementSchema.MARKED, raw_text)

    assert schema.get_marked() is True
    marked = schema.get_marked_property()
    assert isinstance(marked, BooleanType)
    assert marked.get_value() is True


def test_wave365_owner_property_filters_non_simple_children() -> None:
    schema = _rights()
    metadata = schema.get_metadata()
    owners = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        "tmp",
        Cardinality.Bag,
    )
    owners.add_property(
        ProperNameType(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            "li",
            "Alice",
        )
    )
    owners.add_property(
        TextType(metadata, schema.get_namespace(), schema.get_prefix(), "li", "Bob")
    )
    owners.add_property(
        ArrayProperty(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            "nested",
            Cardinality.Seq,
        )
    )

    schema.set_owners_property(owners)

    assert schema.get_owners() == ["Alice", "Bob"]
    typed = schema.get_owners_property()
    assert isinstance(typed, ArrayProperty)
    assert typed.get_array_type() is Cardinality.Bag
    assert [child.get_string_value() for child in typed.get_all_properties()] == [
        "Alice",
        "Bob",
    ]


def test_wave365_usage_terms_property_orders_default_and_skips_bad_values() -> None:
    schema = _rights()
    schema.set_property(
        XMPRightsManagementSchema.USAGE_TERMS,
        {"fr": "Bonjour", "x-default": "Default", "bad": object()},
    )

    lang_alt = schema.get_usage_terms_property()

    assert isinstance(lang_alt, LangAlt)
    assert lang_alt.get_language_value("x-default") == "Default"
    assert lang_alt.get_language_value("fr") == "Bonjour"
    children = lang_alt.get_all_properties()
    first_attr = children[0].get_attribute(LANG_ATTR_NAME)
    assert first_attr is not None
    assert first_attr.get_value() == "x-default"
    assert lang_alt.get_languages() == ["x-default", "fr"]


def test_wave365_set_usage_terms_property_defaults_missing_lang_and_clears() -> None:
    schema = _rights()
    metadata = schema.get_metadata()
    lang_alt = LangAlt(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.USAGE_TERMS,
    )
    default_text = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.USAGE_TERMS,
        "Default from missing xml:lang",
    )
    german_text = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.USAGE_TERMS,
        "Hallo",
    )
    german_text.set_attribute(Attribute(XML_NS_URI, LANG_ATTR_NAME, "de"))
    lang_alt.add_property(default_text)
    lang_alt.add_property(german_text)
    lang_alt.add_property(
        ArrayProperty(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            "nested",
            Cardinality.Bag,
        )
    )

    schema.set_usage_terms_property(lang_alt)

    assert schema.get_usage_terms() == "Default from missing xml:lang"
    assert schema.get_usage_terms("de") == "Hallo"
    assert schema.get_usage_terms_languages() == ["x-default", "de"]

    schema.set_usage_terms_property(None)

    assert schema.get_usage_terms_property() is None
    assert schema.get_usage_terms() is None
