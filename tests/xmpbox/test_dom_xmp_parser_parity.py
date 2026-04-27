from __future__ import annotations

from xml.etree import ElementTree as ET

from pypdfbox.xmpbox import DomXmpParser
from pypdfbox.xmpbox.dom_xmp_parser import _RDF_NS, _XML_NS

SIMPLE_PACKET = b"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:xmp="http://ns.adobe.com/xap/1.0/">
  <rdf:Description rdf:about="">
    <dc:title>
      <rdf:Alt>
        <rdf:li xml:lang="x-default">Hello</rdf:li>
        <rdf:li xml:lang="fr">Bonjour</rdf:li>
      </rdf:Alt>
    </dc:title>
    <dc:creator>
      <rdf:Seq>
        <rdf:li>Alice</rdf:li>
        <rdf:li>Bob</rdf:li>
      </rdf:Seq>
    </dc:creator>
    <xmp:CreatorTool>pypdfbox</xmp:CreatorTool>
  </rdf:Description>
</rdf:RDF>
<?xpacket end="w"?>"""


def test_parse_input_alias_matches_parse() -> None:
    p = DomXmpParser()
    a = p.parse(SIMPLE_PACKET)
    b = p.parse_input(SIMPLE_PACKET)
    assert a.get_xpacket_id() == b.get_xpacket_id()
    # Same set of schema namespaces detected via either entry point.
    assert {s.get_namespace() for s in a.get_all_schemas()} == {
        s.get_namespace() for s in b.get_all_schemas()
    }


def test_strict_parsing_round_trip() -> None:
    p = DomXmpParser()
    # Defaults from upstream: strict on, throw-exception flag mirrors it.
    assert p.is_strict_parsing() is True
    p.set_strict_parsing(False)
    assert p.is_strict_parsing() is False
    p.set_strict_parsing(True)
    assert p.is_strict_parsing() is True


def test_throw_exception_on_invalid_xmp_aliases_strict() -> None:
    p = DomXmpParser()
    p.set_throw_exception_on_invalid_xmp(False)
    assert p.is_throw_exception_on_invalid_xmp() is False
    assert p.is_strict_parsing() is False
    p.set_throw_exception_on_invalid_xmp(True)
    assert p.is_throw_exception_on_invalid_xmp() is True
    assert p.is_strict_parsing() is True


def test_get_namespace_table_returns_known_prefixes() -> None:
    table = DomXmpParser().get_namespace_table()
    assert isinstance(table, dict)
    # Always-present XML/RDF baselines.
    assert table["rdf"] == _RDF_NS
    assert table["xml"] == _XML_NS
    # Built-in schema dispatch table contributors.
    assert table["dc"] == "http://purl.org/dc/elements/1.1/"
    assert table["xmp"] == "http://ns.adobe.com/xap/1.0/"
    assert table["pdfaid"] == "http://www.aiim.org/pdfa/ns/id/"


def test_parse_property_alias_handles_simple_text() -> None:
    elem = ET.fromstring(
        '<xmp:CreatorTool xmlns:xmp="http://ns.adobe.com/xap/1.0/">pypdfbox</xmp:CreatorTool>'
    )
    assert DomXmpParser().parse_property(elem) == "pypdfbox"


def test_parse_property_alias_handles_alt_container() -> None:
    elem = ET.fromstring(
        '<dc:title xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        "<rdf:Alt>"
        '<rdf:li xml:lang="x-default">Hello</rdf:li>'
        '<rdf:li xml:lang="fr">Bonjour</rdf:li>'
        "</rdf:Alt>"
        "</dc:title>"
    )
    result = DomXmpParser().parse_property(elem)
    assert result == {"x-default": "Hello", "fr": "Bonjour"}
