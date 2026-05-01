from __future__ import annotations

from pypdfbox.xmpbox import (
    PDFAExtensionSchema,
    XMPMetadata,
)


def _ext() -> PDFAExtensionSchema:
    return PDFAExtensionSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _ext()
    assert PDFAExtensionSchema.NAMESPACE == "http://www.aiim.org/pdfa/ns/extension/"
    assert PDFAExtensionSchema.PREFERRED_PREFIX == "pdfaExtension"
    assert schema.get_namespace() == "http://www.aiim.org/pdfa/ns/extension/"
    assert schema.get_prefix() == "pdfaExtension"


def test_nested_namespace_constants_match_upstream() -> None:
    assert PDFAExtensionSchema.PDFASCHEMA_NAMESPACE == "http://www.aiim.org/pdfa/ns/schema#"
    assert PDFAExtensionSchema.PDFASCHEMA_PREFIX == "pdfaSchema"
    assert PDFAExtensionSchema.PDFAPROPERTY_NAMESPACE == "http://www.aiim.org/pdfa/ns/property#"
    assert PDFAExtensionSchema.PDFAPROPERTY_PREFIX == "pdfaProperty"
    assert PDFAExtensionSchema.PDFATYPE_NAMESPACE == "http://www.aiim.org/pdfa/ns/type#"
    assert PDFAExtensionSchema.PDFATYPE_PREFIX == "pdfaType"


def test_default_get_extension_schemas_is_empty_list() -> None:
    schema = _ext()
    assert schema.get_extension_schemas() == []


def test_default_get_count_is_zero() -> None:
    schema = _ext()
    assert schema.get_count() == 0


def test_default_get_schemas_element_is_none() -> None:
    schema = _ext()
    assert schema.get_schemas_element() is None


def test_add_then_get_round_trips_single_entry() -> None:
    schema = _ext()
    schema.add_extension_schema(
        schema="My Custom Schema",
        namespace_uri="http://example.com/ns/custom/",
        prefix="custom",
    )
    entries = schema.get_extension_schemas()
    assert len(entries) == 1
    assert entries[0]["schema"] == "My Custom Schema"
    assert entries[0]["namespaceURI"] == "http://example.com/ns/custom/"
    assert entries[0]["prefix"] == "custom"
    assert schema.get_count() == 1


def test_add_two_entries_round_trip_preserves_order() -> None:
    schema = _ext()
    schema.add_extension_schema(
        "First Schema", "http://example.com/ns/first/", "first"
    )
    schema.add_extension_schema(
        "Second Schema", "http://example.com/ns/second/", "second"
    )
    entries = schema.get_extension_schemas()
    assert len(entries) == 2
    assert schema.get_count() == 2
    assert entries[0]["schema"] == "First Schema"
    assert entries[0]["namespaceURI"] == "http://example.com/ns/first/"
    assert entries[0]["prefix"] == "first"
    assert entries[1]["schema"] == "Second Schema"
    assert entries[1]["namespaceURI"] == "http://example.com/ns/second/"
    assert entries[1]["prefix"] == "second"


def test_get_extension_schemas_returns_defensive_copy() -> None:
    schema = _ext()
    schema.add_extension_schema("Initial", "http://example.com/ns/initial/", "init")
    snapshot = schema.get_extension_schemas()
    snapshot.append({"schema": "Bogus", "namespaceURI": "x", "prefix": "y"})
    snapshot[0]["schema"] = "Mutated"
    # Internal state must be untouched by mutations on the returned copy.
    fresh = schema.get_extension_schemas()
    assert len(fresh) == 1
    assert fresh[0]["schema"] == "Initial"


def test_get_schemas_element_after_add_exposes_backing_list() -> None:
    schema = _ext()
    schema.add_extension_schema("Demo", "http://example.com/ns/demo/", "demo")
    raw = schema.get_schemas_element()
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["schema"] == "Demo"


def test_nested_namespaces_registered_on_construction() -> None:
    schema = _ext()
    namespaces = schema.get_namespaces()
    assert namespaces[PDFAExtensionSchema.PREFERRED_PREFIX] == PDFAExtensionSchema.NAMESPACE
    assert (
        namespaces[PDFAExtensionSchema.PDFASCHEMA_PREFIX]
        == PDFAExtensionSchema.PDFASCHEMA_NAMESPACE
    )
    assert (
        namespaces[PDFAExtensionSchema.PDFAPROPERTY_PREFIX]
        == PDFAExtensionSchema.PDFAPROPERTY_NAMESPACE
    )
    assert (
        namespaces[PDFAExtensionSchema.PDFATYPE_PREFIX]
        == PDFAExtensionSchema.PDFATYPE_NAMESPACE
    )


