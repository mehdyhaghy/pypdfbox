"""Wave 1370 — additional upstream :class:`DomXmpParser` port cases.

Ports the upstream ``DomXmpParserTest`` cases that map cleanly onto our
parser's current behaviour. Cases that depend on richer error semantics
(``BadInner``, ``NoSchema``, ``TextInsteadOfArray`` — all of which need
upstream's full type-system validator) are intentionally skipped with a
documented reason rather than translated to a slightly-different
assertion that would mislead readers about behavioral parity.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser, XmpParsingException

# ---------------------------------------------------------------------------
# testParseFailure — empty body / declaration-only input.
# ---------------------------------------------------------------------------


def test_parse_failure_xml_declaration_only_raises() -> None:
    """Upstream: ``testParseFailure`` — XML declaration with no root element
    surfaces FORMAT (upstream returned a "Failed to parse" message)."""
    s = b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(s)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.FORMAT
    )


# ---------------------------------------------------------------------------
# testBadRdfNameSpace — RDF namespace must be exactly the canonical URI.
# ---------------------------------------------------------------------------


def test_bad_rdf_namespace_https_variant_loses_rdf_dispatch() -> None:
    """Upstream ``testBadRdfNameSpace``: ``https://...`` for the rdf
    namespace is not the canonical ``http://...``, so ``rdf:RDF`` is not
    found and parsing fails with NO_ROOT_ELEMENT.
    """
    s = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="https://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(s)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.NO_ROOT_ELEMENT
    )


# ---------------------------------------------------------------------------
# testBadLocalName / testBadLocalNameStrict — already covered by
# tests/xmpbox/upstream/test_dom_xmp_parser.py; here we cover the
# parse_initial_xpacket / parse_end_packet round-trip on these inputs.
# ---------------------------------------------------------------------------


def test_parse_initial_xpacket_round_trips_attributes() -> None:
    """Upstream ``parseInitialXpacket``: begin/id/bytes/encoding all
    populated from a well-formed PI body."""
    parser = DomXmpParser()
    result = parser.parse_initial_xpacket(
        'begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d" '
        'bytes="2000" encoding="UTF-8"'
    )
    assert result["begin"] == "\xef\xbb\xbf"
    assert result["id"] == "W5M0MpCehiHzreSzNTczkc9d"
    assert result["bytes"] == "2000"
    assert result["encoding"] == "UTF-8"


def test_parse_end_packet_accepts_r_marker() -> None:
    parser = DomXmpParser()
    assert parser.parse_end_packet('end="r"') == "r"


def test_parse_end_packet_accepts_w_marker() -> None:
    parser = DomXmpParser()
    assert parser.parse_end_packet('end="w"') == "w"


def test_parse_end_packet_rejects_unknown_marker() -> None:
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_end_packet('end="z"')
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_END
    )


def test_parse_end_packet_rejects_missing_end_attribute() -> None:
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse_end_packet('id="foo"')
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_END
    )


# ---------------------------------------------------------------------------
# testNamespaceInRoot — xmlns declarations on x:xmpmeta wrapper are honored
# (the schemas they bind are accessible through the parsed metadata).
# ---------------------------------------------------------------------------


def test_namespace_in_root_round_trips() -> None:
    """Upstream ``testNamespaceInRoot``: when the xmpmeta wrapper carries
    schema namespace declarations rather than the rdf:Description, the
    parser still resolves the inner property under the right schema."""
    s = (
        b'<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
        b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/"'
        b' xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/"'
        b' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b"<rdf:RDF>"
        b'<rdf:Description rdf:about="">'
        b"<pdfuaid:part>1</pdfuaid:part>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(s)
    pdfua = meta.get_pdfua_identification_schema()
    assert pdfua is not None


# ---------------------------------------------------------------------------
# Skip placeholders — upstream tests requiring richer type-system semantics.
# ---------------------------------------------------------------------------


def test_no_schema_xml_namespace_rejected() -> None:
    """Upstream ``testNoSchema``: a property element whose owning namespace
    is the reserved ``xml:`` namespace cannot be dispatched to any schema
    (the XML reserved namespace is not a schema). Strict mode rejects with
    ``NO_SCHEMA`` (wave 1374 closes the reserved-namespace vs
    unknown-schema distinction)."""
    s = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        b'<rdf:Description rdf:about="">'
        b'<xml:something>value</xml:something>'
        b'</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(s)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.NO_SCHEMA
    )


def test_no_schema_xml_namespace_silently_skipped_in_lenient_mode() -> None:
    """Lenient mode tolerates the reserved-namespace property by dropping
    it (matches upstream's recovery path; no exception raised)."""
    s = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        b'<rdf:Description rdf:about="">'
        b'<xml:something>value</xml:something>'
        b'</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    # Parses without raising; the xml:* element is dropped and no schema is
    # added for the reserved namespace.
    meta = parser.parse(s)
    # Confirm the xml namespace did NOT slip into the schema set.
    for schema in meta.get_all_schemas():
        assert schema.get_namespace() != (
            "http://www.w3.org/XML/1998/namespace"
        )


def test_text_instead_of_array_rejected() -> None:
    """Upstream ``testTextInsteadOfArray``: ``dc:title`` is declared as
    LangAlt; presenting it as a bare Text node is rejected in strict mode
    via the typed-property registry (wave 1371)."""
    s = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="3.1-701">\n'
        b'\t<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        b'\t\t<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
        b'\t\t                 rdf:about="">\n'
        b'\t\t\t<dc:title>Title</dc:title>\n'
        b'\t\t</rdf:Description>\n'
        b'\t</rdf:RDF>\n'
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(s)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_bad_inner_parse_type_mismatch_rejected() -> None:
    """Upstream ``testBadInner``: ``xmpMM:parseType="Resource"`` (non-rdf
    namespace on ``parseType``) is rejected; only ``rdf:parseType`` is
    honoured (wave 1371)."""
    s = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        b'    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        b'        <rdf:Description'
        b' xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"'
        b' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">\n'
        b'            <xmpMM:DerivedFrom xmpMM:parseType="Resource">\n'
        b'                <stRef:instanceID>uuid:abc</stRef:instanceID>\n'
        b'            </xmpMM:DerivedFrom>\n'
        b'        </rdf:Description>\n'
        b'    </rdf:RDF>\n'
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(s)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )
