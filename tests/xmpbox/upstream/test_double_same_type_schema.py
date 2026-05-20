"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/DoubleSameTypeSchemaTest.java

Two :class:`DublinCoreSchema` instances with the same namespace but
different prefixes must coexist on the same :class:`XMPMetadata`. The
prefix-aware getter ``getSchema(prefix, namespace)`` must dispatch to
the correct one, and ``getAllSchemas()`` must return both.
"""

from __future__ import annotations

from pypdfbox.xmpbox import DublinCoreSchema, XMPMetadata


def test_double_dublin_core() -> None:
    """Translated from upstream ``testDoubleDublinCore``."""
    metadata = XMPMetadata.create_xmp_metadata()
    dc1 = metadata.create_and_add_dublin_core_schema()
    own_prefix = "test"
    dc2 = DublinCoreSchema(metadata, own_prefix=own_prefix)
    metadata.add_schema(dc2)

    creators = ["creator1", "creator2"]

    fmt = "application/pdf"
    dc1.set_format(fmt)
    dc1.add_creator(creators[0])
    dc1.add_creator(creators[1])

    coverage = "Coverage"
    dc2.set_coverage(coverage)
    dc2.add_creator(creators[0])
    dc2.add_creator(creators[1])

    # Upstream uses reflection to read StructuredType annotation values;
    # pypdfbox exposes them as class attributes.
    namespace = DublinCoreSchema.NAMESPACE
    prefered_prefix = DublinCoreSchema.PREFERRED_PREFIX

    # We cannot use metadata.get_dublin_core_schema() due to specification
    # of XMPBox (see Javadoc of XMPMetadata).
    fetched1 = metadata.get_schema_by_prefix(prefered_prefix, namespace)
    assert isinstance(fetched1, DublinCoreSchema)
    assert fetched1.get_format() == fmt

    fetched2 = metadata.get_schema_by_prefix(own_prefix, namespace)
    assert isinstance(fetched2, DublinCoreSchema)
    assert fetched2.get_coverage() == coverage

    # Both schemas should carry both creators.
    for schema in metadata.get_all_schemas():
        if isinstance(schema, DublinCoreSchema):
            schema_creators = schema.get_creators() or []
            for creator in creators:
                assert creator in schema_creators
