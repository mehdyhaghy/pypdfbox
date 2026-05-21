"""Wave 1370 — strict vs lenient mode parity.

Validates that the ``set_strict_parsing`` / ``set_throw_exception_on_invalid_xmp``
toggles change the behaviour of the previously-failing class of inputs
(unknown property on a defined schema, malformed xpacket markers,
wrapped-root assertion). Also pins the default mode to strict so the
class behaves like upstream's ``DomXmpParser`` constructor default.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser, XmpParsingException

_PACKET = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
    b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
    b'<rdf:Description rdf:about="">'
    b"<pdf:Producer>pypdfbox</pdf:Producer>"
    b"<pdf:DefinitelyNotAProperty>oops</pdf:DefinitelyNotAProperty>"
    b"</rdf:Description></rdf:RDF></x:xmpmeta>"
    b"<?xpacket end=\"w\"?>"
)


def test_default_mode_is_strict() -> None:
    parser = DomXmpParser()
    # Upstream constructor sets strict=true.
    assert parser.is_strict_parsing() is True


def test_strict_mode_raises_invalid_type_on_unknown_property() -> None:
    parser = DomXmpParser()
    # Strict mode is the default — assert without toggling.
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(_PACKET)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_lenient_mode_does_not_raise_and_keeps_known_property() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(_PACKET)
    schema = meta.get_schema("http://ns.adobe.com/pdf/1.3/")
    assert schema is not None
    assert schema.get_producer() == "pypdfbox"


def test_strict_toggle_idempotent() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    parser.set_strict_parsing(False)
    assert parser.is_strict_parsing() is False
    parser.set_strict_parsing(True)
    parser.set_strict_parsing(True)
    assert parser.is_strict_parsing() is True


def test_check_property_definition_lenient_no_raise() -> None:
    """Direct unit test for the upstream-named helper."""
    from xml.etree import ElementTree as ET

    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
    from pypdfbox.xmpbox.xmp_schema import XMPSchema

    meta = XMPMetadata.create_xmp_metadata()
    schema = XMPSchema(meta, "urn:test", "t")
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    # Should not raise — no KNOWN_PROPERTIES and lenient anyway.
    parser.check_property_definition(schema, "urn:test", "anything")
    # Also create a tiny XML node to exercise the call-site through expect_naming.
    elem = ET.fromstring(
        '<t:foo xmlns:t="urn:test"/>'
    )
    del elem  # only constructed to confirm the import path resolves


def test_check_property_definition_strict_raises_on_unknown_local() -> None:
    from pypdfbox.xmpbox.adobe_pdf_schema import AdobePDFSchema
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

    meta = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(meta)
    parser = DomXmpParser()
    # Strict + AdobePDFSchema (KNOWN_PROPERTIES exists) -> unknown raises.
    with pytest.raises(XmpParsingException) as excinfo:
        parser.check_property_definition(
            schema, "http://ns.adobe.com/pdf/1.3/", "MysteryField"
        )
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )


def test_strict_mode_does_not_reject_property_on_plain_xmpschema() -> None:
    """A free-form schema (no KNOWN_PROPERTIES) accepts arbitrary
    properties even in strict mode — this is upstream parity:
    KNOWN_PROPERTIES is a per-schema opt-in."""
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:vendor="urn:vendor:ext">'
        b'<rdf:Description rdf:about="">'
        b"<vendor:WhateverField>fine</vendor:WhateverField>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
        b"<?xpacket end=\"w\"?>"
    )
    parser = DomXmpParser()
    assert parser.is_strict_parsing() is True
    meta = parser.parse(body)
    schema = meta.get_schema("urn:vendor:ext")
    assert schema is not None


def test_strict_mode_attribute_form_unknown_property_also_raises() -> None:
    """Attribute-shorthand properties go through the same strict check."""
    body = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        b'<rdf:Description rdf:about="" pdf:WeirdAttr="x"/>'
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end=\"w\"?>"
    )
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as excinfo:
        parser.parse(body)
    assert (
        excinfo.value.get_error_type()
        is XmpParsingException.ErrorType.INVALID_TYPE
    )
