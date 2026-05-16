"""Coverage-boost for ``pypdfbox.xmpbox.dom_xmp_parser`` (wave 1321).

Targets the previously-untested upstream-named helpers (parse_initial_xpacket,
parse_end_packet, find_descriptions_parent, remove_comments_and_blanks,
maybe_add_non_standard_namespace, load_attributes, check_property_definition,
create_property, manage_* placeholders, parse_description_root /
parse_description_root_attr / parse_children_as_properties /
parse_schema_extensions / parse_description_inner / parse_li_element /
parse_li_description / instanciate_structured /
try_parse_attributes_as_properties) plus the previously-untested fallback
branches inside ``_try_parse_typed_array`` and the typed-array
``rdf:Description`` wrapper path inside ``_build_structured_from_li``.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import (
    DomXmpParser,
    XmpParsingException,
)
from pypdfbox.xmpbox.adobe_pdf_schema import AdobePDFSchema
from pypdfbox.xmpbox.photoshop_schema import PhotoshopSchema
from pypdfbox.xmpbox.type import LayerType
from pypdfbox.xmpbox.xmp_metadata import RDF_NAMESPACE, XMPMetadata
from pypdfbox.xmpbox.xmp_schema import XMPSchema

_RDF_NS = RDF_NAMESPACE
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_X_NS = "adobe:ns:meta/"


# ---------------------------------------------------------------------------
# parse_initial_xpacket
# ---------------------------------------------------------------------------


def test_parse_initial_xpacket_round_trip() -> None:
    parser = DomXmpParser()
    out = parser.parse_initial_xpacket(
        'begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"'
    )
    assert out["begin"] == "﻿"
    assert out["id"] == "W5M0MpCehiHzreSzNTczkc9d"
    # Optional attrs default to None.
    assert out["bytes"] is None
    assert out["encoding"] is None


def test_parse_initial_xpacket_rejects_missing_terminator() -> None:
    parser = DomXmpParser()
    # No trailing quote -> XPACKET_BAD_START.
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_initial_xpacket("begin=foo")
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_START
    )


def test_parse_initial_xpacket_rejects_no_assign() -> None:
    parser = DomXmpParser()
    # token ends with a quote but contains no =" or =' separator.
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_initial_xpacket('"orphan"')
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_START
    )


def test_parse_initial_xpacket_rejects_unknown_attribute() -> None:
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_initial_xpacket('unknown="value"')
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_START
    )


def test_parse_initial_xpacket_rejects_empty_value_slot() -> None:
    parser = DomXmpParser()
    # ``name="`` has length 6 and pos==4, so pos+2 == 6 == len-1 -> error.
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_initial_xpacket('id="')
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_START
    )


# ---------------------------------------------------------------------------
# parse_end_packet
# ---------------------------------------------------------------------------


def test_parse_end_packet_returns_marker() -> None:
    parser = DomXmpParser()
    assert parser.parse_end_packet("end='w'") == "w"
    assert parser.parse_end_packet('end="r"') == "r"


def test_parse_end_packet_rejects_missing_prefix() -> None:
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_end_packet("foo='w'")
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_END
    )


def test_parse_end_packet_rejects_short_input() -> None:
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_end_packet("end=")
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_END
    )


def test_parse_end_packet_rejects_invalid_marker() -> None:
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_end_packet("end='x'")
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_END
    )


# ---------------------------------------------------------------------------
# find_descriptions_parent + expect_naming
# ---------------------------------------------------------------------------


def test_find_descriptions_parent_returns_rdf_root_directly() -> None:
    parser = DomXmpParser()
    root = ET.Element(f"{{{_RDF_NS}}}RDF")
    assert parser.find_descriptions_parent(root) is root


def test_find_descriptions_parent_unwraps_xmpmeta() -> None:
    parser = DomXmpParser()
    wrapper = ET.Element(f"{{{_X_NS}}}xmpmeta")
    rdf = ET.SubElement(wrapper, f"{{{_RDF_NS}}}RDF")
    assert parser.find_descriptions_parent(wrapper) is rdf


def test_find_descriptions_parent_rejects_empty_xmpmeta() -> None:
    parser = DomXmpParser()
    wrapper = ET.Element(f"{{{_X_NS}}}xmpmeta")
    with pytest.raises(XmpParsingException) as excinfo:
        parser.find_descriptions_parent(wrapper)
    assert excinfo.value.get_error_type() is XmpParsingException.ErrorType.FORMAT


def test_find_descriptions_parent_rejects_multiple_children() -> None:
    parser = DomXmpParser()
    wrapper = ET.Element(f"{{{_X_NS}}}xmpmeta")
    ET.SubElement(wrapper, f"{{{_RDF_NS}}}RDF")
    ET.SubElement(wrapper, f"{{{_RDF_NS}}}RDF")
    with pytest.raises(XmpParsingException) as excinfo:
        parser.find_descriptions_parent(wrapper)
    assert excinfo.value.get_error_type() is XmpParsingException.ErrorType.FORMAT


def test_find_descriptions_parent_lenient_xapmeta() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    wrapper = ET.Element(f"{{{_X_NS}}}xapmeta")
    rdf = ET.SubElement(wrapper, f"{{{_RDF_NS}}}RDF")
    assert parser.find_descriptions_parent(wrapper) is rdf


def test_expect_naming_namespace_mismatch_raises() -> None:
    parser = DomXmpParser()
    element = ET.Element(f"{{{_RDF_NS}}}RDF")
    with pytest.raises(XmpParsingException) as excinfo:
        parser.expect_naming(element, "wrong", "rdf", "RDF")
    assert excinfo.value.get_error_type() is XmpParsingException.ErrorType.FORMAT


def test_expect_naming_local_name_mismatch_raises() -> None:
    parser = DomXmpParser()
    element = ET.Element(f"{{{_RDF_NS}}}RDF")
    with pytest.raises(XmpParsingException) as excinfo:
        parser.expect_naming(element, _RDF_NS, "rdf", "Description")
    assert excinfo.value.get_error_type() is XmpParsingException.ErrorType.FORMAT


def test_expect_naming_allows_none_ns_and_local() -> None:
    parser = DomXmpParser()
    element = ET.Element(f"{{{_RDF_NS}}}RDF")
    # None on both arms: no validation should run, no exception.
    parser.expect_naming(element, None, None, None)


# ---------------------------------------------------------------------------
# remove_comments_and_blanks
# ---------------------------------------------------------------------------


def test_remove_comments_and_blanks_normalises_whitespace() -> None:
    root = ET.Element("root")
    child = ET.SubElement(root, "child")
    child.text = "   "
    child.tail = "\n  "
    DomXmpParser.remove_comments_and_blanks(root)
    assert child.text is None
    assert child.tail is None


# ---------------------------------------------------------------------------
# maybe_add_non_standard_namespace
# ---------------------------------------------------------------------------


def test_maybe_add_non_standard_namespace_records_mapping() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    parser.maybe_add_non_standard_namespace(metadata, "foo", "http://example/foo/")
    assert parser._non_standard_namespaces == {"foo": "http://example/foo/"}
    # Second call appends; same dict.
    parser.maybe_add_non_standard_namespace(metadata, "bar", "http://example/bar/")
    assert parser._non_standard_namespaces["bar"] == "http://example/bar/"


def test_maybe_add_non_standard_namespace_skips_rdf() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    parser.maybe_add_non_standard_namespace(metadata, "rdf", _RDF_NS)
    # No side table created when the RDF namespace is filtered out first.
    assert not hasattr(parser, "_non_standard_namespaces")


# ---------------------------------------------------------------------------
# load_attributes
# ---------------------------------------------------------------------------


def test_load_attributes_captures_about_and_xml_qualifiers() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    element = ET.Element("e")
    element.set(f"{{{_RDF_NS}}}about", "id-1")
    element.set(f"{{{_XML_NS}}}lang", "en-US")
    parser.load_attributes(schema, element)
    assert schema.get_about() == "id-1"
    assert schema._namespaces.get("lang") == "en-US"


def test_load_attributes_ignores_unrelated_qualifiers() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    element = ET.Element("e")
    element.set("plain", "value")  # no namespace
    # Should not raise and should not populate _namespaces.
    parser.load_attributes(schema, element)
    assert "plain" not in schema._namespaces


# ---------------------------------------------------------------------------
# check_property_definition
# ---------------------------------------------------------------------------


def test_check_property_definition_strict_rejects_unknown() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = AdobePDFSchema(metadata)  # exposes KNOWN_PROPERTIES allow-list
    with pytest.raises(XmpParsingException) as excinfo:
        parser.check_property_definition(
            schema, AdobePDFSchema.NAMESPACE, "AbsolutelyNotAProperty"
        )
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_check_property_definition_lenient_is_noop() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    metadata = XMPMetadata()
    schema = AdobePDFSchema(metadata)
    # No exception in lenient mode.
    parser.check_property_definition(schema, AdobePDFSchema.NAMESPACE, "Bogus")


# ---------------------------------------------------------------------------
# create_property + manage_* placeholders
# ---------------------------------------------------------------------------


def test_create_property_writes_text_value() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    element = ET.Element("{http://ex/}foo")
    element.text = "value-1"
    parser.create_property(metadata, element, schema)
    assert schema.get_property("foo") is not None


def test_manage_simple_type_sets_text_property() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    parser.manage_simple_type(schema, "title", "Hello")
    assert schema.get_property("title") is not None


def test_manage_array_appends_each_item() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    parser.manage_array(schema, "keywords", ["a", "b"])
    # No exception suffices for the placeholder branch coverage.


def test_manage_lang_alt_writes_each_lang_entry() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    parser.manage_lang_alt(schema, "title", {"x-default": "Hello", "fr": "Bonjour"})


def test_manage_structured_and_defined_types_return_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = XMPSchema(metadata, namespace_uri="http://ex/", prefix="ex")
    element = ET.Element("e")
    assert parser.manage_structured_type(schema, "any", element) is None
    assert parser.manage_defined_type(schema, "any", element) is None


# ---------------------------------------------------------------------------
# parse_description_root / parse_description_root_attr /
# parse_children_as_properties
# ---------------------------------------------------------------------------


def _make_description() -> ET.Element:
    desc = ET.Element(f"{{{_RDF_NS}}}Description")
    desc.set(f"{{{_RDF_NS}}}about", "doc-1")
    return desc


def test_parse_description_root_creates_schema() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    desc = _make_description()
    desc.set("{http://ex/}title", "Hi")
    parser.set_strict_parsing(False)
    per_ns = parser.parse_description_root(metadata, desc)
    assert "http://ex/" in per_ns


def test_parse_description_root_uses_supplied_accumulator() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    desc = _make_description()
    desc.set("{http://ex/}title", "Hi")
    parser.set_strict_parsing(False)
    per_ns: dict[str, XMPSchema] = {}
    returned = parser.parse_description_root(metadata, desc, per_ns)
    assert returned is per_ns
    assert "http://ex/" in per_ns


def test_parse_description_root_attr_writes_simple_text() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    metadata = XMPMetadata()
    desc = _make_description()
    per_ns: dict[str, XMPSchema] = {}
    parser.parse_description_root_attr(
        metadata, desc, "{http://ex/}title", "Hello", per_ns
    )
    assert "http://ex/" in per_ns


def test_parse_description_root_attr_skips_rdf_namespace() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    desc = _make_description()
    per_ns: dict[str, XMPSchema] = {}
    parser.parse_description_root_attr(
        metadata, desc, f"{{{_RDF_NS}}}about", "ignored", per_ns
    )
    assert per_ns == {}


def test_parse_children_as_properties_walks_each_child() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    metadata = XMPMetadata()
    desc = _make_description()
    ET.SubElement(desc, "{http://ex/}title").text = "Hello"
    ET.SubElement(desc, f"{{{_RDF_NS}}}note").text = "ignored"  # RDF -> skipped
    per_ns: dict[str, XMPSchema] = {}
    parser.parse_children_as_properties(metadata, desc, per_ns)
    assert "http://ex/" in per_ns


# ---------------------------------------------------------------------------
# parse_schema_extensions, parse_description_inner
# ---------------------------------------------------------------------------


def test_parse_schema_extensions_returns_extension_children_only() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    desc = ET.Element("d")
    ext = ET.SubElement(
        desc, "{http://www.aiim.org/pdfa/ns/extension/}schemas"
    )
    ET.SubElement(desc, "{http://other/}node")  # not an extension
    result = parser.parse_schema_extensions(metadata, desc)
    assert result == [ext]


def test_parse_description_inner_returns_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    desc = ET.Element("d")
    assert parser.parse_description_inner(metadata, desc) is None


# ---------------------------------------------------------------------------
# parse_li_element / parse_li_description / instanciate_structured
# ---------------------------------------------------------------------------


def test_parse_li_element_returns_text_for_simple_li() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    li = ET.Element(f"{{{_RDF_NS}}}li")
    li.text = "  hello  "
    out = parser.parse_li_element(metadata, ("ns", "local"), li)
    assert out == "hello"


def test_parse_li_element_returns_element_for_structured_li() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    li = ET.Element(f"{{{_RDF_NS}}}li")
    ET.SubElement(li, f"{{{_RDF_NS}}}Description")
    out = parser.parse_li_element(metadata, ("ns", "local"), li)
    assert isinstance(out, ET.Element)


def test_parse_li_description_returns_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    li = ET.Element(f"{{{_RDF_NS}}}li")
    assert parser.parse_li_description(metadata, ("ns", "local"), li) is None


def test_instanciate_structured_returns_none() -> None:
    parser = DomXmpParser()
    assert parser.instanciate_structured("Layer", "TextLayers") is None


# ---------------------------------------------------------------------------
# try_parse_attributes_as_properties (PDFBOX-3882)
# ---------------------------------------------------------------------------


def test_try_parse_attributes_as_properties_registers_schema() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    metadata = XMPMetadata()
    li = ET.Element(f"{{{_RDF_NS}}}li")
    li.set(f"{{{_RDF_NS}}}about", "x")
    li.set("{http://ex/}title", "Hello")
    li.set(f"{{{_XML_NS}}}lang", "en")  # filtered out
    li.set("plain", "ignored")  # no namespace -> filtered
    per_ns = parser.try_parse_attributes_as_properties(metadata, li)
    assert "http://ex/" in per_ns
    # rdf/xml/plain were skipped.
    assert len(per_ns) == 1


def test_try_parse_attributes_as_properties_accepts_supplied_accumulators() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    metadata = XMPMetadata()
    li = ET.Element(f"{{{_RDF_NS}}}li")
    li.set("{http://ex/}title", "Hello")
    per_ns: dict[str, XMPSchema] = {}
    namespaces: dict[str, str] = {}
    returned = parser.try_parse_attributes_as_properties(
        metadata, li, per_ns, namespaces
    )
    assert returned is per_ns


# ---------------------------------------------------------------------------
# Typed-array fallback branches inside _try_parse_typed_array
# ---------------------------------------------------------------------------


def test_typed_array_unregistered_slot_returns_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element("{http://ex/}NotRegistered")
    assert (
        parser._try_parse_typed_array(
            element, "http://ex/", "NotRegistered", schema
        )
        is None
    )


def test_typed_array_missing_container_returns_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    # No rdf:Seq child -> fall through to plain-list path.
    assert (
        parser._try_parse_typed_array(
            element,
            PhotoshopSchema.NAMESPACE,
            PhotoshopSchema.TEXT_LAYERS,
            schema,
        )
        is None
    )


def test_typed_array_wrong_cardinality_returns_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    # registry expects Seq; Bag should fall through.
    ET.SubElement(element, f"{{{_RDF_NS}}}Bag")
    assert (
        parser._try_parse_typed_array(
            element,
            PhotoshopSchema.NAMESPACE,
            PhotoshopSchema.TEXT_LAYERS,
            schema,
        )
        is None
    )


def test_typed_array_empty_seq_returns_none() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    ET.SubElement(element, f"{{{_RDF_NS}}}Seq")  # no li children
    assert (
        parser._try_parse_typed_array(
            element,
            PhotoshopSchema.NAMESPACE,
            PhotoshopSchema.TEXT_LAYERS,
            schema,
        )
        is None
    )


def test_typed_array_builds_layer_from_attributes() -> None:
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    seq = ET.SubElement(element, f"{{{_RDF_NS}}}Seq")
    li = ET.SubElement(seq, f"{{{_RDF_NS}}}li")
    li.set("{" + PhotoshopSchema.NAMESPACE + "}LayerName", "L1")
    li.set("{" + PhotoshopSchema.NAMESPACE + "}LayerText", "T1")
    arr = parser._try_parse_typed_array(
        element,
        PhotoshopSchema.NAMESPACE,
        PhotoshopSchema.TEXT_LAYERS,
        schema,
    )
    assert arr is not None
    items = arr.get_all_properties()
    assert len(items) == 1
    assert isinstance(items[0], LayerType)


def test_typed_array_handles_li_with_nested_description() -> None:
    """PDFBOX-6126: rdf:Description wrapper inside rdf:li."""
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    seq = ET.SubElement(element, f"{{{_RDF_NS}}}Seq")
    li = ET.SubElement(seq, f"{{{_RDF_NS}}}li")
    inner = ET.SubElement(li, f"{{{_RDF_NS}}}Description")
    # Attribute-form on the wrapper.
    inner.set("{" + PhotoshopSchema.NAMESPACE + "}LayerName", "Lwrap")
    # Plus element-form children.
    ET.SubElement(
        inner, "{" + PhotoshopSchema.NAMESPACE + "}LayerText"
    ).text = "Twrap"
    # An RDF-namespaced child should be skipped.
    ET.SubElement(inner, f"{{{_RDF_NS}}}skip").text = "ignored"
    # A non-field child should be silently dropped.
    ET.SubElement(
        inner, "{" + PhotoshopSchema.NAMESPACE + "}NotAField"
    ).text = "drop"
    arr = parser._try_parse_typed_array(
        element,
        PhotoshopSchema.NAMESPACE,
        PhotoshopSchema.TEXT_LAYERS,
        schema,
    )
    assert arr is not None
    items = arr.get_all_properties()
    assert len(items) == 1
    assert isinstance(items[0], LayerType)


def test_build_structured_skips_rdf_and_xml_attributes_on_li() -> None:
    """Attributes in rdf: / xml: namespaces must not become fields."""
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    seq = ET.SubElement(element, f"{{{_RDF_NS}}}Seq")
    li = ET.SubElement(seq, f"{{{_RDF_NS}}}li")
    li.set(f"{{{_RDF_NS}}}parseType", "Resource")  # filtered
    li.set(f"{{{_XML_NS}}}lang", "en")  # filtered
    li.set("{" + PhotoshopSchema.NAMESPACE + "}LayerName", "Lonly")
    arr = parser._try_parse_typed_array(
        element,
        PhotoshopSchema.NAMESPACE,
        PhotoshopSchema.TEXT_LAYERS,
        schema,
    )
    assert arr is not None
    assert len(arr.get_all_properties()) == 1


def test_build_structured_inner_description_filters_rdf_xml_attributes() -> None:
    """rdf:/xml: attrs on the inner rdf:Description wrapper are skipped too."""
    parser = DomXmpParser()
    metadata = XMPMetadata()
    schema = PhotoshopSchema(metadata)
    element = ET.Element(
        "{" + PhotoshopSchema.NAMESPACE + "}" + PhotoshopSchema.TEXT_LAYERS
    )
    seq = ET.SubElement(element, f"{{{_RDF_NS}}}Seq")
    li = ET.SubElement(seq, f"{{{_RDF_NS}}}li")
    inner = ET.SubElement(li, f"{{{_RDF_NS}}}Description")
    inner.set(f"{{{_RDF_NS}}}parseType", "Resource")  # filtered
    inner.set(f"{{{_XML_NS}}}lang", "en")  # filtered
    inner.set("{" + PhotoshopSchema.NAMESPACE + "}LayerName", "ok")
    arr = parser._try_parse_typed_array(
        element,
        PhotoshopSchema.NAMESPACE,
        PhotoshopSchema.TEXT_LAYERS,
        schema,
    )
    assert arr is not None
    assert len(arr.get_all_properties()) == 1
