from __future__ import annotations

from pypdfbox.xmpbox import DublinCoreSchema, XMPBasicSchema, XMPMetadata, XMPSchema
from pypdfbox.xmpbox import xmp_metadata as xmp_constants


def test_create_xmp_metadata_uses_defaults() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.get_xpacket_id() == "W5M0MpCehiHzreSzNTczkc9d"
    assert meta.get_xpacket_encoding() == "UTF-8"
    assert meta.get_end_xpacket() == "w"
    assert meta.get_all_schemas() == []


def test_custom_xpacket_attributes_round_trip() -> None:
    meta = XMPMetadata(
        xpacket_begin="",
        xpacket_id="custom-id",
        xpacket_bytes="100",
        xpacket_encoding="UTF-16",
        xpacket_end="r",
    )
    assert meta.get_xpacket_begin() == ""
    assert meta.get_xpacket_id() == "custom-id"
    assert meta.get_xpacket_bytes() == "100"
    assert meta.get_xpacket_encoding() == "UTF-16"
    assert meta.get_end_xpacket() == "r"
    meta.set_end_xpacket("w")
    assert meta.get_end_xpacket() == "w"


def test_add_and_get_schema_by_namespace() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    dc = DublinCoreSchema(meta)
    meta.add_schema(dc)
    assert meta.get_schema(DublinCoreSchema.NAMESPACE) is dc
    assert meta.get_schema("http://example.com/missing") is None


def test_get_schema_by_class() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    dc = DublinCoreSchema(meta)
    basic = XMPBasicSchema(meta)
    meta.add_schema(dc)
    meta.add_schema(basic)
    assert meta.get_schema(DublinCoreSchema) is dc
    assert meta.get_schema(XMPBasicSchema) is basic
    assert meta.get_dublin_core_schema() is dc
    assert meta.get_xmp_basic_schema() is basic


def test_get_schema_by_prefix_disambiguates_duplicates() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    dc1 = DublinCoreSchema(meta, own_prefix="dc")
    dc2 = DublinCoreSchema(meta, own_prefix="alt")
    meta.add_schema(dc1)
    meta.add_schema(dc2)
    assert meta.get_schema_by_prefix("dc", DublinCoreSchema.NAMESPACE) is dc1
    assert meta.get_schema_by_prefix("alt", DublinCoreSchema.NAMESPACE) is dc2


def test_get_all_schemas_returns_defensive_copy() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = XMPSchema(meta, namespace_uri="http://example.com/ns#", prefix="ex")
    meta.add_schema(schema)
    snapshot = meta.get_all_schemas()
    snapshot.clear()
    assert meta.get_all_schemas() == [schema]


def test_xmp_constants_rdf_wire_names() -> None:
    """Mirror of upstream ``org.apache.xmpbox.XmpConstants``: the seven
    RDF wire-format local names live alongside the rest of the
    constants in :mod:`pypdfbox.xmpbox.xmp_metadata`."""
    assert xmp_constants.LIST_NAME == "li"
    assert xmp_constants.LANG_NAME == "lang"
    assert xmp_constants.ABOUT_NAME == "about"
    assert xmp_constants.DESCRIPTION_NAME == "Description"
    assert xmp_constants.RESOURCE_NAME == "Resource"
    assert xmp_constants.PARSE_TYPE == "parseType"
    assert xmp_constants.X_DEFAULT == "x-default"


