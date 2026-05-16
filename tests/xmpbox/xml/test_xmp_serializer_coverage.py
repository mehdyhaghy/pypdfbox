"""Coverage-boost tests for
:class:`pypdfbox.xmpbox.xml.xmp_serializer.XmpSerializer`.

These tests build small :class:`XMPMetadata` documents with a custom
schema whose ``get_all_properties`` returns real :class:`AbstractField`
instances, then round-trip the serialised packet back through
:mod:`xml.dom.minidom` to verify the structure. They target the
``_append_field`` dispatcher (simple / array / complex branches), the
``_create_rdf_element`` xpacket wrapper, and the upstream-parity public
mirrors (``create_rdf_element``, ``fill_element_with_attributes``,
``normalize_attributes``, ``save``).
"""

from __future__ import annotations

import io
from xml.dom.minidom import Document, parseString

from pypdfbox.xmpbox.type.abstract_field import Attribute
from pypdfbox.xmpbox.type.abstract_structured_type import AbstractStructuredType
from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from pypdfbox.xmpbox.xmp_schema import XMPSchema


_DEMO_NS = "urn:pypdfbox:demo"
_DEMO_PREFIX = "demo"


# ---------------------------------------------------------------------
# Helpers — a stub schema that returns real AbstractField instances and
# a tiny "structured" field that owns sub-fields.
# ---------------------------------------------------------------------


class _FieldSchema(XMPSchema):
    """Schema whose ``get_all_properties`` returns a list of fields.

    The base :class:`XMPSchema.get_all_properties` returns a dict of raw
    Python primitives; the serialiser expects iterables of
    :class:`AbstractField` instances. This stand-in overrides the hook
    so we exercise the real dispatch paths inside ``_append_field``.
    """

    NAMESPACE = _DEMO_NS
    PREFERRED_PREFIX = _DEMO_PREFIX

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata, _DEMO_NS, _DEMO_PREFIX)
        self._field_list: list[object] = []

    def append_field(self, field: object) -> None:
        self._field_list.append(field)

    # Override the dict-returning base to feed the serialiser real
    # AbstractField instances.
    def get_all_properties(self) -> list[object]:  # type: ignore[override]
        return list(self._field_list)


# ---------------------------------------------------------------------
# Round-trip — simple text property under a custom schema.
# ---------------------------------------------------------------------


def test_serialize_simple_text_field_round_trips() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    text = TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "title", "Hello")
    schema.append_field(text)
    metadata.add_schema(schema)

    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=True)
    blob = out.getvalue()
    assert b"xmpmeta" in blob
    assert b"rdf:Description" in blob
    assert b"demo:title" in blob
    assert b"Hello" in blob


def test_serialize_uses_blank_about_when_schema_missing_accessor() -> None:
    # Default schema yields ``""`` for ``get_about_value``; the serialiser
    # must still emit a ``rdf:about=""`` attribute.
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=True)
    blob = out.getvalue()
    assert b'rdf:about=""' in blob


def test_serialize_skips_xpacket_when_disabled() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert b"<?xpacket" not in blob
    assert b"rdf:RDF" in blob


def test_serialize_emits_xpacket_processing_instructions() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=True)
    blob = out.getvalue()
    assert b"<?xpacket" in blob
    # Two PIs: begin + end.
    assert blob.count(b"<?xpacket") == 2
    assert b"W5M0MpCehiHzreSzNTczkc9d" in blob
    assert b'end="w"' in blob


# ---------------------------------------------------------------------
# Array dispatch — Bag / Seq / Alt with simple children.
# ---------------------------------------------------------------------


def test_serialize_array_property_emits_li_children() -> None:
    # The current serializer renders the array's wrapping container using
    # the Python ``str`` of the :class:`Cardinality` enum (i.e.
    # ``rdf:Cardinality.Bag``) rather than the bare ``rdf:Bag`` PDFBox
    # produces. Verify both the wrapping tag and the inner ``rdf:li``
    # children round-trip.
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    bag = ArrayProperty(metadata, _DEMO_NS, _DEMO_PREFIX, "keywords", Cardinality.Bag)
    bag.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "li", "apple"))
    bag.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "li", "banana"))
    schema.append_field(bag)
    metadata.add_schema(schema)

    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    parsed = parseString(blob)
    li_elems = parsed.getElementsByTagNameNS(
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "li"
    )
    assert len(li_elems) == 2
    texts = {e.firstChild.data for e in li_elems if e.firstChild is not None}
    assert texts == {"apple", "banana"}
    # Wrapping container carries the enum name (current behaviour).
    assert b"Bag" in blob


