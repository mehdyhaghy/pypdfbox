"""Branch-coverage round-out (wave 1367) for ``XMPRightsManagementSchema``.

Pins typed-instance / string-form interop, the BooleanType marked flag
parsing fallbacks, owner bag ArrayProperty removal, and UsageTerms
LangAlt language-listing behavior.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type import (
    ArrayProperty,
    BooleanType,
    Cardinality,
    LangAlt,
    ProperNameType,
    TextType,
    URIType,
)
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from pypdfbox.xmpbox.xmp_rights_management_schema import XMPRightsManagementSchema


@pytest.fixture()
def schema() -> XMPRightsManagementSchema:
    return XMPRightsManagementSchema(XMPMetadata.create_xmp_metadata())


def test_certificate_string_then_typed_property(
    schema: XMPRightsManagementSchema,
) -> None:
    schema.set_certificate("http://example.org/cert")
    # Typed getter must wrap the plain string into a URIType.
    typed = schema.get_certificate_property()
    assert isinstance(typed, URIType)
    assert typed.get_string_value() == "http://example.org/cert"


def test_certificate_typed_setter_round_trip(
    schema: XMPRightsManagementSchema,
) -> None:
    uri = URIType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.CERTIFICATE,
        "http://example.org/typed-cert",
    )
    schema.set_certificate_property(uri)
    assert schema.get_certificate() == "http://example.org/typed-cert"


def test_marked_true_false_round_trip(schema: XMPRightsManagementSchema) -> None:
    schema.set_marked(True)
    assert schema.get_marked() is True
    schema.set_marked(False)
    assert schema.get_marked() is False
    schema.set_marked(None)
    assert schema.get_marked() is None


def test_marked_string_fallback_parsing(schema: XMPRightsManagementSchema) -> None:
    # Direct-store a string that needs the lower()/strip() normalizer path.
    schema.set_property(XMPRightsManagementSchema.MARKED, "  TRUE ")
    assert schema.get_marked() is True
    schema.set_property(XMPRightsManagementSchema.MARKED, "False")
    assert schema.get_marked() is False
    # Unknown value -> None (matches upstream "absent" treatment).
    schema.set_property(XMPRightsManagementSchema.MARKED, "maybe")
    assert schema.get_marked() is None


def test_marked_typed_setter_round_trip(schema: XMPRightsManagementSchema) -> None:
    boolean = BooleanType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.MARKED,
        True,
    )
    schema.set_marked_property(boolean)
    assert schema.get_marked() is True
    typed = schema.get_marked_property()
    assert isinstance(typed, BooleanType)
    assert typed.get_value() is True


def test_owner_bag_add_remove(schema: XMPRightsManagementSchema) -> None:
    schema.add_owner("Acme Corp")
    schema.add_owner("Globex")
    schema.add_owner("Initech")
    schema.remove_owner("Globex")
    assert schema.get_owners() == ["Acme Corp", "Initech"]


def test_remove_owner_from_array_property_path(
    schema: XMPRightsManagementSchema,
) -> None:
    # Install an ArrayProperty directly so remove_owner routes through the
    # ArrayProperty filter branch rather than the list branch.
    array = ArrayProperty(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.OWNER,
        Cardinality.Bag,
    )
    for name in ("One", "Two", "Three"):
        array.add_property(
            ProperNameType(
                schema.get_metadata(),
                schema.get_namespace(),
                schema.get_prefix(),
                XMPRightsManagementSchema.OWNER,
                name,
            )
        )
    schema.set_owners_property(array)
    schema.remove_owner("Two")
    assert schema.get_owners() == ["One", "Three"]


def test_set_owners_with_none_clears(schema: XMPRightsManagementSchema) -> None:
    schema.add_owner("A")
    schema.set_owners(None)
    assert schema.get_owners() is None


def test_usage_terms_lang_alt_languages(schema: XMPRightsManagementSchema) -> None:
    schema.set_usage_terms("Free to use")
    schema.add_usage_terms("fr", "Libre d'utilisation")
    langs = schema.get_usage_terms_languages()
    assert langs is not None
    assert "x-default" in langs
    assert "fr" in langs


def test_usage_terms_typed_property_round_trip(
    schema: XMPRightsManagementSchema,
) -> None:
    la = LangAlt(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.USAGE_TERMS,
    )
    la.set_language_value("x-default", "Default terms")
    la.set_language_value("es", "Terminos por defecto")
    schema.set_usage_terms_property(la)
    assert schema.get_usage_terms() == "Default terms"
    assert schema.get_usage_terms("es") == "Terminos por defecto"


def test_set_certificate_with_none_removes(
    schema: XMPRightsManagementSchema,
) -> None:
    schema.set_certificate("http://x")
    schema.set_certificate(None)
    assert schema.get_certificate() is None
    assert schema.get_certificate_property() is None


def test_web_statement_typed_view_after_string_setter(
    schema: XMPRightsManagementSchema,
) -> None:
    schema.set_web_statement("http://example.org/web")
    typed = schema.get_web_statement_property()
    assert isinstance(typed, URIType)
    # The typed-set companion must also work.
    other = URIType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.WEB_STATEMENT,
        "http://example.org/other",
    )
    schema.set_web_statement_property(other)
    assert schema.get_web_statement() == "http://example.org/other"


def test_owners_property_synthesized_from_legacy_list(
    schema: XMPRightsManagementSchema,
) -> None:
    schema.add_owner("X")
    schema.add_owner("Y")
    array = schema.get_owners_property()
    assert isinstance(array, ArrayProperty)
    assert array.get_array_type() == Cardinality.Bag
    children = array.get_all_properties()
    assert all(isinstance(c, ProperNameType) for c in children)


def test_text_type_certificate_cross_wraps_to_uri(
    schema: XMPRightsManagementSchema,
) -> None:
    # Direct-install a TextType then request the URIType form — typed-get
    # should re-wrap.
    text = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        XMPRightsManagementSchema.CERTIFICATE,
        "http://example.org/cross",
    )
    schema.set_property(XMPRightsManagementSchema.CERTIFICATE, text)
    typed = schema.get_certificate_property()
    assert isinstance(typed, URIType)
    assert typed.get_string_value() == "http://example.org/cross"