def test_xmp_constants_existing_constants_unchanged() -> None:
    """Sanity check that adding the wire-name constants did not move
    the older RDF / xpacket constants."""
    assert (
        xmp_constants.RDF_NAMESPACE
        == "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    )
    assert xmp_constants.DEFAULT_RDF_PREFIX == "rdf"
    assert xmp_constants.DEFAULT_RDF_LOCAL_NAME == "RDF"
    assert xmp_constants.DEFAULT_XPACKET_ID == "W5M0MpCehiHzreSzNTczkc9d"
    assert xmp_constants.DEFAULT_XPACKET_ENCODING == "UTF-8"
    assert xmp_constants.DEFAULT_XPACKET_END == "w"


def test_create_and_add_dublin_core_schema_alias() -> None:
    """Mirror of upstream ``XMPMetadata.createAndAddDublinCoreSchema``: the
    alias delegates to :meth:`add_dublin_core_schema` and is idempotent."""
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.create_and_add_dublin_core_schema()
    assert isinstance(schema, DublinCoreSchema)
    # Repeat call returns the same instance (idempotent like upstream).
    assert meta.create_and_add_dublin_core_schema() is schema
    # Alias and primary share storage.
    assert meta.add_dublin_core_schema() is schema
    assert meta.get_dublin_core_schema() is schema


def test_clear_schemas_drops_every_schema() -> None:
    """Mirror of upstream ``XMPMetadata.clearSchemas``: removes every schema
    and leaves xpacket attributes intact."""
    meta = XMPMetadata.create_xmp_metadata()
    meta.add_dublin_core_schema()
    meta.add_xmp_basic_schema()
    assert len(meta.get_all_schemas()) == 2

    meta.clear_schemas()
    assert meta.get_all_schemas() == []
    # xpacket attributes survive the clear.
    assert meta.get_xpacket_id() == "W5M0MpCehiHzreSzNTczkc9d"
    assert meta.get_xpacket_encoding() == "UTF-8"
    # Idempotent — second clear stays empty.
    meta.clear_schemas()
    assert meta.get_all_schemas() == []


def test_create_and_add_default_schema_returns_plain_schema() -> None:
    """Mirror of upstream ``XMPMetadata.createAndAddDefaultSchema``: produces
    a bare :class:`XMPSchema` for the supplied prefix + namespace."""
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.create_and_add_default_schema("ex", "http://example.com/ns#")
    assert isinstance(schema, XMPSchema)
    assert schema.get_prefix() == "ex"
    assert schema.get_namespace() == "http://example.com/ns#"
    assert schema.get_about() == ""
    assert meta.get_schema("http://example.com/ns#") is schema


def test_create_and_add_default_schema_returns_distinct_instances() -> None:
    """Upstream creates unconditionally — repeat calls produce distinct
    instances (unlike the idempotent ``add_*`` helpers)."""
    meta = XMPMetadata.create_xmp_metadata()
    a = meta.create_and_add_default_schema("ex", "http://example.com/ns#")
    b = meta.create_and_add_default_schema("ex", "http://example.com/ns#")
    assert a is not b
    assert len(meta.get_all_schemas()) == 2


def test_create_and_add_xmp_basic_schema_returns_distinct_instances() -> None:
    """Mirror of upstream ``XMPMetadata.createAndAddXMPBasicSchema``: each
    call installs a fresh schema with ``rdf:about=""``."""
    meta = XMPMetadata.create_xmp_metadata()
    a = meta.create_and_add_xmp_basic_schema()
    b = meta.create_and_add_xmp_basic_schema()
    assert isinstance(a, XMPBasicSchema)
    assert isinstance(b, XMPBasicSchema)
    assert a is not b
    assert a.get_about() == ""
    assert b.get_about() == ""
    # ``get_xmp_basic_schema`` returns the first installed one (upstream
    # ``getSchema(Class)`` semantics).
    assert meta.get_xmp_basic_schema() is a


def test_create_and_add_xmp_media_management_schema_returns_distinct_instances() -> None:
    """Mirror of upstream
    ``XMPMetadata.createAndAddXMPMediaManagementSchema``."""
    from pypdfbox.xmpbox import XMPMediaManagementSchema

    meta = XMPMetadata.create_xmp_metadata()
    a = meta.create_and_add_xmp_media_management_schema()
    b = meta.create_and_add_xmp_media_management_schema()
    assert isinstance(a, XMPMediaManagementSchema)
    assert isinstance(b, XMPMediaManagementSchema)
    assert a is not b
    assert a.get_about() == ""
    assert b.get_about() == ""
    assert meta.get_xmp_media_management_schema() is a
