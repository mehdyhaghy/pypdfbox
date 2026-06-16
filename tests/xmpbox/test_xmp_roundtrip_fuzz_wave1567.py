"""Round-trip fuzz tests for the xmpbox parse/serialize pipeline (wave 1567).

These exercise ``DomXmpParser`` + ``XmpSerializer`` together: parse → serialize
→ reparse and assert the semantic payload survives. They hammer container
ordering (Bag/Seq/Alt), ``xml:lang`` alt-text selection, namespace prefix
collisions, empty / unicode values, malformed RDF error categories, duplicate
properties, and typed-property coercion (bool / int / date), checking each
against the upstream xmpbox semantics.

Behavioral notes vs upstream (PDFBox 3.0.x ``org.apache.xmpbox``):
  * ``XMPSchema.getUnqualifiedLanguagePropertyValue`` returns ``None`` for an
    unknown language — it does NOT fall back to ``x-default``.
  * ``xml:lang`` matching is case-sensitive (exact ``String.equals``).
  * Boolean XMP values serialize as the capitalised spec form ``True`` /
    ``False`` (``BooleanType.TRUE`` / ``FALSE``).
  * ``x-default`` is reorganised to the front of a LangAlt on schema-setter
    writes, but the parser preserves source ``rdf:li`` order.
  * The serializer preserves the parsed ``rdf:Bag`` vs ``rdf:Seq`` container
    kind on round-trip even for unknown-schema arrays (wave 1567 fix).
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser, XmpParsingException
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

DC_NS = "http://purl.org/dc/elements/1.1/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _serialize(metadata: XMPMetadata, with_xpacket: bool = True) -> bytes:
    buf = BytesIO()
    XmpSerializer().serialize(metadata, buf, with_xpacket)
    return buf.getvalue()


def _reparse(metadata: XMPMetadata, lenient: bool = False) -> XMPMetadata:
    parser = DomXmpParser()
    if lenient:
        parser.set_strict_parsing(False)
    return parser.parse(_serialize(metadata))


def _wrap(body: str) -> str:
    return (
        f'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        f'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        f'<rdf:RDF xmlns:rdf="{RDF_NS}">{body}</rdf:RDF></x:xmpmeta>'
        f'<?xpacket end="w"?>'
    )


def _dc_desc(inner: str) -> str:
    return _wrap(
        f'<rdf:Description rdf:about="" xmlns:dc="{DC_NS}">{inner}</rdf:Description>'
    )


def _parse(xml: str, lenient: bool = False) -> XMPMetadata:
    parser = DomXmpParser()
    if lenient:
        parser.set_strict_parsing(False)
    return parser.parse(xml)


# --------------------------------------------------------------------------- #
# Seq / Bag / Alt ordering preservation
# --------------------------------------------------------------------------- #


def test_creator_seq_order_preserved_through_full_roundtrip():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    for name in ("Charlie", "Alice", "Bob"):
        dc.add_creator(name)
    m2 = _reparse(m)
    assert m2.get_dublin_core_schema().get_creators() == ["Charlie", "Alice", "Bob"]


def test_subject_bag_values_preserved():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    for s in ("zeta", "alpha", "mu"):
        dc.add_subject(s)
    got = _reparse(m).get_dublin_core_schema().get_subjects()
    assert set(got) == {"zeta", "alpha", "mu"}
    assert len(got) == 3


def test_creator_seq_serializes_as_rdf_seq():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.add_creator("Solo")
    out = _serialize(m).decode("utf-8")
    assert "<dc:creator><rdf:Seq>" in out


def test_subject_bag_serializes_as_rdf_bag():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.add_subject("kw")
    out = _serialize(m).decode("utf-8")
    assert "<dc:subject><rdf:Bag>" in out


def test_known_schema_seq_parsed_then_reserialized_stays_seq():
    m = _parse(
        _dc_desc(
            "<dc:creator><rdf:Seq><rdf:li>A</rdf:li>"
            "<rdf:li>B</rdf:li></rdf:Seq></dc:creator>"
        )
    )
    out = _serialize(m).decode("utf-8")
    assert "<dc:creator><rdf:Seq>" in out
    assert "<rdf:Bag>" not in out


def test_known_schema_bag_parsed_then_reserialized_stays_bag():
    m = _parse(
        _dc_desc(
            "<dc:subject><rdf:Bag><rdf:li>x</rdf:li>"
            "<rdf:li>y</rdf:li></rdf:Bag></dc:subject>"
        )
    )
    out = _serialize(m).decode("utf-8")
    assert "<dc:subject><rdf:Bag>" in out


@pytest.mark.parametrize("container", ["Seq", "Bag"])
def test_custom_namespace_container_kind_preserved(container):
    # Wave 1567 fix: an unknown-schema rdf:Seq used to re-serialize as rdf:Bag
    # because the flat-dict storage discarded the parsed cardinality.
    xml = _wrap(
        '<rdf:Description rdf:about="" xmlns:custom="http://example.com/c/">'
        f"<custom:Items><rdf:{container}><rdf:li>one</rdf:li>"
        f"<rdf:li>two</rdf:li></rdf:{container}></custom:Items>"
        "</rdf:Description>"
    )
    m = _parse(xml, lenient=True)
    out = _serialize(m).decode("utf-8")
    assert f"<rdf:{container}>" in out
    other = "Bag" if container == "Seq" else "Seq"
    assert f"<rdf:{other}>" not in out


def test_custom_namespace_seq_order_preserved():
    xml = _wrap(
        '<rdf:Description rdf:about="" xmlns:custom="http://example.com/c/">'
        "<custom:Items><rdf:Seq><rdf:li>3</rdf:li>"
        "<rdf:li>1</rdf:li><rdf:li>2</rdf:li></rdf:Seq></custom:Items>"
        "</rdf:Description>"
    )
    m = _parse(xml, lenient=True)
    schema = m.get_all_schemas()[0]
    assert schema.get_all_properties()["Items"] == ["3", "1", "2"]


# --------------------------------------------------------------------------- #
# xml:lang / LangAlt selection
# --------------------------------------------------------------------------- #


def test_langalt_multi_language_roundtrip_selection():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_title("Bonjour", "fr")
    dc.set_title("Hello", "en")
    dc.set_title("Default", None)
    dc2 = _reparse(m).get_dublin_core_schema()
    assert dc2.get_title("en") == "Hello"
    assert dc2.get_title("fr") == "Bonjour"
    assert dc2.get_title(None) == "Default"


def test_langalt_unknown_language_returns_none_not_default():
    # Upstream getUnqualifiedLanguagePropertyValue does NOT fall back to
    # x-default for an unknown language.
    m = _parse(
        _dc_desc(
            '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">D</rdf:li>'
            '<rdf:li xml:lang="en">E</rdf:li></rdf:Alt></dc:title>'
        )
    )
    dc = m.get_dublin_core_schema()
    assert dc.get_title("de") is None
    assert dc.get_title(None) == "D"


def test_langalt_matching_is_case_sensitive():
    # xml:lang comparison is exact String.equals in upstream.
    m = _parse(
        _dc_desc(
            '<dc:title><rdf:Alt><rdf:li xml:lang="en-US">Hi</rdf:li>'
            "</rdf:Alt></dc:title>"
        )
    )
    dc = m.get_dublin_core_schema()
    assert dc.get_title("en-US") == "Hi"
    assert dc.get_title("en-us") is None


def test_langalt_missing_lang_defaults_to_x_default():
    m = _parse(
        _dc_desc("<dc:title><rdf:Alt><rdf:li>NoLang</rdf:li></rdf:Alt></dc:title>")
    )
    dc = m.get_dublin_core_schema()
    assert dc.get_title_languages() == ["x-default"]
    assert dc.get_title(None) == "NoLang"


def test_langalt_x_default_reorganized_to_front_on_setter():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_title("English", "en")
    dc.set_title("Default", None)
    # x-default must be reorganised first even though it was added second.
    assert dc.get_title_languages()[0] == "x-default"


def test_langalt_serializes_with_xml_lang_attributes():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_title("Wert", "de")
    out = _serialize(m).decode("utf-8")
    assert 'xml:lang="de"' in out
    assert "<rdf:Alt>" in out


# --------------------------------------------------------------------------- #
# namespace prefix collisions / unknown namespaces
# --------------------------------------------------------------------------- #


def test_unknown_namespace_prefix_survives_roundtrip():
    xml = _wrap(
        '<rdf:Description rdf:about="" xmlns:custom="http://example.com/custom/">'
        "<custom:Foo>bar</custom:Foo></rdf:Description>"
    )
    m = _parse(xml, lenient=True)
    schema = m.get_all_schemas()[0]
    assert schema.get_namespace() == "http://example.com/custom/"
    assert schema.get_prefix() == "custom"
    out = _serialize(m).decode("utf-8")
    assert 'xmlns:custom="http://example.com/custom/"' in out
    assert "<custom:Foo>bar</custom:Foo>" in out


def test_two_namespaces_in_one_description_split_into_schemas():
    xml = _wrap(
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
        "<dc:format>text/plain</dc:format>"
        "<xmp:CreatorTool>Tool</xmp:CreatorTool></rdf:Description>"
    )
    m = _parse(xml)
    namespaces = {s.get_namespace() for s in m.get_all_schemas()}
    assert "http://purl.org/dc/elements/1.1/" in namespaces
    assert "http://ns.adobe.com/xap/1.0/" in namespaces


def test_schema_split_across_descriptions_merges_by_namespace():
    xml = _wrap(
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:format>application/pdf</dc:format></rdf:Description>"
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:source>src</dc:source></rdf:Description>"
    )
    m = _parse(xml)
    dc_schemas = [s for s in m.get_all_schemas() if s.get_namespace() == DC_NS]
    assert len(dc_schemas) == 1
    props = dc_schemas[0].get_all_properties()
    assert props.get("format") == "application/pdf"
    assert props.get("source") == "src"


# --------------------------------------------------------------------------- #
# empty / unicode / whitespace values
# --------------------------------------------------------------------------- #


def test_empty_simple_value_roundtrip():
    m = _parse(_dc_desc("<dc:format></dc:format>"))
    assert m.get_dublin_core_schema().get_format() == ""
    out = _serialize(m).decode("utf-8")
    m2 = _parse(out)
    assert m2.get_dublin_core_schema().get_format() == ""


@pytest.mark.parametrize(
    "text",
    ["élève", "你好世界", "emoji \U0001f600", "Ω≈ç√∫", "mixed café 日本"],
    ids=["accents", "cjk", "emoji", "symbols", "mixed"],
)
def test_unicode_value_roundtrip(text):
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_format(text)
    m2 = _reparse(m)
    assert m2.get_dublin_core_schema().get_format() == text


def test_unicode_in_langalt_value_roundtrip():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_title("日本語タイトル", "ja")
    m2 = _reparse(m)
    assert m2.get_dublin_core_schema().get_title("ja") == "日本語タイトル"


def test_whitespace_only_value_is_stripped():
    # The parser strips surrounding whitespace on simple text nodes.
    m = _parse(_dc_desc("<dc:source>   </dc:source>"))
    assert m.get_dublin_core_schema().get_source() == ""


def test_special_xml_chars_in_value_roundtrip():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_format("a < b & c > d \" e ' f")
    m2 = _reparse(m)
    assert m2.get_dublin_core_schema().get_format() == "a < b & c > d \" e ' f"


# --------------------------------------------------------------------------- #
# typed-property coercion (bool / int / date)
# --------------------------------------------------------------------------- #


def test_integer_property_roundtrips_as_int():
    m = XMPMetadata.create_xmp_metadata()
    basic = m.create_and_add_xmp_basic_schema()
    basic.set_rating(4)
    rating = _reparse(m).get_xmp_basic_schema().get_rating()
    assert rating == 4
    assert isinstance(rating, int)


def test_boolean_property_serializes_capitalised_and_roundtrips():
    m = XMPMetadata.create_xmp_metadata()
    rights = m.create_and_add_xmp_rights_management_schema()
    rights.set_marked(True)
    out = _serialize(m).decode("utf-8")
    assert "<xmpRights:Marked>True</xmpRights:Marked>" in out
    marked = _parse(out).get_xmp_rights_management_schema().get_marked()
    assert marked is True


def test_boolean_false_roundtrip():
    m = XMPMetadata.create_xmp_metadata()
    rights = m.create_and_add_xmp_rights_management_schema()
    rights.set_marked(False)
    out = _serialize(m).decode("utf-8")
    assert "<xmpRights:Marked>False</xmpRights:Marked>" in out
    assert _parse(out).get_xmp_rights_management_schema().get_marked() is False


def test_date_property_iso8601_roundtrip():
    dt = datetime(2021, 3, 4, 5, 6, 7, tzinfo=UTC)
    m = XMPMetadata.create_xmp_metadata()
    basic = m.create_and_add_xmp_basic_schema()
    basic.set_create_date(dt)
    out = _serialize(m).decode("utf-8")
    # Upstream DateConverter.toISO8601 emits explicit +HH:MM, not 'Z'.
    assert "2021-03-04T05:06:07+00:00" in out
    got = _parse(out).get_xmp_basic_schema().get_create_date_value()
    assert got == dt


def test_date_seq_roundtrip_stays_seq():
    m = _parse(
        _dc_desc(
            "<dc:date><rdf:Seq><rdf:li>2020-01-01</rdf:li>"
            "<rdf:li>2021-02-02</rdf:li></rdf:Seq></dc:date>"
        )
    )
    out = _serialize(m).decode("utf-8")
    assert "<dc:date><rdf:Seq>" in out


# --------------------------------------------------------------------------- #
# duplicate properties
# --------------------------------------------------------------------------- #


def test_duplicate_langalt_entry_last_wins():
    # Two rdf:li with the same xml:lang collapse to one (last value wins) —
    # the parsed lang map is keyed by language.
    m = _parse(
        _dc_desc(
            '<dc:title><rdf:Alt><rdf:li xml:lang="en">First</rdf:li>'
            '<rdf:li xml:lang="en">Second</rdf:li></rdf:Alt></dc:title>'
        )
    )
    dc = m.get_dublin_core_schema()
    assert dc.get_title("en") == "Second"
    assert dc.get_title_languages() == ["en"]


def test_repeated_setter_overwrites_simple_value():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_format("first")
    dc.set_format("second")
    assert _reparse(m).get_dublin_core_schema().get_format() == "second"


# --------------------------------------------------------------------------- #
# malformed RDF -> XmpParsingException with the right ErrorType
# --------------------------------------------------------------------------- #


def test_missing_rdf_root_raises_no_root_element():
    with pytest.raises(XmpParsingException) as exc:
        _parse('<x:xmpmeta xmlns:x="adobe:ns:meta/"></x:xmpmeta>')
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.NO_ROOT_ELEMENT


def test_truncated_xml_raises_undefined():
    with pytest.raises(XmpParsingException) as exc:
        _parse("<rdf:RDF><unclosed>")
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.UNDEFINED


def test_empty_input_raises_undefined():
    with pytest.raises(XmpParsingException) as exc:
        _parse("")
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.UNDEFINED


def test_doctype_rejected_as_undefined():
    body = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE rdf:RDF []>"
        f'<rdf:RDF xmlns:rdf="{RDF_NS}"></rdf:RDF>'
    )
    with pytest.raises(XmpParsingException) as exc:
        _parse(body)
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.UNDEFINED


def test_bad_xpacket_end_marker_rejected():
    body = (
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        f'<rdf:RDF xmlns:rdf="{RDF_NS}"></rdf:RDF>'
        '<?xpacket end="z"?>'
    )
    with pytest.raises(XmpParsingException) as exc:
        _parse(body)
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.XPACKET_BAD_END


def test_unknown_simple_property_on_dc_is_tolerated():
    # DublinCoreSchema has no KNOWN_PROPERTIES allow-list, so an unrecognised
    # simple property is accepted and stored as text in both strict and
    # lenient modes (upstream falls back to a TextType for it).
    m = _parse(_dc_desc("<dc:bogusProperty>x</dc:bogusProperty>"))
    assert m.get_dublin_core_schema().get_all_properties()["bogusProperty"] == "x"


def test_unknown_simple_property_on_dc_lenient_tolerated():
    m = _parse(_dc_desc("<dc:bogusProperty>x</dc:bogusProperty>"), lenient=True)
    assert m.get_dublin_core_schema().get_all_properties()["bogusProperty"] == "x"


def test_empty_rdf_yields_no_schemas():
    m = _parse(f'<rdf:RDF xmlns:rdf="{RDF_NS}"></rdf:RDF>')
    assert m.get_all_schemas() == []


def test_cardinality_mismatch_simple_as_array_strict_raises():
    # dc:format is Simple; presenting it as a Bag is an INVALID_TYPE in strict.
    with pytest.raises(XmpParsingException) as exc:
        _parse(
            _dc_desc(
                "<dc:format><rdf:Bag><rdf:li>x</rdf:li></rdf:Bag></dc:format>"
            )
        )
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.INVALID_TYPE


def test_cardinality_mismatch_alt_as_text_strict_raises():
    # dc:title is Alt; presenting it as bare text is INVALID_TYPE in strict.
    with pytest.raises(XmpParsingException) as exc:
        _parse(_dc_desc("<dc:title>bare</dc:title>"))
    assert exc.value.get_error_type() == XmpParsingException.ErrorType.INVALID_TYPE


# --------------------------------------------------------------------------- #
# xpacket envelope preservation
# --------------------------------------------------------------------------- #


def test_serialize_without_xpacket_omits_processing_instructions():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_format("text/plain")
    out = _serialize(m, with_xpacket=False).decode("utf-8")
    assert "<?xpacket" not in out
    assert "<x:xmpmeta" in out


def test_serialized_packet_has_no_xml_declaration():
    m = XMPMetadata.create_xmp_metadata()
    dc = m.create_and_add_dublin_core_schema()
    dc.set_format("text/plain")
    out = _serialize(m).decode("utf-8")
    assert not out.startswith("<?xml")
    assert out.startswith("<?xpacket")
