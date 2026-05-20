"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/AdobePDFTest.java

Upstream drives ``testElementValue`` / ``testElementProperty`` through the
``XMPSchemaTester`` reflection helper over three (property, type, value)
tuples. The Python translation enumerates the same three tuples directly
and round-trips them via :class:`AdobePDFSchema`'s typed accessors.

``testBadPDFAConformanceId`` belongs to :class:`PDFAIdentificationSchema`
and is covered by ``test_pdfa_identification_others.py``; the upstream
test merely happens to live in this file, so it is not duplicated here.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import AdobePDFSchema, TextType, XMPMetadata

# Mirrors upstream ``initializeParameters()`` — kept verbatim for re-syncs.
_PARAMETERS: tuple[tuple[str, str], ...] = (
    ("Keywords", "kw1 kw2 kw3"),
    ("PDFVersion", "1.4"),
    ("Producer", "testcase"),
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> AdobePDFSchema:
    return metadata.create_and_add_adobe_pdf_schema()


@pytest.mark.parametrize(("local_name", "value"), _PARAMETERS)
def test_element_value(schema: AdobePDFSchema, local_name: str, value: str) -> None:
    """Translated from upstream ``testElementValue`` — set the property
    by string value via the generic ``set_text_property_value`` helper
    and read it back through ``get_unqualified_text_property_value``."""
    schema.set_text_property_value(local_name, value)
    assert schema.get_unqualified_text_property_value(local_name) == value


@pytest.mark.parametrize(("local_name", "value"), _PARAMETERS)
def test_element_property(
    metadata: XMPMetadata,
    schema: AdobePDFSchema,
    local_name: str,
    value: str,
) -> None:
    """Translated from upstream ``testElementProperty`` — construct a
    :class:`TextType`, install via the typed setter, retrieve via the
    typed getter, and assert the round-tripped property name + value."""
    prop = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        local_name,
        value,
    )
    # Map local-name to the typed setter / getter pair on AdobePDFSchema.
    setter_name = {
        "Keywords": "set_keywords_property",
        "PDFVersion": "set_pdf_version_property",
        "Producer": "set_producer_property",
    }[local_name]
    getter_name = {
        "Keywords": "get_keywords_property",
        "PDFVersion": "get_pdf_version_property",
        "Producer": "get_producer_property",
    }[local_name]
    getattr(schema, setter_name)(prop)
    fetched = getattr(schema, getter_name)()
    assert fetched is not None
    assert isinstance(fetched, TextType)
    assert fetched.get_value() == value
    assert fetched.get_property_name() == local_name


def test_pdfa_identification() -> None:
    """Translated from upstream ``testPDFAIdentification`` —
    string-form setters round-trip through both the simple and typed
    getters; ``getProducer()`` returns ``None`` until explicitly set."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_adobe_pdf_schema()

    keywords = "keywords ihih"
    pdf_version = "1.4"
    producer = "producer"

    schema.set_keywords(keywords)
    schema.set_pdf_version(pdf_version)

    # Mirror upstream's null-check before producer is set.
    assert schema.get_producer() is None

    schema.set_producer(producer)

    assert schema.get_prefix() == "pdf"
    assert schema.get_keywords() == keywords

    assert schema.get_prefix() == "pdf"
    assert schema.get_pdf_version() == pdf_version

    assert schema.get_prefix() == "pdf"
    assert schema.get_producer() == producer
