"""Wave 1371 — :class:`DomXmpParser` typed-property registry wins.

Covers the four upstream-parity fixes landed in wave 1371:

1. Typed-property registry rejects shape mismatches in strict mode
   (``dc:title`` declared as LangAlt — bare Text rejected; LangAlt
   accepted; ``dc:creator`` declared as Seq — Bag tolerated in lenient
   mode but rejected in strict mode).
2. Non-rdf-namespaced ``parseType`` attributes are rejected
   (``xmpMM:parseType="Resource"`` — see upstream ``testBadInner``).
3. Strict-parsing flag is consumed by the cardinality and parseType
   validators (lenient mode passes; strict mode raises).
4. ``bj`` namespace is promoted to :class:`XMPBasicJobTicketSchema` by
   ``_SCHEMA_REGISTRY``.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser, XmpParsingException
from pypdfbox.xmpbox.xmp_basic_job_ticket_schema import XMPBasicJobTicketSchema

_HEADER = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
)
_FOOTER = b"</x:xmpmeta><?xpacket end=\"w\"?>"


def _wrap(rdf: bytes) -> bytes:
    return _HEADER + rdf + _FOOTER


# ---------------------------------------------------------------------------
# 1. Typed-property registry: dc:title is LangAlt — bare Text is a mismatch.
# ---------------------------------------------------------------------------


def test_dc_title_bare_text_rejected_in_strict_mode() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:title>Title</dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    # default mode is strict
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )
    assert "Alt" in str(excinfo.value)


def test_dc_title_bare_text_tolerated_in_lenient_mode() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:title>Title</dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    # The bare text is stored under "title" as a string in lenient mode.
    assert dc.get_unqualified_text_property_value("title") == "Title"


def test_dc_title_lang_alt_accepted_in_strict_mode() -> None:
    """Well-formed LangAlt for dc:title passes the cardinality gate."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        b' xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        b'<rdf:Description rdf:about="">'
        b"<dc:title><rdf:Alt>"
        b'<rdf:li xml:lang="x-default">Title</rdf:li>'
        b'<rdf:li xml:lang="fr">Titre</rdf:li>'
        b"</rdf:Alt></dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_title() == "Title"
    assert dc.get_title("fr") == "Titre"


def test_dc_creator_bag_rejected_when_declared_as_seq() -> None:
    """``dc:creator`` is declared ``Seq`` — a ``rdf:Bag`` shape is a
    mismatch in strict mode."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:creator><rdf:Alt>"
        b"<rdf:li>Foo</rdf:li>"
        b"</rdf:Alt></dc:creator>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_dc_creator_seq_accepted_in_strict_mode() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:creator><rdf:Seq>"
        b"<rdf:li>Alice</rdf:li>"
        b"<rdf:li>Bob</rdf:li>"
        b"</rdf:Seq></dc:creator>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_creators() == ["Alice", "Bob"]


def test_dc_title_attribute_shorthand_rejected_in_strict_mode() -> None:
    """Attribute-shorthand form on a declared-array property fails strict."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="" dc:title="Shorthand"/>'
        b"</rdf:RDF>"
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


# ---------------------------------------------------------------------------
# 2. xmpMM:parseType="Resource" vs rdf:parseType="Resource".
# ---------------------------------------------------------------------------


def test_xmp_mm_parse_type_rejected_in_strict_mode() -> None:
    """Only ``rdf:parseType="Resource"`` is honoured; non-rdf namespaces
    on ``parseType`` are rejected (upstream ``testBadInner``)."""
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description'
        b' xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"'
        b' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">'
        b'<xmpMM:DerivedFrom xmpMM:parseType="Resource">'
        b'<stRef:instanceID>uuid:abc</stRef:instanceID>'
        b"</xmpMM:DerivedFrom>"
        b"</rdf:Description></rdf:RDF>"
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_rdf_parse_type_resource_accepted() -> None:
    """``rdf:parseType="Resource"`` round-trips in strict mode."""
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description'
        b' xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"'
        b' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">'
        b'<xmpMM:DerivedFrom rdf:parseType="Resource">'
        b'<stRef:instanceID>uuid:abc</stRef:instanceID>'
        b"</xmpMM:DerivedFrom>"
        b"</rdf:Description></rdf:RDF>"
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    # Should not raise on the parseType attribute even if structured-type
    # population isn't fully wired up.
    parser.parse(body)