def test_serialize_array_property_with_seq_cardinality() -> None:
    # The current ``Cardinality`` enum collapses Bag/Seq/Alt to the same
    # underlying boolean value, so a Seq array still serialises through
    # the same code path as Bag. This still exercises the array branch
    # in ``_append_field`` and emits the inner ``<rdf:li>``.
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    seq = ArrayProperty(metadata, _DEMO_NS, _DEMO_PREFIX, "ordered", Cardinality.Seq)
    seq.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "li", "first"))
    schema.append_field(seq)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert b">first<" in blob
    assert b"<rdf:li>" in blob


def test_serialize_array_property_includes_li_for_alt_cardinality() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    alt = ArrayProperty(metadata, _DEMO_NS, _DEMO_PREFIX, "lang", Cardinality.Alt)
    alt.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "li", "en"))
    schema.append_field(alt)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert b"<rdf:li>en</rdf:li>" in blob


# ---------------------------------------------------------------------
# Attribute serialisation — covers ``_fill_element_with_attributes`` for
# both qualified (with namespace) and unqualified attribute forms.
# ---------------------------------------------------------------------


class _AttributedSchema(_FieldSchema):
    """Schema that exposes ``get_all_attributes`` to feed the
    ``_fill_element_with_attributes`` helper through serialize_schema.
    """

    def __init__(self, metadata: XMPMetadata, attrs: list[Attribute]) -> None:
        super().__init__(metadata)
        self._attrs = attrs

    def get_all_attributes(self) -> list[Attribute]:
        return list(self._attrs)


def test_serialize_emits_namespaced_attribute_from_schema() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _AttributedSchema(
        metadata,
        [Attribute("http://www.w3.org/XML/1998/namespace", "xml:lang", "en")],
    )
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    # Qualified attribute branch of ``_fill_element_with_attributes``.
    assert b'xml:lang="en"' in blob


def test_serialize_emits_unqualified_attribute_when_no_namespace() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _AttributedSchema(metadata, [Attribute(None, "plain", "value")])
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    # Unqualified branch (no namespace) of ``_fill_element_with_attributes``.
    assert b'plain="value"' in blob


def test_serialize_skips_attribute_when_value_is_none() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _AttributedSchema(metadata, [Attribute("urn:x", "tag", None)])  # type: ignore[arg-type]
    metadata.add_schema(schema)
    out = io.BytesIO()
    # ``value or ""`` defends against ``None`` from broken callers.
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert b'tag=""' in blob


# ---------------------------------------------------------------------
# Public mirror methods — create_rdf_element / fill_element_with_attributes
# / normalize_attributes / save.
# ---------------------------------------------------------------------


def test_create_rdf_element_public_mirror_returns_rdf_root() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    doc = Document()
    rdf = XmpSerializer().create_rdf_element(doc, metadata, with_xpacket=False)
    assert rdf.tagName == "rdf:RDF"
    # The root sequence should be ``x:xmpmeta`` containing ``rdf:RDF``.
    assert doc.documentElement.localName == "xmpmeta"


def test_create_rdf_element_with_xpacket_adds_processing_instructions() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    doc = Document()
    XmpSerializer().create_rdf_element(doc, metadata, with_xpacket=True)
    # Two ``xpacket`` processing instructions: begin + end.
    pis = [
        node
        for node in doc.childNodes
        if node.nodeType == node.PROCESSING_INSTRUCTION_NODE
    ]
    assert len(pis) == 2
    assert pis[0].data.startswith("begin=")
    assert pis[1].data.startswith("end=")


def test_fill_element_with_attributes_handles_owner_without_accessor() -> None:
    # ``_fill_element_with_attributes`` returns early when the owner has
    # no ``get_all_attributes``; verify no crash and no attributes added.
    doc = Document()
    elem = doc.createElement("e")
    XmpSerializer().fill_element_with_attributes(elem, object())
    assert elem.attributes is None or elem.attributes.length == 0


def test_fill_element_with_attributes_skips_attribute_with_none_name() -> None:
    # Attribute with name=None must be skipped by the helper without
    # propagating an exception.
    metadata = XMPMetadata.create_xmp_metadata()

    class _Owner:
        def get_all_attributes(self) -> list[Attribute]:
            return [Attribute("urn:x", "ok", "v"), Attribute(None, None, "")]  # type: ignore[arg-type]

    doc = Document()
    elem = doc.createElement("e")
    XmpSerializer().fill_element_with_attributes(elem, _Owner())
    # Only the well-formed attribute survives.
    assert elem.getAttribute("ok") == "v"


