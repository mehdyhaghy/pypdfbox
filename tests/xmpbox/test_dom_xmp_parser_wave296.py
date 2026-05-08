from __future__ import annotations

from pypdfbox.xmpbox import DomXmpParser, DublinCoreSchema
from pypdfbox.xmpbox.dom_xmp_parser import parse as module_parse

SIMPLE_PACKET = (
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
    b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b'<rdf:Description rdf:about="">'
    b"<dc:format>application/pdf</dc:format>"
    b"</rdf:Description></rdf:RDF>"
)


def test_parse_accepts_memoryview_input() -> None:
    metadata = DomXmpParser().parse(memoryview(SIMPLE_PACKET))

    dc = metadata.get_dublin_core_schema()
    assert isinstance(dc, DublinCoreSchema)
    assert dc.get_format() == "application/pdf"


def test_parse_input_and_module_parse_accept_memoryview_input() -> None:
    class_metadata = DomXmpParser().parse_input(memoryview(SIMPLE_PACKET))
    module_metadata = module_parse(memoryview(SIMPLE_PACKET))

    class_dc = class_metadata.get_dublin_core_schema()
    module_dc = module_metadata.get_dublin_core_schema()
    assert isinstance(class_dc, DublinCoreSchema)
    assert isinstance(module_dc, DublinCoreSchema)
    assert class_dc.get_format() == "application/pdf"
    assert module_dc.get_format() == "application/pdf"
