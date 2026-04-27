"""Parity tests for upstream-named ``XMPMetadata`` accessors."""

from __future__ import annotations

from pypdfbox.xmpbox import (
    DublinCoreSchema,
    PDFAIdentificationSchema,
    XMPBasicSchema,
    XMPMetadata,
    XMPSchema,
)


# --- get_schema(namespace) -----------------------------------------------


def test_get_schema_by_namespace_returns_schema_or_none() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.get_schema(DublinCoreSchema.NAMESPACE) is None
    dc = DublinCoreSchema(meta)
    meta.add_schema(dc)
    assert meta.get_schema(DublinCoreSchema.NAMESPACE) is dc
    assert meta.get_schema("http://example.invalid/missing#") is None


# --- get_all_schemas ------------------------------------------------------


def test_get_all_schemas_returns_list() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.get_all_schemas() == []
    dc = DublinCoreSchema(meta)
    basic = XMPBasicSchema(meta)
    meta.add_schema(dc)
    meta.add_schema(basic)
    schemas = meta.get_all_schemas()
    assert isinstance(schemas, list)
    assert schemas == [dc, basic]


# --- add_schema / remove_schema round-trip --------------------------------


def test_add_remove_schema_round_trip() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = XMPSchema(meta, namespace_uri="http://example.com/ns#", prefix="ex")
    meta.add_schema(schema)
    assert meta.get_schema("http://example.com/ns#") is schema
    meta.remove_schema(schema)
    assert meta.get_schema("http://example.com/ns#") is None
    assert meta.get_all_schemas() == []
    # Removing a schema that was never registered is a no-op (mirrors
    # upstream ``List#remove(Object)``).
    meta.remove_schema(schema)


# --- get_about / set_about ------------------------------------------------


def test_get_about_is_none_for_empty_metadata() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.get_about() is None


def test_set_about_propagates_to_registered_schemas() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    dc = DublinCoreSchema(meta)
    basic = XMPBasicSchema(meta)
    meta.add_schema(dc)
    meta.add_schema(basic)
    meta.set_about("uuid:doc-123")
    assert meta.get_about() == "uuid:doc-123"
    assert dc.get_about() == "uuid:doc-123"
    assert basic.get_about() == "uuid:doc-123"


# --- get_pdfa_identification_schema (typed) -------------------------------


def test_get_pdfa_identification_schema_returns_typed_wrapper_after_add() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.get_pdfa_identification_schema() is None
    schema = meta.add_pdfa_identification_schema()
    assert isinstance(schema, PDFAIdentificationSchema)
    fetched = meta.get_pdfa_identification_schema()
    assert fetched is schema
    # Idempotent — adding twice does not stack duplicates.
    again = meta.add_pdfa_identification_schema()
    assert again is schema
    assert meta.get_all_schemas() == [schema]


# --- typed add accessors --------------------------------------------------


def test_add_dublin_core_schema_returns_typed_wrapper() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_dublin_core_schema()
    assert isinstance(schema, DublinCoreSchema)
    assert meta.get_dublin_core_schema() is schema
    # Idempotent.
    assert meta.add_dublin_core_schema() is schema


def test_add_xmp_basic_schema_returns_typed_wrapper() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_xmp_basic_schema()
    assert isinstance(schema, XMPBasicSchema)
    assert meta.get_xmp_basic_schema() is schema
    assert meta.add_xmp_basic_schema() is schema


# --- placeholder accessors (PDF basic / PDF/A extension) -----------------


def test_pdf_basic_schema_placeholders_return_none_when_absent() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.get_pdf_schema() is None
    assert meta.add_pdf_basic_schema() is None
    assert meta.get_pdfa_extension_schema() is None
    assert meta.add_pdfa_extension_schema() is None
    assert meta.add_pdf_extension_schema() is None


# --- xpacket header setters ----------------------------------------------


def test_xpacket_begin_id_setters_round_trip() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    meta.set_xpacket_begin("")
    meta.set_xpacket_id("custom-id")
    meta.set_xpacket_bytes("100")
    meta.set_xpacket_encoding("UTF-16")
    assert meta.get_xpacket_begin() == ""
    assert meta.get_xpacket_id() == "custom-id"
    assert meta.get_xpacket_bytes() == "100"
    assert meta.get_xpacket_encoding() == "UTF-16"


# --- read-only flag ------------------------------------------------------


def test_read_only_default_false_and_setter_flips_end_marker() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    assert meta.is_read_only() is False
    assert meta.get_end_xpacket() == "w"
    meta.set_read_only(True)
    assert meta.is_read_only() is True
    assert meta.get_end_xpacket() == "r"
    meta.set_read_only(False)
    assert meta.is_read_only() is False
    assert meta.get_end_xpacket() == "w"


def test_set_end_xpacket_keeps_read_only_in_sync() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    meta.set_end_xpacket("r")
    assert meta.is_read_only() is True
    meta.set_end_xpacket("w")
    assert meta.is_read_only() is False
