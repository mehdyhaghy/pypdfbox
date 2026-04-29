from __future__ import annotations

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DomXmpParser,
    ProperNameType,
    XMPMetadata,
    XMPRightsManagementSchema,
)


def _rights() -> XMPRightsManagementSchema:
    return XMPRightsManagementSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _rights()
    assert XMPRightsManagementSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/rights/"
    assert XMPRightsManagementSchema.PREFERRED_PREFIX == "xmpRights"
    assert schema.get_namespace() == "http://ns.adobe.com/xap/1.0/rights/"
    assert schema.get_prefix() == "xmpRights"


def test_default_accessors_return_none() -> None:
    schema = _rights()
    assert schema.get_certificate() is None
    assert schema.get_marked() is None
    assert schema.get_owners() is None
    assert schema.get_usage_terms() is None
    assert schema.get_web_statement() is None


def test_round_trip_each_accessor() -> None:
    schema = _rights()
    schema.set_certificate("https://example.com/cert.crt")
    schema.set_marked(True)
    schema.set_owners(["Alice"])
    schema.set_usage_terms("Use only with permission.")
    schema.set_web_statement("https://example.com/rights")
    assert schema.get_certificate() == "https://example.com/cert.crt"
    assert schema.get_marked() is True
    assert schema.get_owners() == ["Alice"]
    assert schema.get_usage_terms() == "Use only with permission."
    assert schema.get_web_statement() == "https://example.com/rights"

    # set_*(None) clears the property.
    schema.set_certificate(None)
    schema.set_marked(None)
    schema.set_owners(None)
    schema.set_usage_terms(None)
    schema.set_web_statement(None)
    assert schema.get_certificate() is None
    assert schema.get_marked() is None
    assert schema.get_owners() is None
    assert schema.get_usage_terms() is None
    assert schema.get_web_statement() is None


def test_marked_true_false_round_trip() -> None:
    schema = _rights()
    schema.set_marked(True)
    assert schema.get_marked() is True
    schema.set_marked(False)
    assert schema.get_marked() is False
    # None is distinct from False — the property is removed entirely.
    schema.set_marked(None)
    assert schema.get_marked() is None
    assert schema.get_property(XMPRightsManagementSchema.MARKED) is None


def test_marked_parses_lowercase_strings_from_parser() -> None:
    schema = _rights()
    # Parser path: attribute-form properties land as raw strings via
    # ``set_text_property_value``. Accept both capitalised and lowercase forms.
    schema.set_text_property_value(XMPRightsManagementSchema.MARKED, "true")
    assert schema.get_marked() is True
    schema.set_text_property_value(XMPRightsManagementSchema.MARKED, "False")
    assert schema.get_marked() is False
    schema.set_text_property_value(XMPRightsManagementSchema.MARKED, "junk")
    assert schema.get_marked() is None


def test_owners_single_round_trip() -> None:
    schema = _rights()
    schema.add_owner("Alice")
    assert schema.get_owners() == ["Alice"]


def test_owners_multiple_round_trip() -> None:
    schema = _rights()
    schema.add_owner("Alice")
    schema.add_owner("Bob")
    schema.add_owner("Carol")
    assert schema.get_owners() == ["Alice", "Bob", "Carol"]


def test_remove_owner_removes_single_list_entry() -> None:
    schema = _rights()
    schema.add_owner("Alice")
    schema.add_owner("Bob")
    schema.add_owner("Carol")

    schema.remove_owner("Bob")

    assert schema.get_owners() == ["Alice", "Carol"]


def test_remove_owner_ignores_missing_value() -> None:
    schema = _rights()
    schema.add_owner("Alice")

    schema.remove_owner("Bob")

    assert schema.get_owners() == ["Alice"]


def test_remove_owner_handles_typed_array_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPRightsManagementSchema(metadata)
    owners = ArrayProperty(
        metadata,
        XMPRightsManagementSchema.NAMESPACE,
        XMPRightsManagementSchema.PREFERRED_PREFIX,
        XMPRightsManagementSchema.OWNER,
        Cardinality.Bag,
    )
    owners.add_property(
        ProperNameType(
            metadata,
            XMPRightsManagementSchema.NAMESPACE,
            XMPRightsManagementSchema.PREFERRED_PREFIX,
            XMPRightsManagementSchema.OWNER,
            "Alice",
        )
    )
    owners.add_property(
        ProperNameType(
            metadata,
            XMPRightsManagementSchema.NAMESPACE,
            XMPRightsManagementSchema.PREFERRED_PREFIX,
            XMPRightsManagementSchema.OWNER,
            "Bob",
        )
    )
    schema.set_property(XMPRightsManagementSchema.OWNER, owners)

    schema.remove_owner("Alice")

    assert schema.get_owners() == ["Bob"]
    prop = schema.get_property(XMPRightsManagementSchema.OWNER)
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() is Cardinality.Bag


def test_set_owners_replaces_existing_bag() -> None:
    schema = _rights()
    schema.add_owner("Alice")
    schema.set_owners(["Bob", "Carol"])
    assert schema.get_owners() == ["Bob", "Carol"]


def test_usage_terms_with_explicit_lang() -> None:
    schema = _rights()
    schema.set_usage_terms("Use only with permission.", lang="en")
    schema.set_usage_terms("Utilisation soumise a autorisation.", lang="fr")
    assert schema.get_usage_terms("en") == "Use only with permission."
    assert schema.get_usage_terms("fr") == "Utilisation soumise a autorisation."
    # Default lang fetch falls back to ``x-default`` and is absent here.
    assert schema.get_usage_terms() is None


def test_usage_terms_default_lang_is_x_default() -> None:
    schema = _rights()
    schema.set_usage_terms("Default text.")
    assert schema.get_usage_terms() == "Default text."
    assert schema.get_usage_terms("x-default") == "Default text."


def test_dom_parser_dispatches_marked_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpRights='http://ns.adobe.com/xap/1.0/rights/'"
        b" xmpRights:Marked='True'"
        b" xmpRights:WebStatement='https://example.com/rights'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPRightsManagementSchema)
    assert isinstance(schema, XMPRightsManagementSchema)
    assert schema.get_marked() is True
    assert schema.get_web_statement() == "https://example.com/rights"


def test_dom_parser_dispatches_owner_bag_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpRights='http://ns.adobe.com/xap/1.0/rights/'>"
        b"<xmpRights:Owner>"
        b"<rdf:Bag>"
        b"<rdf:li>Alice</rdf:li>"
        b"<rdf:li>Bob</rdf:li>"
        b"</rdf:Bag>"
        b"</xmpRights:Owner>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPRightsManagementSchema)
    assert isinstance(schema, XMPRightsManagementSchema)
    assert schema.get_owners() == ["Alice", "Bob"]


def test_xmp_metadata_get_xmp_rights_management_schema_returns_typed_wrapper() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    # Empty by default.
    assert metadata.get_xmp_rights_management_schema() is None
    schema = metadata.add_xmp_rights_management_schema()
    assert isinstance(schema, XMPRightsManagementSchema)
    # Idempotent — repeat add returns the same instance.
    assert metadata.add_xmp_rights_management_schema() is schema
    assert metadata.get_xmp_rights_management_schema() is schema


def test_dom_parser_get_namespace_table_includes_xmp_rights() -> None:
    table = DomXmpParser().get_namespace_table()
    assert table.get("xmpRights") == "http://ns.adobe.com/xap/1.0/rights/"
