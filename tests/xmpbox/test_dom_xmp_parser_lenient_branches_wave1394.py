"""Wave 1394 — lenient-mode early-returns in ``DomXmpParser`` validators.

Covers lines 570, 600, 642-644, 671, 1252 in
``pypdfbox.xmpbox.dom_xmp_parser``:

* Line 570 — ``_validate_attribute_form_cardinality`` lenient mode skip.
* Line 600 — ``_validate_parse_type_namespace`` xml-namespace `parseType`
  silent skip (the comment notes ElementTree won't normally produce this
  shape, so we exercise it directly).
* Lines 642-644 — ``_validate_element_form_cardinality`` lenient Simple
  mismatch.
* Line 671 — same validator's lenient Bag/Seq mismatch.
* Line 1252 — ``parse_children_as_properties`` skipping a child whose
  namespace is the reserved ``xml:`` namespace (lenient mode).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: N817

import pytest

from pypdfbox.xmpbox import DomXmpParser, XMPMetadata, XmpParsingException
from pypdfbox.xmpbox.dom_xmp_parser import (
    _RDF_NS,
    _XML_NS,
)
from pypdfbox.xmpbox.dublin_core_schema import DublinCoreSchema


def _lenient_parser() -> DomXmpParser:
    p = DomXmpParser()
    p.set_strict_parsing(False)
    return p


# ---------- line 570 — attribute-form lenient skip ----------


def test_validate_attribute_form_cardinality_lenient_skips_array_warning() -> None:
    """Property declared as Bag/Seq but presented via attribute shorthand
    is silently tolerated in lenient mode (line 570)."""
    parser = _lenient_parser()
    # CREATOR is declared Seq. In strict mode this would raise; in lenient mode
    # the validator returns without raising.
    parser._validate_attribute_form_cardinality(  # noqa: SLF001
        DublinCoreSchema.NAMESPACE, DublinCoreSchema.CREATOR
    )


# ---------- line 600 — parseType in xml namespace silent skip ----------


def test_validate_parse_type_xml_namespace_is_skipped() -> None:
    """A ``parseType`` attribute carried in the XML reserved namespace
    is treated as harmless (line 600). The strict-mode raise only fires
    for ``parseType`` in *other* non-rdf namespaces."""
    parser = DomXmpParser()  # strict default — still tolerated for XML ns
    elem = ET.Element(f"{{{_RDF_NS}}}Description")
    elem.set(f"{{{_XML_NS}}}parseType", "Resource")
    # Should not raise.
    parser._validate_parse_type_namespace(elem, "ns", "local")  # noqa: SLF001


# ---------- lines 642-644 — Simple-cardinality lenient mode ----------


def test_validate_element_form_cardinality_simple_with_list_lenient_skips() -> None:
    """Simple-declared property got a list (Bag/Seq shape) — lenient
    mode silently accepts (lines 642-644)."""
    parser = _lenient_parser()
    parser._validate_element_form_cardinality(  # noqa: SLF001
        ET.Element("dummy"),
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.COVERAGE,  # declared Simple
        parsed_value=["one", "two"],
    )


def test_validate_element_form_cardinality_simple_with_dict_lenient_skips() -> None:
    parser = _lenient_parser()
    parser._validate_element_form_cardinality(  # noqa: SLF001
        ET.Element("dummy"),
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.COVERAGE,
        parsed_value={"x-default": "value"},
    )


# ---------- line 671 — Bag/Seq lenient mode ----------


def test_validate_element_form_cardinality_seq_with_str_lenient_skips() -> None:
    """Bag/Seq-declared property received a bare string — lenient mode
    tolerates (line 671)."""
    parser = _lenient_parser()
    parser._validate_element_form_cardinality(  # noqa: SLF001
        ET.Element("dummy"),
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.CREATOR,  # declared Seq
        parsed_value="not-a-list",
    )


def test_validate_element_form_cardinality_seq_with_dict_lenient_skips() -> None:
    parser = _lenient_parser()
    parser._validate_element_form_cardinality(  # noqa: SLF001
        ET.Element("dummy"),
        DublinCoreSchema.NAMESPACE,
        DublinCoreSchema.CREATOR,
        parsed_value={"x-default": "value"},
    )


# ---------- line 1252 — parse_children_as_properties skip xml ns ----------


def test_validate_parse_type_namespace_skips_non_parsetype_attributes() -> None:
    """Line 592 — the loop's ``continue`` for attributes whose local
    name is *not* ``parseType``."""
    parser = DomXmpParser()
    elem = ET.Element(f"{{{_RDF_NS}}}Description")
    # An unrelated attribute (`rdf:about` is common on Description nodes).
    elem.set(f"{{{_RDF_NS}}}about", "http://example.com/")
    elem.set("nakedAttr", "value")
    # Should not raise — neither attribute is parseType.
    parser._validate_parse_type_namespace(elem, "ns", "local")  # noqa: SLF001


def test_validate_element_form_cardinality_strict_simple_mismatch_raises() -> None:
    """Line 644 — strict mode raises INVALID_TYPE when a Simple-declared
    property gets a list/dict shape."""
    parser = DomXmpParser()  # strict default
    with pytest.raises(XmpParsingException) as excinfo:
        parser._validate_element_form_cardinality(  # noqa: SLF001
            ET.Element("dummy"),
            DublinCoreSchema.NAMESPACE,
            DublinCoreSchema.COVERAGE,  # declared Simple
            parsed_value=["one", "two"],
        )
    assert excinfo.value.get_error_type() is XmpParsingException.ErrorType.INVALID_TYPE


def test_parse_children_as_properties_skips_xml_namespace_child() -> None:
    """A property whose namespace is the reserved ``xml:`` namespace
    causes ``_reject_reserved_namespace_as_property`` to return ``True``
    (lenient mode), which makes the loop ``continue`` (line 1252)."""
    parser = _lenient_parser()
    metadata = XMPMetadata.create_xmp_metadata()
    description = ET.Element(f"{{{_RDF_NS}}}Description")
    # One child in the XML reserved namespace (will be skipped via
    # the lenient-mode reject helper).
    bogus = ET.SubElement(description, f"{{{_XML_NS}}}lang")
    bogus.text = "en"
    # Should not raise; should not register any schemas.
    parser.parse_children_as_properties(metadata, description, {})
    assert metadata.get_all_schemas() == []
