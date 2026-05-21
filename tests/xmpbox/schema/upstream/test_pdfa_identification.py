"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/PDFAIdentificationTest.java

Upstream drives ``testElementValue`` / ``testElementProperty`` through
``XMPSchemaTester`` over four (property, type, value) tuples. The
pypdfbox port exposes typed accessors (``set_part`` / ``set_amd`` /
``set_conformance`` / ``set_rev`` and the matching ``set_xxx_property``
variants) directly, so the reflection layer collapses to a regular
parametrize. The complementary error-channel tests live in upstream's
``PDFAIdentificationOthersTest.java`` and are translated separately at
``test_pdfa_identification_others.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    IntegerType,
    PDFAIdentificationSchema,
    TextType,
    XMPMetadata,
)

# Mirrors upstream ``initializeParameters()`` — kept verbatim.
_PARAMETERS: tuple[tuple[str, str, object], ...] = (
    ("part", "Integer", 1),
    ("amd", "Text", "2005"),
    ("conformance", "Text", "B"),
    ("rev", "Integer", 2020),
)


@pytest.fixture
def metadata() -> XMPMetadata:
    """Mirror of upstream's ``@BeforeEach initMetadata``."""
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> PDFAIdentificationSchema:
    return metadata.create_and_add_pdfa_identification_schema()


@pytest.mark.parametrize(("property_name", "type_token", "value"), _PARAMETERS)
def test_element_value(
    schema: PDFAIdentificationSchema,
    property_name: str,
    type_token: str,
    value: object,
) -> None:
    """Translated from upstream ``testElementValue`` — string/int-form
    setter round-trips through the matching getter."""
    del type_token
    setter_name = {
        "part": "set_part",
        "amd": "set_amd",
        "conformance": "set_conformance",
        "rev": "set_rev",
    }[property_name]
    getter_name = {
        "part": "get_part",
        "amd": "get_amendment",
        "conformance": "get_conformance",
        "rev": "get_rev",
    }[property_name]
    getattr(schema, setter_name)(value)
    assert getattr(schema, getter_name)() == value


@pytest.mark.parametrize(("property_name", "type_token", "value"), _PARAMETERS)
def test_element_property(
    metadata: XMPMetadata,
    schema: PDFAIdentificationSchema,
    property_name: str,
    type_token: str,
    value: object,
) -> None:
    """Translated from upstream ``testElementProperty`` — construct the
    matching typed property and round-trip through ``set_xxx_property`` /
    ``get_xxx_property``."""
    if type_token == "Integer":
        prop: object = IntegerType(
            metadata,
            PDFAIdentificationSchema.NAMESPACE,
            PDFAIdentificationSchema.PREFERRED_PREFIX,
            property_name,
            value,
        )
    else:
        prop = TextType(
            metadata,
            PDFAIdentificationSchema.NAMESPACE,
            PDFAIdentificationSchema.PREFERRED_PREFIX,
            property_name,
            value,
        )
    typed_setter = {
        "part": "set_part_property",
        "amd": "set_amd_property",
        "conformance": "set_conformance_property",
        "rev": "set_rev_property",
    }[property_name]
    typed_getter = {
        "part": "get_part_property",
        "amd": "get_amd_property",
        "conformance": "get_conformance_property",
        "rev": "get_rev_property",
    }[property_name]
    getattr(schema, typed_setter)(prop)
    fetched = getattr(schema, typed_getter)()
    assert fetched is not None
    # Upstream asserts the typed wrapper is returned (value-equality);
    # pypdfbox's `_typed_set` pins ``prop`` directly so identity holds.
    assert fetched is prop