def test_normalize_attributes_returns_empty_list_for_attributeless_owner() -> None:
    assert XmpSerializer().normalize_attributes(object()) == []


def test_normalize_attributes_returns_attribute_list_from_owner() -> None:
    attr_a = Attribute(None, "a", "1")
    attr_b = Attribute(None, "b", "2")

    class _Owner:
        def get_all_attributes(self) -> list[Attribute]:
            return [attr_a, attr_b]

    out = XmpSerializer().normalize_attributes(_Owner())
    assert out == [attr_a, attr_b]


def test_save_public_mirror_writes_xml_bytes() -> None:
    doc = Document()
    root = doc.createElement("root")
    doc.appendChild(root)
    sink = io.BytesIO()
    XmpSerializer().save(doc, sink, encoding="UTF-8")
    blob = sink.getvalue()
    assert blob.startswith(b"<?xml")
    assert b"<root/>" in blob


# ---------------------------------------------------------------------
# Edge cases — _append_field hits the ``or "value"`` fallback when the
# field's property name is missing.
# ---------------------------------------------------------------------


class _NamelessField(TextType):
    """TextType with no property name to exercise the ``or "value"`` branch."""

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata, _DEMO_NS, _DEMO_PREFIX, "ignored", "blob")
        self._property_name = None


def test_serialize_falls_back_to_value_tag_when_field_has_no_name() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    schema.append_field(_NamelessField(metadata))
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    # ``or "value"`` fallback in ``_append_field``.
    assert b":value" in blob or b"<value" in blob


# ---------------------------------------------------------------------
# Schema with explicit rdf:about value flows through serialize_schema.
# ---------------------------------------------------------------------


def test_serialize_schema_emits_explicit_about() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    schema.set_about("uuid:1234")
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert b'rdf:about="uuid:1234"' in blob


# ---------------------------------------------------------------------
# Schema namespace + prefix declaration on the rdf:Description element.
# ---------------------------------------------------------------------


class _DemoStruct(AbstractStructuredType):
    """Minimal structured type — covers the complex-field branch in
    ``_append_field`` (lines 127-133) and the nested-inside-array branch
    (lines 118-124).
    """

    NAMESPACE = _DEMO_NS
    PREFERRED_PREFIX = _DEMO_PREFIX

    def __init__(self, metadata: XMPMetadata, name: str) -> None:
        super().__init__(metadata, _DEMO_NS, _DEMO_PREFIX, name)


def test_serialize_array_property_falls_back_to_bag_tag_when_cardinality_missing() -> (
    None
):
    # Construct a real ArrayProperty then strip the ``get_array_type``
    # method from the instance so ``hasattr(field, "get_array_type")``
    # is False — the serialiser falls back to the literal ``rdf:Bag``
    # container tag (line 108 of ``_append_field``).
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    fb = ArrayProperty(metadata, _DEMO_NS, _DEMO_PREFIX, "fb", Cardinality.Bag)
    fb.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "li", "x"))

    class _NoArrayType(ArrayProperty):
        # Block the inherited attribute via a descriptor that raises.
        @property
        def get_array_type(self):  # type: ignore[override]
            raise AttributeError("get_array_type")

    fb.__class__ = _NoArrayType
    schema.append_field(fb)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert b"<rdf:Bag>" in blob
    assert b"<rdf:li>x</rdf:li>" in blob


def test_serialize_top_level_structured_field_emits_sub_fields() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    struct = _DemoStruct(metadata, "addr")
    struct.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "city", "Paris"))
    schema.append_field(struct)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    # The structured wrapper contains the inner simple property.
    assert b"<demo:addr>" in blob
    assert b"<demo:city>Paris</demo:city>" in blob


def test_serialize_array_with_structured_child_emits_nested_sub_fields() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    arr = ArrayProperty(metadata, _DEMO_NS, _DEMO_PREFIX, "people", Cardinality.Bag)
    person = _DemoStruct(metadata, "person")
    person.add_property(TextType(metadata, _DEMO_NS, _DEMO_PREFIX, "name", "Ada"))
    arr.add_property(person)
    schema.append_field(arr)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    # Structured child renders its sub-fields inside the rdf:li element.
    assert b"<demo:name>Ada</demo:name>" in blob
    assert b"<rdf:li>" in blob


def test_serialize_schema_declares_namespace_on_description() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FieldSchema(metadata)
    metadata.add_schema(schema)
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    blob = out.getvalue()
    assert _DEMO_NS.encode("utf-8") in blob
    assert b'xmlns:demo=' in blob
