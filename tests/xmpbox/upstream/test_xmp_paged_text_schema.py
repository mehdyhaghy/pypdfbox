"""
Ported upstream tests for ``org.apache.xmpbox.schema.XMPageTextSchema``.

Upstream (PDFBox 3.0.x ``xmpbox/src/test/java/org/apache/xmpbox/schema/``) does
**not** ship a dedicated ``XMPageTextSchemaTest.java``. Schema coverage
upstream comes via the integration suite that exercises ``XMPMetadata`` end to
end. This file therefore mirrors the smoke-coverage pattern other ported
upstream files use: confirm the structured-type contract upstream's
``@StructuredType`` / ``@PropertyType`` annotations declare for the schema.
"""

from __future__ import annotations

from pypdfbox.xmpbox import (
    XMPMetadata,
    XMPageTextSchema,
)


def test_structured_type_namespace_and_prefix() -> None:
    # @StructuredType(preferedPrefix = "xmpTPg",
    #                 namespace = "http://ns.adobe.com/xap/1.0/t/pg/")
    assert XMPageTextSchema.PREFERRED_PREFIX == "xmpTPg"
    assert XMPageTextSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/t/pg/"


def test_property_local_names_match_upstream_constants() -> None:
    # public static final String MAX_PAGE_SIZE = "MaxPageSize";
    assert XMPageTextSchema.MAX_PAGE_SIZE == "MaxPageSize"
    # public static final String N_PAGES = "NPages";
    assert XMPageTextSchema.N_PAGES == "NPages"
    # public static final String HAS_VISIBLE_TRANSPARENCY = "HasVisibleTransparency";
    assert XMPageTextSchema.HAS_VISIBLE_TRANSPARENCY == "HasVisibleTransparency"
    # public static final String HAS_VISIBLE_OVERPRINT = "HasVisibleOverprint";
    assert XMPageTextSchema.HAS_VISIBLE_OVERPRINT == "HasVisibleOverprint"
    # public static final String PLATENAMES = "PlateNames";
    assert XMPageTextSchema.PLATENAMES == "PlateNames"
    # public static final String COLORANTS = "Colorants";
    assert XMPageTextSchema.COLORANTS == "Colorants"
    # public static final String FONTS = "Fonts";
    assert XMPageTextSchema.FONTS == "Fonts"


def test_constructor_metadata_only() -> None:
    # public XMPageTextSchema(XMPMetadata metadata)
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPageTextSchema(metadata)
    assert schema.get_metadata() is metadata
    assert schema.get_prefix() == "xmpTPg"


def test_constructor_metadata_and_prefix() -> None:
    # public XMPageTextSchema(XMPMetadata metadata, String prefix)
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPageTextSchema(metadata, "myPrefix")
    assert schema.get_metadata() is metadata
    assert schema.get_prefix() == "myPrefix"
    assert schema.get_namespace() == "http://ns.adobe.com/xap/1.0/t/pg/"


def test_xmp_metadata_create_and_add_page_text_schema() -> None:
    # XMPMetadata.createAndAddPageTextSchema()
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_page_text_schema()
    assert isinstance(schema, XMPageTextSchema)
    # createAndAddPageTextSchema sets rdf:about="" via setAboutAsSimple("").
    assert schema.get_about() == ""
    assert metadata.get_page_text_schema() is schema