def test_xmp_metadata_get_pdfa_extension_schema_returns_typed_wrapper() -> None:
    # Wave 24 left this as a None placeholder; wave-25 replaces with the real
    # typed accessor that materialises a PDFAExtensionSchema on demand.
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_pdfa_extension_schema() is None
    schema = metadata.add_pdfa_extension_schema()
    assert isinstance(schema, PDFAExtensionSchema)
    # Idempotent: subsequent fetches return the same instance.
    assert metadata.get_pdfa_extension_schema() is schema
    assert metadata.add_pdfa_extension_schema() is schema


def test_xmp_metadata_add_pdf_extension_schema_alias() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.add_pdf_extension_schema()
    assert isinstance(schema, PDFAExtensionSchema)
    assert metadata.get_pdfa_extension_schema() is schema


def test_get_schemas_property_alias_of_get_schemas_element() -> None:
    """Mirror of upstream ``getSchemasProperty()`` — returns whatever
    backs ``pdfaExtension:schemas`` (``None`` when absent, otherwise the
    same object :meth:`get_schemas_element` returns)."""
    schema = _ext()
    # Default: no schemas declared yet.
    assert schema.get_schemas_property() is None
    schema.add_extension_schema("Demo", "http://example.com/ns/demo/", "demo")
    assert schema.get_schemas_property() is schema.get_schemas_element()
    raw = schema.get_schemas_property()
    assert isinstance(raw, list)
    assert len(raw) == 1


def test_xmp_metadata_create_and_add_pdfa_extension_schema_with_default_ns() -> None:
    """Mirror of upstream ``createAndAddPDFAExtensionSchemaWithDefaultNS``."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_pdfa_extension_schema_with_default_ns()
    assert isinstance(schema, PDFAExtensionSchema)
    assert metadata.get_pdfa_extension_schema() is schema
    # Default nested namespaces are registered.
    namespaces = schema.get_namespaces()
    assert (
        namespaces[PDFAExtensionSchema.PDFASCHEMA_PREFIX]
        == PDFAExtensionSchema.PDFASCHEMA_NAMESPACE
    )


def test_xmp_metadata_create_and_add_pdfa_extension_schema_with_ns_adds_extras() -> None:
    """Mirror of upstream ``createAndAddPDFAExtensionSchemaWithNS(Map)``."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_pdfa_extension_schema_with_ns(
        {"custom": "http://example.com/ns/custom/"}
    )
    assert isinstance(schema, PDFAExtensionSchema)
    namespaces = schema.get_namespaces()
    # User-supplied binding is registered.
    assert namespaces["custom"] == "http://example.com/ns/custom/"
    # Default nested-struct namespaces are still present.
    assert (
        namespaces[PDFAExtensionSchema.PDFASCHEMA_PREFIX]
        == PDFAExtensionSchema.PDFASCHEMA_NAMESPACE
    )


def test_xmp_metadata_create_and_add_pdfa_extension_schema_with_ns_accepts_none() -> None:
    """Passing ``None`` (or an empty dict) is the same as the default-NS form."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_pdfa_extension_schema_with_ns(None)
    assert isinstance(schema, PDFAExtensionSchema)
    assert metadata.get_pdfa_extension_schema() is schema


def test_xmp_metadata_get_pdf_extension_schema_alias() -> None:
    """Mirror of upstream ``getPDFExtensionSchema`` — the alternate spelling
    upstream uses for this accessor."""
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_pdf_extension_schema() is None
    schema = metadata.add_pdfa_extension_schema()
    assert metadata.get_pdf_extension_schema() is schema


def test_dispatch_via_parser_creates_typed_wrapper() -> None:
    # A packet whose only schema is pdfaExtension:schemas (Bag of structs)
    # should dispatch to PDFAExtensionSchema via the registry, even though the
    # parser's struct decoding is deferred.
    from pypdfbox.xmpbox import DomXmpParser

    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfaExtension='http://www.aiim.org/pdfa/ns/extension/'"
        b" xmlns:pdfaSchema='http://www.aiim.org/pdfa/ns/schema#'>"
        b"<pdfaExtension:schemas><rdf:Bag>"
        b"<rdf:li rdf:parseType='Resource'>"
        b"<pdfaSchema:schema>Demo</pdfaSchema:schema>"
        b"<pdfaSchema:namespaceURI>http://example.com/ns/demo/</pdfaSchema:namespaceURI>"
        b"<pdfaSchema:prefix>demo</pdfaSchema:prefix>"
        b"</rdf:li>"
        b"</rdf:Bag></pdfaExtension:schemas>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_pdfa_extension_schema()
    assert isinstance(schema, PDFAExtensionSchema)