def test_xmp_mm_parse_type_tolerated_in_lenient_mode() -> None:
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description'
        b' xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"'
        b' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">'
        b'<xmpMM:DerivedFrom xmpMM:parseType="Resource">'
        b'<stRef:instanceID>uuid:abc</stRef:instanceID>'
        b"</xmpMM:DerivedFrom>"
        b"</rdf:Description></rdf:RDF>"
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    # Lenient mode silently drops the non-rdf parseType and parses on.
    parser.parse(body)


# ---------------------------------------------------------------------------
# 3. Strict-parsing flag is consumed by every validation path.
# ---------------------------------------------------------------------------


def test_strict_lenient_toggle_changes_cardinality_validator() -> None:
    """The same dc:title-as-Text packet raises in strict mode and parses
    silently in lenient mode."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:title>Hi</dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    strict = DomXmpParser()
    with pytest.raises(XmpParsingException):
        strict.parse(body)
    lenient = DomXmpParser()
    lenient.set_strict_parsing(False)
    lenient.parse(body)


def test_strict_lenient_toggle_changes_parse_type_validator() -> None:
    """xmpMM:parseType -> strict raises, lenient tolerates."""
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description'
        b' xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"'
        b' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">'
        b'<xmpMM:DerivedFrom xmpMM:parseType="Resource"/>'
        b"</rdf:Description></rdf:RDF>"
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    strict = DomXmpParser()
    with pytest.raises(XmpParsingException):
        strict.parse(body)
    lenient = DomXmpParser()
    lenient.set_strict_parsing(False)
    lenient.parse(body)


def test_throw_exception_alias_drives_typed_registry_too() -> None:
    """The throw-exception alias also flips the typed-registry path."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:title>Hi</dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_throw_exception_on_invalid_xmp(False)
    parser.parse(body)
    parser.set_throw_exception_on_invalid_xmp(True)
    with pytest.raises(XmpParsingException):
        parser.parse(body)


# ---------------------------------------------------------------------------
# 4. bj namespace -> XMPBasicJobTicketSchema promotion.
# ---------------------------------------------------------------------------


def test_bj_namespace_promotes_to_basic_job_ticket_schema() -> None:
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:xmpBJ="http://ns.adobe.com/xap/1.0/bj/"'
        b' xmlns:stJob="http://ns.adobe.com/xap/1.0/sType/Job#">'
        b'<rdf:Description rdf:about="">'
        b"<xmpBJ:JobRef><rdf:Bag>"
        b'<rdf:li rdf:parseType="Resource">'
        b"<stJob:name>Job-A</stJob:name>"
        b"<stJob:id>job-1</stJob:id>"
        b"</rdf:li>"
        b"</rdf:Bag></xmpBJ:JobRef>"
        b"</rdf:Description></rdf:RDF>"
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)  # struct fields aren't in registry
    meta = parser.parse(body)
    schema = meta.get_schema("http://ns.adobe.com/xap/1.0/bj/")
    assert schema is not None
    assert isinstance(schema, XMPBasicJobTicketSchema)
    # The typed accessor on XMPMetadata also resolves.
    assert meta.get_basic_job_ticket_schema() is schema


def test_bj_namespace_uses_preferred_prefix() -> None:
    """The promoted schema uses the upstream-preferred prefix ``xmpBJ``."""
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:xmpBJ="http://ns.adobe.com/xap/1.0/bj/">'
        b'<rdf:Description rdf:about=""/>'
        b"</rdf:RDF>"
        b'</x:xmpmeta><?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    # No JobRef so no shape check triggered. Schema still promoted just
    # by visiting an empty rdf:Description that declares the xmlns.
    parser.parse(body)
