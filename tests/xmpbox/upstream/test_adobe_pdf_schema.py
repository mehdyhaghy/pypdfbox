"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/AdobePDFTest.java

The upstream parameterized tests (``testElementValue`` /
``testElementProperty``) drive ``XMPSchemaTester``, which in turn exercises
the ``TextType`` / ``PropertyType`` system that has not landed in this
cluster. They are translated to a single parametrised round-trip check that
covers the same three properties (Keywords, PDFVersion, Producer); the
property-object variant is deferred until the type system is ported.

The upstream ``testBadPDFAConformanceId`` test exercises
``PDFAIdentificationSchema`` and is covered by that module's tests rather
than here.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import AdobePDFSchema, XMPMetadata


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
