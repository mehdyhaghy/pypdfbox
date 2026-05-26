"""Robustness (wave 1405): XMP packets must not carry a DTD.

XMP metadata is parsed on essentially any PDF that has metadata, so the XMP
packet is one of the most-exposed untrusted-XML surfaces. ``DomXmpParser`` hands
the packet bytes to ``xml.etree.ElementTree`` (expat), which expands internal
entities — a "billion laughs" DoS vector. ISO 16684-1 §7.3.2 forbids a DOCTYPE
in an XMP packet, so the parser now rejects any DOCTYPE before parsing.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XmpParsingException
from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser

_VALID_XMP = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
    b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b'<rdf:Description rdf:about="">'
    b"<dc:format>application/pdf</dc:format>"
    b"</rdf:Description></rdf:RDF></x:xmpmeta>"
)


def test_xmp_with_doctype_rejected() -> None:
    payload = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "v">]>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">&e;</x:xmpmeta>'
    )
    with pytest.raises(XmpParsingException):
        DomXmpParser().parse(payload)


def test_xmp_comment_padded_doctype_rejected() -> None:
    payload = (
        b'<?xml version="1.0"?><!-- ' + b"A" * 2100 + b" -->"
        b'<!DOCTYPE x [<!ENTITY e "v">]>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">&e;</x:xmpmeta>'
    )
    with pytest.raises(XmpParsingException):
        DomXmpParser().parse(payload)


def test_valid_xmp_still_parses() -> None:
    meta = DomXmpParser().parse(_VALID_XMP)
    assert meta is not None
    assert meta.get_dublin_core_schema().get_format() == "application/pdf"
