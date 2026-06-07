"""Wave 1370 — :class:`DomXmpParser` tolerance for malformed packets.

Targets the lenient code paths that survive imperfect upstream
producers: malformed / mixed RDF prefixes, missing ``rdf:about``,
multiple namespaces sharing one ``rdf:Description``, BOM/whitespace
prefixes, and embedded comments.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser, XmpParsingException

_HEADER = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
)
_FOOTER = b"</x:xmpmeta><?xpacket end=\"w\"?>"


def _wrap(rdf: bytes) -> bytes:
    return _HEADER + rdf + _FOOTER


# ---------------------------------------------------------------------------
# Missing rdf:about — schemas accept empty-string default.
# ---------------------------------------------------------------------------


def test_missing_rdf_about_treated_as_empty_string() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b"<rdf:Description><dc:format>application/pdf</dc:format>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    # Upstream getAboutValue() returns None when no rdf:about is set
    # (raw backing string is the empty string).
    assert dc.get_about() == ""
    assert dc.get_about_value() is None


def test_empty_rdf_about_attribute_round_trips() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:format>image/png</dc:format>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_about() == ""


# ---------------------------------------------------------------------------
# Mixed namespaces in a single rdf:Description — each schema is created.
# ---------------------------------------------------------------------------


def test_mixed_namespaces_in_single_description() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/"'
        b' xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:format>application/pdf</dc:format>"
        b"<pdf:Producer>pypdfbox</pdf:Producer>"
        b"<xmp:CreatorTool>pypdfbox</xmp:CreatorTool>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    # All three schemas must be discoverable.
    assert meta.get_dublin_core_schema() is not None
    assert meta.get_schema("http://ns.adobe.com/pdf/1.3/") is not None
    assert meta.get_xmp_basic_schema() is not None


def test_split_descriptions_same_namespace_merge() -> None:
    """Two ``rdf:Description`` blocks for the same namespace fold into
    one schema."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about=""><dc:format>image/jpeg</dc:format>'
        b'</rdf:Description>'
        b'<rdf:Description rdf:about=""><dc:source>cam-1</dc:source>'
        b'</rdf:Description></rdf:RDF>'
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    # Exactly one Dublin Core schema, but both properties present.
    dc_schemas = [
        s
        for s in meta.get_all_schemas()
        if s.get_namespace() == "http://purl.org/dc/elements/1.1/"
    ]
    assert len(dc_schemas) == 1
    dc = dc_schemas[0]
    assert dc.get_format() == "image/jpeg"
    assert dc.get_source() == "cam-1"


# ---------------------------------------------------------------------------
# Strict vs lenient: unknown property under a defined schema.
# ---------------------------------------------------------------------------


def test_strict_mode_rejects_unknown_property_on_known_schema() -> None:
    # AdobePDFSchema declares a KNOWN_PROPERTIES allow-list.
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        b'<rdf:Description rdf:about="">'
        b"<pdf:NotARealProperty>nope</pdf:NotARealProperty>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(True)
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_lenient_mode_accepts_unknown_property_on_known_schema() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        b'<rdf:Description rdf:about="">'
        b"<pdf:NotARealProperty>ok</pdf:NotARealProperty>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    schema = meta.get_schema("http://ns.adobe.com/pdf/1.3/")
    assert schema is not None


# ---------------------------------------------------------------------------
# Throw-exception alias is the strict-parsing toggle (upstream parity).
# ---------------------------------------------------------------------------


def test_throw_exception_alias_round_trips_with_strict_flag() -> None:
    parser = DomXmpParser()
    parser.set_throw_exception_on_invalid_xmp(False)
    assert parser.is_throw_exception_on_invalid_xmp() is False
    assert parser.is_strict_parsing() is False
    parser.set_throw_exception_on_invalid_xmp(True)
    assert parser.is_throw_exception_on_invalid_xmp() is True
    assert parser.is_strict_parsing() is True


# ---------------------------------------------------------------------------
# Malformed RDF: parser surfaces FORMAT error.
# ---------------------------------------------------------------------------


def test_malformed_rdf_surfaces_undefined_error() -> None:
    # Unclosed Description tag — expat hard-fails. Upstream's ``parse`` wraps
    # the resulting SAXException as ``ErrorType.Undefined`` ("Failed to
    # parse: ...", DomXmpParser line 140), not FORMAT. Validated against the
    # live xmpbox 3.0.7 oracle in
    # tests/xmpbox/oracle/test_xmp_parse_fuzz_wave1512.py.
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about=""><dc:format>oops'
        b"</rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert excinfo.value.get_error_type() is XmpParsingException.ErrorType.UNDEFINED


def test_malformed_rdf_prefix_unknown_namespace_keeps_prefix() -> None:
    """Unknown ``ns0`` namespace round-trips as a free-form schema."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:weird="urn:vendor:weird">'
        b'<rdf:Description rdf:about="">'
        b"<weird:custom>1</weird:custom>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    schema = meta.get_schema("urn:vendor:weird")
    assert schema is not None
    # Plain XMPSchema picks up the source prefix rather than ``ns0``.
    assert schema.get_prefix() == "weird"


# ---------------------------------------------------------------------------
# XML comments / blanks are stripped silently.
# ---------------------------------------------------------------------------


def test_xml_comments_inside_packet_dont_break_parse() -> None:
    body = _wrap(
        b"<!-- packet comment -->\n"
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b"<!-- inner -->"
        b'<rdf:Description rdf:about="">'
        b"<dc:format>text/xml</dc:format>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_format() == "text/xml"


# ---------------------------------------------------------------------------
# Attribute-form (shorthand) properties parse identically to element-form.
# ---------------------------------------------------------------------------


def test_attribute_shorthand_form_yields_text_property() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        b'<rdf:Description rdf:about="" pdf:Producer="pypdfbox-1.0"/>'
        b"</rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    pdf_schema = meta.get_schema("http://ns.adobe.com/pdf/1.3/")
    assert pdf_schema is not None
    assert pdf_schema.get_producer() == "pypdfbox-1.0"
