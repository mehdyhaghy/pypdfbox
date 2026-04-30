from __future__ import annotations

from pypdfbox.xmpbox import (
    DomXmpParser,
    XMPMediaManagementSchema,
    XMPMetadata,
)
from pypdfbox.xmpbox.type import ResourceEventType, ResourceRefType, VersionType


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
    assert schema.get_versions() is None


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
    assert XMPMediaManagementSchema.VERSIONS == "Versions"


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


def test_derived_from_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    assert schema.get_derived_from() is None
    ref = ResourceRefType(metadata)
    ref.set_document_id("uuid:source-doc")
    ref.set_instance_id("uuid:source-inst")
    schema.set_derived_from(ref)
    same = schema.get_derived_from()
    assert same is ref
    assert same.get_document_id() == "uuid:source-doc"
    schema.set_derived_from(None)
    assert schema.get_derived_from() is None


def test_derived_from_upstream_property_aliases() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    ref = ResourceRefType(metadata)
    ref.set_instance_id("uuid:source-inst")

    schema.set_derived_from_property(ref)

    assert schema.get_resource_ref_property() is ref
    assert schema.get_derived_from() is ref

    schema.set_derived_from_property(None)
    assert schema.get_resource_ref_property() is None


def test_history_seq_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    assert schema.get_history() is None
    e1 = ResourceEventType(metadata)
    e1.set_action("created")
    e2 = ResourceEventType(metadata)
    e2.set_action("converted")
    schema.add_history(e1)
    schema.add_history(e2)
    history = schema.get_history()
    assert history == [e1, e2]


def test_versions_seq_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    assert schema.get_versions() is None
    v1 = VersionType(metadata)
    v1.set_version("1")
    v1.set_modifier("Ada")
    v2 = VersionType(metadata)
    v2.set_version("2")
    v2.set_comments("released")
    schema.add_version(v1)
    schema.add_version(v2)
    versions = schema.get_versions()
    assert versions == [v1, v2]
    assert versions[0].get_modifier() == "Ada"
    assert versions[1].get_comments() == "released"


def test_versions_filters_untyped_entries() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    version = VersionType(metadata)
    version.set_version("1")
    schema.set_property(
        XMPMediaManagementSchema.VERSIONS,
        ["legacy", version, ResourceEventType(metadata)],
    )
    assert schema.get_versions() == [version]


def test_manifest_bag_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    assert schema.get_manifest() is None
    r = ResourceRefType(metadata)
    r.set_document_id("uuid:ingredient")
    schema.add_manifest(r)
    manifest = schema.get_manifest()
    assert manifest == [r]


def test_ingredients_bag_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    assert schema.get_ingredients() is None
    r = ResourceRefType(metadata)
    r.set_document_id("uuid:i1")
    schema.add_ingredient(r)
    ingredients = schema.get_ingredients()
    assert ingredients == [r]


def test_namespace_registration_for_resource_types() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPMediaManagementSchema(metadata)
    namespaces = schema.get_namespaces()
    assert namespaces.get(ResourceRefType.PREFERRED_PREFIX) == ResourceRefType.NAMESPACE
    assert namespaces.get(ResourceEventType.PREFERRED_PREFIX) == ResourceEventType.NAMESPACE
    assert namespaces.get(VersionType.PREFERRED_PREFIX) == VersionType.NAMESPACE
