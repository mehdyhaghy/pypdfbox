"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/AdobePDFTest.java

The upstream parameterized tests (``testElementValue`` /
``testElementProperty``) drive ``XMPSchemaTester``, which in turn exercises
the ``TextType`` / ``PropertyType`` system. With Wave 31's typed-property
foundation in place and Wave 32's typed accessors landed on
:class:`AdobePDFSchema`, both halves of the upstream test matrix are now
translatable: ``test_element_value`` covers the string-form pathway and
``test_element_property`` covers the typed-form pathway.

The upstream ``testBadPDFAConformanceId`` test exercises
``PDFAIdentificationSchema`` and is covered by that module's tests rather
than here.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import AdobePDFSchema, TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> AdobePDFSchema:
    return metadata.create_and_add_adobe_pdf_schema()


@pytest.mark.parametrize(
    ("local_name", "value"),
    [
        ("Keywords", "kw1 kw2 kw3"),
        ("PDFVersion", "1.4"),
        ("Producer", "testcase"),
    ],
)
def test_element_value(schema: AdobePDFSchema, local_name: str, value: str) -> None:
    schema.set_text_property_value(local_name, value)
    assert schema.get_unqualified_text_property_value(local_name) == value


@pytest.mark.parametrize(
    ("local_name", "value", "set_attr", "get_attr"),
    [
        ("Keywords", "kw1 kw2 kw3", "set_keywords_property", "get_keywords_property"),
        ("PDFVersion", "1.4", "set_pdf_version_property", "get_pdf_version_property"),
        ("Producer", "testcase", "set_producer_property", "get_producer_property"),
    ],
)
def test_element_property(
    metadata: XMPMetadata,
    schema: AdobePDFSchema,
    local_name: str,
    value: str,
    set_attr: str,
    get_attr: str,
) -> None:
    """Mirrors upstream ``XMPSchemaTester#testElementProperty`` — build a
    ``TextType`` instance, set it via the typed setter, retrieve it via the
    typed getter, and assert the round-tripped value matches."""
    prop = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        local_name,
        value,
    )
    getattr(schema, set_attr)(prop)
    fetched = getattr(schema, get_attr)()
    assert fetched is not None
    assert isinstance(fetched, TextType)
    assert fetched.get_value() == value
    assert fetched.get_property_name() == local_name


def test_pdfa_identification(metadata: XMPMetadata) -> None:
    schem = metadata.create_and_add_adobe_pdf_schema()

    keywords = "keywords ihih"
    pdf_version = "1.4"
    producer = "producer"

    schem.set_keywords(keywords)
    schem.set_pdf_version(pdf_version)

    assert schem.get_producer() is None

    schem.set_producer(producer)

    assert schem.get_prefix() == "pdf"
    assert schem.get_keywords() == keywords

    assert schem.get_prefix() == "pdf"
    assert schem.get_pdf_version() == pdf_version

    assert schem.get_prefix() == "pdf"
    assert schem.get_producer() == producer
