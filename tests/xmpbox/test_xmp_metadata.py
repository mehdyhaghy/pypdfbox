from __future__ import annotations

from pypdfbox.xmpbox import DublinCoreSchema, XMPBasicSchema, XMPMetadata, XMPSchema


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
