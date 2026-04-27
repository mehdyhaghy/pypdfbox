from __future__ import annotations

from pypdfbox.xmpbox import (
    DomXmpParser,
    XMPMediaManagementSchema,
    XMPMetadata,
)


def _mm() -> XMPMediaManagementSchema:
    return XMPMediaManagementSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _mm()
    assert XMPMediaManagementSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/mm/"
    assert XMPMediaManagementSchema.PREFERRED_PREFIX == "xmpMM"
    assert schema.get_namespace() == "http://ns.adobe.com/xap/1.0/mm/"
    assert schema.get_prefix() == "xmpMM"


def test_default_accessors_return_none() -> None:
    schema = _mm()
    assert schema.get_document_id() is None
    assert schema.get_instance_id() is None
    assert schema.get_original_document_id() is None
    assert schema.get_version_id() is None
    assert schema.get_rendition_class() is None
    assert schema.get_rendition_params() is None
    assert schema.get_manage_to() is None
    assert schema.get_manage_ui() is None
    assert schema.get_manager() is None
    assert schema.get_manager_variant() is None


def test_round_trip_each_accessor() -> None:
    schema = _mm()
    schema.set_document_id("uuid:doc-1")
    schema.set_instance_id("uuid:inst-1")
    schema.set_original_document_id("uuid:orig-1")
    schema.set_version_id("v1")
    schema.set_rendition_class("default")
    schema.set_rendition_params("dpi=300")
    schema.set_manage_to("https://dam.example.com/asset/42")
    schema.set_manage_ui("https://dam.example.com/ui/asset/42")
    schema.set_manager("Acme DAM")
    schema.set_manager_variant("enterprise")

    assert schema.get_document_id() == "uuid:doc-1"
    assert schema.get_instance_id() == "uuid:inst-1"
    assert schema.get_original_document_id() == "uuid:orig-1"
    assert schema.get_version_id() == "v1"
    assert schema.get_rendition_class() == "default"
    assert schema.get_rendition_params() == "dpi=300"
    assert schema.get_manage_to() == "https://dam.example.com/asset/42"
    assert schema.get_manage_ui() == "https://dam.example.com/ui/asset/42"
    assert schema.get_manager() == "Acme DAM"
    assert schema.get_manager_variant() == "enterprise"

    # set_*(None) clears the property.
    schema.set_document_id(None)
    schema.set_instance_id(None)
    schema.set_original_document_id(None)
    schema.set_version_id(None)
    schema.set_rendition_class(None)
    schema.set_rendition_params(None)
    schema.set_manage_to(None)
    schema.set_manage_ui(None)
    schema.set_manager(None)
    schema.set_manager_variant(None)

    assert schema.get_document_id() is None
    assert schema.get_instance_id() is None
    assert schema.get_original_document_id() is None
    assert schema.get_version_id() is None
    assert schema.get_rendition_class() is None
    assert schema.get_rendition_params() is None
    assert schema.get_manage_to() is None
    assert schema.get_manage_ui() is None
    assert schema.get_manager() is None
    assert schema.get_manager_variant() is None


def test_local_name_constants_match_upstream() -> None:
    assert XMPMediaManagementSchema.DOCUMENT_ID == "DocumentID"
    assert XMPMediaManagementSchema.INSTANCE_ID == "InstanceID"
    assert XMPMediaManagementSchema.ORIGINAL_DOCUMENT_ID == "OriginalDocumentID"
    assert XMPMediaManagementSchema.VERSION_ID == "VersionID"
    assert XMPMediaManagementSchema.RENDITION_CLASS == "RenditionClass"
    assert XMPMediaManagementSchema.RENDITION_PARAMS == "RenditionParams"
    assert XMPMediaManagementSchema.MANAGE_TO == "ManageTo"
    assert XMPMediaManagementSchema.MANAGE_UI == "ManageUI"
    assert XMPMediaManagementSchema.MANAGER == "Manager"
    assert XMPMediaManagementSchema.MANAGER_VARIANT == "ManagerVariant"


def test_round_trip_through_xmp_packet() -> None:
    # Hand-rolled XMP packet — exercises the parser path: attribute-form
    # xmpMM:* properties land on the typed schema via the registry.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpMM='http://ns.adobe.com/xap/1.0/mm/'"
        b" xmpMM:DocumentID='urn:foo'"
        b" xmpMM:InstanceID='urn:bar'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPMediaManagementSchema)
    assert isinstance(schema, XMPMediaManagementSchema)
    assert schema.get_document_id() == "urn:foo"
    assert schema.get_instance_id() == "urn:bar"
    # The convenience accessor finds the same schema instance.
    assert metadata.get_xmp_media_management_schema() is schema


def test_parser_dispatches_element_form_property() -> None:
    # Element-form property variant — the parser should also route
    # <xmpMM:DocumentID>...</xmpMM:DocumentID> onto the typed schema.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpMM='http://ns.adobe.com/xap/1.0/mm/'>"
        b"<xmpMM:DocumentID>urn:doc-element</xmpMM:DocumentID>"
        b"<xmpMM:RenditionClass>proof</xmpMM:RenditionClass>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPMediaManagementSchema)
    assert isinstance(schema, XMPMediaManagementSchema)
    assert schema.get_document_id() == "urn:doc-element"
    assert schema.get_rendition_class() == "proof"


def test_xmp_metadata_add_returns_typed_wrapper() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_xmp_media_management_schema() is None

    schema = metadata.add_xmp_media_management_schema()
    assert isinstance(schema, XMPMediaManagementSchema)
    # Idempotent: a second add returns the same instance.
    assert metadata.add_xmp_media_management_schema() is schema
    assert metadata.get_xmp_media_management_schema() is schema
