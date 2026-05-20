"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/XmpRightsSchemaTest.java

Upstream drives ``XMPSchemaTester#testGetSetValue`` /
``XMPSchemaTester#testGetSetProperty`` over five tuples covering the
URL / Boolean / Bag-of-ProperName / LangAlt cardinality columns of
:class:`XMPRightsManagementSchema`. The Python port collapses the
reflection-driven matrix to direct accessor calls per property.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata, XMPRightsManagementSchema


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> XMPRightsManagementSchema:
    return metadata.create_and_add_xmp_rights_management_schema()


def test_certificate(schema: XMPRightsManagementSchema) -> None:
    """Upstream tuple ``Arguments.of("Certificate", URL, "http://...cer")``."""
    value = "http://une.url.vers.un.certificat/moncert.cer"
    schema.set_certificate(value)
    assert schema.get_certificate() == value


def test_marked(schema: XMPRightsManagementSchema) -> None:
    """Upstream tuple ``Arguments.of("Marked", Boolean, true)``."""
    schema.set_marked(True)
    assert schema.get_marked() is True
    schema.set_marked(False)
    assert schema.get_marked() is False


def test_owner(schema: XMPRightsManagementSchema) -> None:
    """Upstream tuple ``Arguments.of("Owner", ProperName, Bag, ["OwnerName"])``."""
    schema.add_owner("OwnerName")
    owners = schema.get_owners()
    assert owners is not None
    assert "OwnerName" in owners


def test_usage_terms(schema: XMPRightsManagementSchema) -> None:
    """Upstream tuple
    ``Arguments.of("UsageTerms", LangAlt, {"fr": ..., "en": ...})``."""
    schema.add_usage_terms("fr", "Termes d'utilisation")
    schema.add_usage_terms("en", "Usage Terms")
    assert schema.get_usage_terms("fr") == "Termes d'utilisation"
    assert schema.get_usage_terms("en") == "Usage Terms"
    langs = schema.get_usage_terms_languages()
    assert langs is not None
    assert set(langs) == {"fr", "en"}


def test_web_statement(schema: XMPRightsManagementSchema) -> None:
    """Upstream tuple ``Arguments.of("WebStatement", URL, "http://...fr/")``."""
    value = "http://une.url.vers.une.page.fr/"
    schema.set_web_statement(value)
    assert schema.get_web_statement() == value


def test_typed_certificate_property(
    metadata: XMPMetadata, schema: XMPRightsManagementSchema
) -> None:
    """Translated from upstream ``testElementProperty`` for the URL row —
    construct a :class:`URIType` and round-trip through the typed setter."""
    from pypdfbox.xmpbox import URIType
    value = "http://une.url.vers.un.certificat/moncert.cer"
    prop = URIType(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.CERTIFICATE,
        value,
    )
    schema.set_certificate_property(prop)
    fetched = schema.get_certificate_property()
    assert fetched is not None
    assert fetched.get_string_value() == value


def test_typed_marked_property(
    metadata: XMPMetadata, schema: XMPRightsManagementSchema
) -> None:
    """Translated from upstream ``testElementProperty`` for the Boolean row."""
    from pypdfbox.xmpbox import BooleanType
    prop = BooleanType(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.MARKED,
        True,
    )
    schema.set_marked_property(prop)
    fetched = schema.get_marked_property()
    assert fetched is not None
    assert fetched.get_value() is True


def test_unset_initial_state(schema: XMPRightsManagementSchema) -> None:
    """Mirror of upstream's ``XMPSchemaTester#testGetSetValue`` null
    branch — every property reads as ``None`` on a fresh schema."""
    assert schema.get_certificate() is None
    assert schema.get_marked() is None
    assert schema.get_owners() is None
    assert schema.get_usage_terms() is None
    assert schema.get_web_statement() is None
    # Typed accessors mirror the string-form null state.
    assert schema.get_certificate_property() is None
    assert schema.get_marked_property() is None
    assert schema.get_owners_property() is None
    assert schema.get_usage_terms_property() is None
    assert schema.get_web_statement_property() is None
