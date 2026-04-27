from __future__ import annotations

from pypdfbox.xmpbox import (
    DomXmpParser,
    XMPMetadata,
    XMPageTextSchema,
)


def _pt() -> XMPageTextSchema:
    return XMPageTextSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _pt()
    assert XMPageTextSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/t/pg/"
    assert XMPageTextSchema.PREFERRED_PREFIX == "xmpTPg"
    assert schema.get_namespace() == "http://ns.adobe.com/xap/1.0/t/pg/"
    assert schema.get_prefix() == "xmpTPg"


def test_local_name_constants_match_upstream() -> None:
    assert XMPageTextSchema.MAX_PAGE_SIZE == "MaxPageSize"
    assert XMPageTextSchema.N_PAGES == "NPages"
    assert XMPageTextSchema.PLATENAMES == "PlateNames"
    assert XMPageTextSchema.COLORANTS == "Colorants"
    assert XMPageTextSchema.FONTS == "Fonts"


def test_default_accessors_return_none() -> None:
    schema = _pt()
    assert schema.get_n_pages() is None
    assert schema.get_max_page_size() is None
    assert schema.get_plate_names() is None
    assert schema.get_colorants() is None
    assert schema.get_fonts() is None


def test_n_pages_round_trip() -> None:
    schema = _pt()
    schema.set_n_pages(42)
    assert schema.get_n_pages() == 42
    # Setting None clears.
    schema.set_n_pages(None)
    assert schema.get_n_pages() is None


def test_n_pages_returns_none_when_value_is_not_integer() -> None:
    schema = _pt()
    # Simulate a parser-stored bogus value.
    schema.set_property(XMPageTextSchema.N_PAGES, "not-a-number")
    assert schema.get_n_pages() is None


def test_max_page_size_round_trip_dict_payload() -> None:
    schema = _pt()
    payload = {"w": "612", "h": "792", "unit": "Pt"}
    schema.set_max_page_size(payload)
    assert schema.get_max_page_size() == payload
    schema.set_max_page_size(None)
    assert schema.get_max_page_size() is None


def test_plate_names_seq_add_and_remove() -> None:
    schema = _pt()
    schema.add_plate_name("Cyan")
    schema.add_plate_name("Magenta")
    schema.add_plate_name("Yellow")
    schema.add_plate_name("Black")
    assert schema.get_plate_names() == ["Cyan", "Magenta", "Yellow", "Black"]
    schema.remove_plate_name("Magenta")
    assert schema.get_plate_names() == ["Cyan", "Yellow", "Black"]


def test_colorants_seq_add_and_get() -> None:
    schema = _pt()
    schema.add_colorant("PANTONE 185 C")
    schema.add_colorant({"swatchName": "PANTONE 116 C", "type": "SPOT"})
    colorants = schema.get_colorants()
    assert colorants is not None
    assert len(colorants) == 2
    assert colorants[0] == "PANTONE 185 C"
    assert colorants[1] == {"swatchName": "PANTONE 116 C", "type": "SPOT"}


def test_fonts_bag_add_and_get() -> None:
    schema = _pt()
    schema.add_font("Helvetica")
    schema.add_font("TimesNewRoman")
    fonts = schema.get_fonts()
    assert fonts is not None
    assert set(fonts) == {"Helvetica", "TimesNewRoman"}


def test_xmp_metadata_create_and_add_returns_typed_wrapper() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_page_text_schema() is None

    schema = metadata.create_and_add_page_text_schema()
    assert isinstance(schema, XMPageTextSchema)
    # rdf:about defaults to "" (empty string) per upstream semantics.
    assert schema.get_about() == ""
    # The lookup accessor finds the same instance.
    assert metadata.get_page_text_schema() is schema


def test_round_trip_through_xmp_packet_attribute_form() -> None:
    # Exercise the parser path: xmpTPg:NPages as an attribute on rdf:Description.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpTPg='http://ns.adobe.com/xap/1.0/t/pg/'"
        b" xmpTPg:NPages='12'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPageTextSchema)
    assert isinstance(schema, XMPageTextSchema)
    assert schema.get_n_pages() == 12
    # Convenience accessor finds the same schema instance.
    assert metadata.get_page_text_schema() is schema


def test_round_trip_through_xmp_packet_seq_and_bag() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpTPg='http://ns.adobe.com/xap/1.0/t/pg/'>"
        b"<xmpTPg:NPages>3</xmpTPg:NPages>"
        b"<xmpTPg:PlateNames>"
        b"<rdf:Seq>"
        b"<rdf:li>Cyan</rdf:li>"
        b"<rdf:li>Magenta</rdf:li>"
        b"<rdf:li>Yellow</rdf:li>"
        b"</rdf:Seq>"
        b"</xmpTPg:PlateNames>"
        b"<xmpTPg:Fonts>"
        b"<rdf:Bag>"
        b"<rdf:li>Helvetica</rdf:li>"
        b"<rdf:li>Arial</rdf:li>"
        b"</rdf:Bag>"
        b"</xmpTPg:Fonts>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPageTextSchema)
    assert isinstance(schema, XMPageTextSchema)
    assert schema.get_n_pages() == 3
    assert schema.get_plate_names() == ["Cyan", "Magenta", "Yellow"]
    fonts = schema.get_fonts()
    assert fonts is not None
    assert set(fonts) == {"Helvetica", "Arial"}


def test_subclass_constructor_accepts_custom_prefix() -> None:
    # Upstream supports a (metadata, prefix) constructor variant; mirror that.
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPageTextSchema(metadata, "customTPg")
    assert schema.get_prefix() == "customTPg"
    assert schema.get_namespace() == XMPageTextSchema.NAMESPACE
