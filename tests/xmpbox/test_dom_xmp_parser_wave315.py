from __future__ import annotations

from pypdfbox.xmpbox import DomXmpParser, DublinCoreSchema


def test_wave315_parse_xpacket_begin_attributes_in_noncanonical_order() -> None:
    packet = (
        b"<?xpacket id='W5M0MpCehiHzreSzNTczkc9d' encoding='UTF-8' "
        b"bytes='123' begin='\xef\xbb\xbf'?>"
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b"<dc:format>application/pdf</dc:format>"
        b"</rdf:Description></rdf:RDF>"
        b"<?xpacket end='r'?>"
    )

    metadata = DomXmpParser().parse(packet)

    assert metadata.get_xpacket_begin() == "\ufeff"
    assert metadata.get_xpacket_id() == "W5M0MpCehiHzreSzNTczkc9d"
    assert metadata.get_xpacket_bytes() == "123"
    assert metadata.get_xpacket_encoding() == "UTF-8"
    assert metadata.get_end_xpacket() == "r"
    dc = metadata.get_dublin_core_schema()
    assert isinstance(dc, DublinCoreSchema)
    assert dc.get_format() == "application/pdf"
