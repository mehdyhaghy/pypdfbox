"""Wave 1370 — RDF Bag / Seq / Alt cardinality on parse + serialize.

Mirrors the upstream behaviour that ``<rdf:Bag>`` / ``<rdf:Seq>`` /
``<rdf:Alt>`` containers round-trip into the corresponding
:class:`Cardinality` flavour on the :class:`ArrayProperty` produced by
``set_unqualified_*`` schema helpers.
"""

from __future__ import annotations

import io

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer

_HEADER = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
)
_FOOTER = b"</x:xmpmeta><?xpacket end=\"w\"?>"


def _wrap(rdf: bytes) -> bytes:
    return _HEADER + rdf + _FOOTER


# ---------------------------------------------------------------------------
# Bag: unordered.
# ---------------------------------------------------------------------------


def test_rdf_bag_parses_to_string_list() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:subject><rdf:Bag>"
        b"<rdf:li>pdf</rdf:li><rdf:li>parity</rdf:li><rdf:li>xmpbox</rdf:li>"
        b"</rdf:Bag></dc:subject>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    items = dc.get_unqualified_bag_value_list("subject")
    assert items is not None
    assert set(items) == {"pdf", "parity", "xmpbox"}


# ---------------------------------------------------------------------------
# Seq: ordered.
# ---------------------------------------------------------------------------


def test_rdf_seq_preserves_order() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:creator><rdf:Seq>"
        b"<rdf:li>Ada</rdf:li><rdf:li>Bob</rdf:li><rdf:li>Carol</rdf:li>"
        b"</rdf:Seq></dc:creator>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    creators = dc.get_unqualified_sequence_value_list("creator")
    assert creators == ["Ada", "Bob", "Carol"]


# ---------------------------------------------------------------------------
# Alt: language-keyed.
# ---------------------------------------------------------------------------


def test_rdf_alt_parses_to_lang_dict() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b'<dc:title><rdf:Alt>'
        b'<rdf:li xml:lang="x-default">Hello</rdf:li>'
        b'<rdf:li xml:lang="fr">Bonjour</rdf:li>'
        b'<rdf:li xml:lang="ja">'
        b"\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf"
        b"</rdf:li>"
        b"</rdf:Alt></dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_title("x-default") == "Hello"
    assert dc.get_title("fr") == "Bonjour"
    assert (
        dc.get_title("ja")
        == "こんにちは"
    )


def test_rdf_alt_li_without_xml_lang_defaults_to_x_default() -> None:
    """An ``rdf:Alt`` with a single ``rdf:li`` missing ``xml:lang`` is
    treated as the ``x-default`` value (PDFBox lenient fallback)."""
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b'<dc:title><rdf:Alt><rdf:li>Untagged</rdf:li></rdf:Alt></dc:title>'
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_title("x-default") == "Untagged"


# ---------------------------------------------------------------------------
# Empty containers — return either an empty list, a one-item structure, or
# ``None`` (depending on container flavour) without crashing.
# ---------------------------------------------------------------------------


def test_empty_bag_yields_empty_list() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:subject><rdf:Bag/></dc:subject>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    # Either None (no array constructed) or an empty list — both are valid
    # interpretations; assert we don't crash and the schema is present.
    result = dc.get_unqualified_bag_value_list("subject")
    assert result is None or result == []


# ---------------------------------------------------------------------------
# Serialize round-trip — cardinality flavour reappears in the output.
# ---------------------------------------------------------------------------


def _serialize(meta) -> bytes:
    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=False)
    return out.getvalue()


def test_serialize_seq_carries_rdf_seq_tag() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:creator><rdf:Seq>"
        b"<rdf:li>One</rdf:li><rdf:li>Two</rdf:li>"
        b"</rdf:Seq></dc:creator>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    blob = _serialize(meta)
    assert b"rdf:Seq" in blob
    # Order preserved.
    one_pos = blob.find(b">One<")
    two_pos = blob.find(b">Two<")
    assert one_pos < two_pos


def test_serialize_alt_carries_rdf_alt_tag_and_xml_lang() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b'<dc:title><rdf:Alt>'
        b'<rdf:li xml:lang="x-default">Hi</rdf:li>'
        b'<rdf:li xml:lang="de">Hallo</rdf:li>'
        b"</rdf:Alt></dc:title>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    blob = _serialize(meta)
    assert b"rdf:Alt" in blob
    assert b"x-default" in blob
    assert b"Hallo" in blob


def test_serialize_bag_carries_rdf_bag_tag() -> None:
    body = _wrap(
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:subject><rdf:Bag>"
        b"<rdf:li>alpha</rdf:li><rdf:li>beta</rdf:li>"
        b"</rdf:Bag></dc:subject>"
        b"</rdf:Description></rdf:RDF>"
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    blob = _serialize(meta)
    assert b"rdf:Bag" in blob
    assert b"alpha" in blob
    assert b"beta" in blob


# ---------------------------------------------------------------------------
# parse_property direct unit test (upstream alias).
# ---------------------------------------------------------------------------


def test_parse_property_alias_returns_bag_as_list() -> None:
    from xml.etree import ElementTree as ET

    elem = ET.fromstring(
        '<dc:subject xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        "<rdf:Bag><rdf:li>x</rdf:li><rdf:li>y</rdf:li></rdf:Bag></dc:subject>"
    )
    parser = DomXmpParser()
    result = parser.parse_property(elem)
    assert result == ["x", "y"]


def test_parse_property_alias_returns_alt_as_dict() -> None:
    from xml.etree import ElementTree as ET

    elem = ET.fromstring(
        '<dc:title xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        ' xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        '<rdf:Alt><rdf:li xml:lang="x-default">D</rdf:li>'
        '<rdf:li xml:lang="fr">F</rdf:li></rdf:Alt></dc:title>'
    )
    parser = DomXmpParser()
    result = parser.parse_property(elem)
    assert result == {"x-default": "D", "fr": "F"}


def test_parse_property_alias_returns_simple_text() -> None:
    from xml.etree import ElementTree as ET

    elem = ET.fromstring(
        '<pdf:Producer xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        "pypdfbox</pdf:Producer>"
    )
    parser = DomXmpParser()
    assert parser.parse_property(elem) == "pypdfbox"
